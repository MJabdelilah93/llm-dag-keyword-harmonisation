"""Synthetic-data tests for the primary gold-standard freeze pipeline:
completed-adjudication validation, the direct-agreement/adjudicated gold
rule, row-by-row verification, stratum/context/outcome summaries, the
held-out and H3-readiness manifests, and the biomedical release-readiness
check. Real-data checks are limited to hashes/gitignore/structure of
files this task must never modify."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook

from strengthening.human_annotation.build_primary_gold_freeze import (
    FROZEN_STRATUM_QUOTAS,
    adjudication_outcome_analysis,
    build_stratum_summary,
    context_use_summary,
    gold_distributions,
    human_annotation_flow,
    verify_gold_row_by_row,
)
from strengthening.human_annotation.finalise_primary_gold import finalise
from strengthening.human_annotation.h2_validate_completed_adjudication import (
    AdjudicationValidationError,
    validate_completed_adjudication,
)
from strengthening.human_annotation.adjudication_session_quality_check import analyze_session
from strengthening.human_annotation.h3_readiness_check import EXPECTED as H3_EXPECTED
from strengthening.human_annotation.heldout_evidence_manifest import DEVELOPMENT_SET, HELD_OUT_DATASETS

PKG_DIR = Path(__file__).resolve().parents[1] / "restricted_local" / "human_annotation" / "v1"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# -- Step 2: completed adjudication validation -------------------------------

def _write_adjudication_workbook(path, rows):
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Disagreements")
    cols = ["adjudication_row", "pair_id", "domain", "string_a", "string_b", "decision_A", "decision_B",
            "justification_A", "justification_B", "context_used_A", "context_used_B",
            "adjudicated_label", "adjudicator_notes", "adjudicator_context_used"]
    ws.append(cols)
    for r in rows:
        ws.append(list(r))
    wb.save(path)


SOURCE_ROWS = [
    (1, "p1", "circular_economy", "a1", "b1", "match", "non-match", "", "", "no", "no", "", "", ""),
    (2, "p2", "biomedical_diabetes_mellitus", "a2", "b2", "non-match", "uncertain", "", "", "no", "no", "", "", ""),
]


def test_validate_completed_adjudication_passes_when_well_formed(tmp_path):
    source = tmp_path / "source.xlsx"
    completed = tmp_path / "completed.xlsx"
    _write_adjudication_workbook(source, SOURCE_ROWS)
    completed_rows = [
        (1, "p1", "circular_economy", "a1", "b1", "match", "non-match", "", "", "no", "no", "match", "", "no"),
        (2, "p2", "biomedical_diabetes_mellitus", "a2", "b2", "non-match", "uncertain", "", "", "no", "no", "uncertain", "", "yes"),
    ]
    _write_adjudication_workbook(completed, completed_rows)
    result = validate_completed_adjudication(completed, source, {"p1", "p2"}, expected_rows=2)
    assert result.ok
    assert result.blank_adjudicated_labels == 0


def test_validate_completed_adjudication_detects_blank_label(tmp_path):
    source = tmp_path / "source.xlsx"
    completed = tmp_path / "completed.xlsx"
    _write_adjudication_workbook(source, SOURCE_ROWS)
    completed_rows = [
        (1, "p1", "circular_economy", "a1", "b1", "match", "non-match", "", "", "no", "no", "", "", ""),
        (2, "p2", "biomedical_diabetes_mellitus", "a2", "b2", "non-match", "uncertain", "", "", "no", "no", "uncertain", "", "no"),
    ]
    _write_adjudication_workbook(completed, completed_rows)
    result = validate_completed_adjudication(completed, source, {"p1", "p2"}, expected_rows=2)
    assert not result.ok
    assert result.blank_adjudicated_labels == 1


def test_validate_completed_adjudication_detects_drifted_decision(tmp_path):
    source = tmp_path / "source.xlsx"
    completed = tmp_path / "completed.xlsx"
    _write_adjudication_workbook(source, SOURCE_ROWS)
    # decision_A changed from "match" to "non-match" -- must never happen
    completed_rows = [
        (1, "p1", "circular_economy", "a1", "b1", "non-match", "non-match", "", "", "no", "no", "match", "", "no"),
        (2, "p2", "biomedical_diabetes_mellitus", "a2", "b2", "non-match", "uncertain", "", "", "no", "no", "uncertain", "", "no"),
    ]
    _write_adjudication_workbook(completed, completed_rows)
    result = validate_completed_adjudication(completed, source, {"p1", "p2"}, expected_rows=2)
    assert not result.ok
    assert "p1" in result.drifted_pair_ids


def test_validate_completed_adjudication_detects_extra_and_missing_pair_ids(tmp_path):
    source = tmp_path / "source.xlsx"
    completed = tmp_path / "completed.xlsx"
    _write_adjudication_workbook(source, SOURCE_ROWS)
    completed_rows = [
        (1, "p1", "circular_economy", "a1", "b1", "match", "non-match", "", "", "no", "no", "match", "", "no"),
        (2, "p3", "biomedical_diabetes_mellitus", "a3", "b3", "match", "match", "", "", "no", "no", "match", "", "no"),
    ]
    _write_adjudication_workbook(completed, completed_rows)
    result = validate_completed_adjudication(completed, source, {"p1", "p2"}, expected_rows=2)
    assert not result.ok
    assert "p2" in result.missing_pair_ids
    assert "p3" in result.extra_pair_ids


def test_validate_completed_adjudication_missing_file_raises(tmp_path):
    with pytest.raises(AdjudicationValidationError):
        validate_completed_adjudication(tmp_path / "nope.xlsx", tmp_path / "also_nope.xlsx", {"p1"})


# -- Step 3: adjudicator session quality check -------------------------------

def test_analyze_session_no_anomaly_on_varied_fast_but_not_stuck_decisions():
    rows = [
        {"timestamp": "2026-09-09T10:00:00+00:00", "pair_id": "p0", "old_label": "", "new_label": "match", "context_used": "no", "action": "label"},
        {"timestamp": "2026-09-09T10:00:02+00:00", "pair_id": "p1", "old_label": "", "new_label": "non-match", "context_used": "no", "action": "label"},
        {"timestamp": "2026-09-09T10:00:03+00:00", "pair_id": "p2", "old_label": "", "new_label": "uncertain", "context_used": "no", "action": "label"},
    ]
    s = analyze_session(rows)
    assert not s["evidence_of_stuck_key_or_autorepeat"]
    assert not s["evidence_of_duplicated_gui_callback"]


def test_analyze_session_flags_sub_100ms_signature():
    rows = [
        {"timestamp": "2026-09-09T10:00:00.000+00:00", "pair_id": "p0", "old_label": "", "new_label": "match", "context_used": "no", "action": "label"},
        {"timestamp": "2026-09-09T10:00:00.020+00:00", "pair_id": "p1", "old_label": "", "new_label": "match", "context_used": "no", "action": "label"},
    ]
    s = analyze_session(rows)
    assert s["evidence_of_stuck_key_or_autorepeat"]


# -- Step 4: direct-agreement / adjudicated gold rule (finalise) ------------

def test_finalise_uses_direct_agreement_for_agreed_and_adjudicator_for_disagreed():
    merged = pd.DataFrame({
        "pair_id": ["p1", "p2"],
        "domain": ["circular_economy", "biomedical_diabetes_mellitus"],
        "string_a": ["a1", "a2"], "string_b": ["b1", "b2"],
        "annotator_1_label": ["match", "non-match"], "annotator_1_justification": ["", ""], "annotator_1_context_used": ["no", "no"],
        "annotator_2_label": ["match", "uncertain"], "annotator_2_justification": ["", ""], "annotator_2_context_used": ["no", "yes"],
        "agree": [True, False],
    })
    adjudication = pd.DataFrame({"pair_id": ["p2"], "adjudicated_label": ["match"], "adjudicator_notes": [""], "adjudicator_context_used": ["no"]})
    gold = finalise(merged, adjudication)
    p1, p2 = gold[gold["pair_id"] == "p1"].iloc[0], gold[gold["pair_id"] == "p2"].iloc[0]
    assert p1["final_gold_label"] == "match" and p1["gold_source"] == "direct_agreement"
    # p2's adjudicated label ("match") differs from BOTH annotators (non-match, uncertain) --
    # the "third label not proposed by either" case -- gold must still take it, never default to A1/A2.
    assert p2["final_gold_label"] == "match" and p2["gold_source"] == "adjudicated"


def test_finalise_never_uses_superseded_label_for_gold():
    merged = pd.DataFrame({
        "pair_id": ["p1"], "domain": ["biomedical_diabetes_mellitus"], "string_a": ["a"], "string_b": ["b"],
        "annotator_1_label": ["non-match"], "annotator_1_justification": [""], "annotator_1_context_used": ["no"],
        "annotator_2_label": ["uncertain"], "annotator_2_justification": [""], "annotator_2_context_used": ["no"],
        "agree": [False],
        "original_a2_diabetes_label": ["match"],  # the superseded, degenerate original run
    })
    adjudication = pd.DataFrame({"pair_id": ["p1"], "adjudicated_label": ["non-match"], "adjudicator_notes": [""], "adjudicator_context_used": ["no"]})
    gold = finalise(merged, adjudication)
    row = gold.iloc[0]
    assert row["final_gold_label"] == "non-match"  # adjudicated outcome, NOT the superseded "match"
    assert row["superseded_original_a2_diabetes_label"] == "match"  # preserved as audit-only


# -- Step 5: independent row-by-row verification (fail closed) --------------

def _synthetic_merged_and_adjudication(n_agree=3, n_disagree=2):
    rows = []
    for i in range(n_agree):
        rows.append({"pair_id": f"a{i}", "domain": "circular_economy", "string_a": f"x{i}", "string_b": f"y{i}",
                     "annotator_1_label": "match", "annotator_1_justification": "", "annotator_1_context_used": "no",
                     "annotator_2_label": "match", "annotator_2_justification": "", "annotator_2_context_used": "no", "agree": True})
    for i in range(n_disagree):
        rows.append({"pair_id": f"d{i}", "domain": "biomedical_diabetes_mellitus", "string_a": f"x{i}", "string_b": f"y{i}",
                     "annotator_1_label": "non-match", "annotator_1_justification": "", "annotator_1_context_used": "no",
                     "annotator_2_label": "uncertain", "annotator_2_justification": "", "annotator_2_context_used": "no", "agree": False})
    merged = pd.DataFrame(rows)
    adjudication = pd.DataFrame({"pair_id": [f"d{i}" for i in range(n_disagree)], "adjudicated_label": ["uncertain"] * n_disagree,
                                  "adjudicator_notes": [""] * n_disagree, "adjudicator_context_used": ["no"] * n_disagree})
    return merged, adjudication


_SYNTH_KWARGS = dict(expected_total=5, expected_direct_agreement=3, expected_adjudicated=2, expected_ce=3, expected_diabetes=2)


def test_verify_gold_row_by_row_passes_on_correct_gold():
    merged, adjudication = _synthetic_merged_and_adjudication()
    gold = finalise(merged, adjudication)
    result = verify_gold_row_by_row(gold, merged, adjudication, **_SYNTH_KWARGS)
    assert result["ok"]
    assert result["n_direct_agreement"] == 3 and result["n_adjudicated"] == 2


def test_verify_gold_row_by_row_fails_closed_on_tampered_gold():
    merged, adjudication = _synthetic_merged_and_adjudication()
    gold = finalise(merged, adjudication)
    tampered = gold.copy()
    tampered.loc[tampered["pair_id"] == "d0", "final_gold_label"] = "match"  # silently overwritten with A1/A2-style default
    result = verify_gold_row_by_row(tampered, merged, adjudication, **_SYNTH_KWARGS)
    assert not result["ok"]
    assert any("d0" in issue for issue in result["issues"])


def test_verify_gold_row_by_row_fails_closed_on_wrong_gold_source():
    merged, adjudication = _synthetic_merged_and_adjudication()
    gold = finalise(merged, adjudication)
    tampered = gold.copy()
    tampered.loc[tampered["pair_id"] == "a0", "gold_source"] = "adjudicated"  # agreement row mislabelled
    result = verify_gold_row_by_row(tampered, merged, adjudication, **_SYNTH_KWARGS)
    assert not result["ok"]


# -- Step 6: distributions ----------------------------------------------------

def test_gold_distributions_sum_correctly():
    merged, adjudication = _synthetic_merged_and_adjudication(n_agree=3, n_disagree=2)
    gold = finalise(merged, adjudication)
    d = gold_distributions(gold)
    total = d["overall"]["match"]["count"] + d["overall"]["non-match"]["count"] + d["overall"]["uncertain"]["count"]
    assert total == d["overall"]["n"] == 5


# -- Step 8: adjudication outcome analysis (no identity leak) ---------------

def test_adjudication_outcome_analysis_detects_third_label_selection():
    merged = pd.DataFrame({
        "pair_id": ["p1"], "domain": ["circular_economy"],
        "disagreement_type": ["match vs non-match"],
    })
    adjudication = pd.DataFrame({
        "pair_id": ["p1"], "decision_A": ["match"], "decision_B": ["non-match"],
        "adjudicated_label": ["uncertain"], "adjudicator_context_used": ["yes"],
    })
    out = adjudication_outcome_analysis(adjudication, merged)
    assert out["selection_kind_counts"] == {"selected_third_label_not_proposed": 1}
    assert out["adjudicator_context_use_count"] == 1
    # no annotator-identity field anywhere in the output
    assert "annotator_1" not in str(out) and "annotator_2" not in str(out)


def test_adjudication_outcome_analysis_detects_one_of_two_selection():
    merged = pd.DataFrame({"pair_id": ["p1"], "domain": ["circular_economy"], "disagreement_type": ["match vs non-match"]})
    adjudication = pd.DataFrame({"pair_id": ["p1"], "decision_A": ["match"], "decision_B": ["non-match"],
                                  "adjudicated_label": ["match"], "adjudicator_context_used": ["no"]})
    out = adjudication_outcome_analysis(adjudication, merged)
    assert out["selection_kind_counts"] == {"selected_one_of_the_two_proposed": 1}


# -- Step 9: context-use summary ---------------------------------------------

def test_context_use_summary_categories():
    merged, adjudication = _synthetic_merged_and_adjudication(n_agree=2, n_disagree=2)
    merged.loc[merged["pair_id"] == "a0", "annotator_1_context_used"] = "yes"
    adjudication.loc[adjudication["pair_id"] == "d0", "adjudicator_context_used"] = "yes"
    gold = finalise(merged, adjudication)
    c = context_use_summary(gold)
    assert c["gold_from_direct_agreement_with_at_least_one_context"] == 1
    assert c["gold_from_direct_agreement_without_either_context"] == 1
    assert c["gold_from_adjudication_with_adjudicator_context"] == 1
    assert c["gold_from_adjudication_without_adjudicator_context"] == 1


# -- Step 10: CONSORT flow ----------------------------------------------------

def test_human_annotation_flow_fixed_counts():
    flow = human_annotation_flow()
    assert flow["direct_agreements"] + flow["disagreements_requiring_adjudication"] == flow["final_gold"] == 900
    assert flow["partition"]["circular_economy"] + flow["partition"]["biomedical_diabetes_mellitus"] == 900


# -- Step 7: stratum quotas (frozen sampling design) -------------------------

def test_frozen_stratum_quotas_sum_to_domain_totals():
    assert sum(FROZEN_STRATUM_QUOTAS["circular_economy"].values()) == 400
    assert sum(FROZEN_STRATUM_QUOTAS["biomedical_diabetes_mellitus"].values()) == 500


# -- Step 14: held-out manifest ------------------------------------------------

def test_heldout_totals_sum_to_1049_and_development_kept_separate():
    total = sum(d["n"] for d in HELD_OUT_DATASETS.values())
    assert total == 1049
    assert "legacy_ce_development" not in HELD_OUT_DATASETS
    assert DEVELOPMENT_SET["legacy_ce_development"]["n"] == 351


# -- Step 15: H3 package unchanged, no labels created ------------------------

def test_h3_expected_counts_match_frozen_manifest_composition():
    assert H3_EXPECTED["annotator_1_ce_rows"] + H3_EXPECTED["annotator_1_diabetes_rows"] == H3_EXPECTED["annotator_1_total_rows"] == 6185
    assert H3_EXPECTED["annotator_2_outside_pool_rows"] + H3_EXPECTED["annotator_2_audit_sample_rows"] == H3_EXPECTED["annotator_2_total_rows"] == 2066


def test_h3_retrieval_files_have_zero_filled_labels_if_present():
    for name in ("03_ANNOTATOR_1_RETRIEVAL.xlsx", "04_ANNOTATOR_2_RETRIEVAL.xlsx"):
        path = PKG_DIR / name
        if not path.exists():
            pytest.skip(f"{name} not present in this environment")
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
        for sheet_name, df in sheets.items():
            if sheet_name == "Instructions" or "label" not in df.columns:
                continue
            assert df["label"].notna().sum() == 0, f"{name}/{sheet_name} has non-blank retrieval labels -- H3 must not have started"


def test_no_retrieval_working_or_completed_files_exist():
    matches = list(PKG_DIR.glob("*RETRIEVAL_WORKING*")) + list(PKG_DIR.glob("*RETRIEVAL_COMPLETED*"))
    assert matches == []


# -- real (never-modified) restricted evidence: hashes + structure ----------

def test_original_evidence_files_unchanged_by_this_task():
    expected = {
        "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx": "92aadca4785b21e2ce7ffaacd3754f8f7e43010fd7d2c25444029e6370f08759",
        "ANNOTATOR_2_PRIMARY_COMPLETED.xlsx": "760ec6b4c7395cce95ca2e4b07c3bbf97f92a4d9f1a40f15f8a16fc7f6228bdf",
    }
    for name, expected_hash in expected.items():
        path = PKG_DIR / name
        if not path.exists():
            pytest.skip(f"{name} not present in this environment")
        assert _sha256(path) == expected_hash

    corrected_adj_source = PKG_DIR / "h2" / "corrected" / "PRIMARY_ADJUDICATION_CORRECTED.xlsx"
    if corrected_adj_source.exists():
        assert _sha256(corrected_adj_source) == "849ff01420cd46cadcd77270782df16b10677df4e6f128be1e9ba7ccc7589819"


def test_gold_files_exist_and_have_900_rows_if_present():
    gold_dir = PKG_DIR / "gold"
    xlsx = gold_dir / "PRIMARY_GOLD_900_FINAL.xlsx"
    csv_path = gold_dir / "PRIMARY_GOLD_900_FINAL.csv"
    if not (xlsx.exists() and csv_path.exists()):
        pytest.skip("final gold files not present in this environment")
    df = pd.read_csv(csv_path)
    assert len(df) == 900
    assert df["pair_id"].nunique() == 900
    assert df["final_gold_label"].isin(["match", "non-match", "uncertain"]).all()
    assert set(df["gold_source"]) <= {"direct_agreement", "adjudicated"}


def test_gold_directory_is_gitignored():
    worktree = Path(__file__).resolve().parents[2]
    if not (worktree / ".git").exists():
        pytest.skip("requires a git checkout to verify gitignore coverage via `git check-ignore`; not applicable to a plain source archive/tarball extraction")
    proc = subprocess.run(
        ["git", "check-ignore", "-v", "strengthening/restricted_local/human_annotation/v1/gold/probe.xlsx"],
        cwd=worktree, capture_output=True, text=True,
    )
    assert proc.returncode == 0
