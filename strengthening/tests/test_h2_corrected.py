"""Synthetic-data tests for the corrected H2 pipeline (post diabetes
re-annotation): diabetes re-annotation validation, corrected Annotator-2
composition, CE-unchanged guard, corrected alignment/agreement, the
original-vs-redo audit, per-row A/B anonymisation, the corrected
adjudicator GUI's filename-prefix path resolution, and finalise_primary_
gold's new provenance columns. Never touches real annotator data except
for hash/gitignore/launcher-content checks against the real, never-
modified restricted package."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook

from strengthening.human_annotation.finalise_primary_gold import finalise
from strengthening.human_annotation.h2_build_corrected_adjudication_package import (
    build_adjudication_dataframe_per_row,
    choose_ab_mapping_per_row,
)
from strengthening.human_annotation.h2_build_corrected_reports import _build_old_vs_new_audit
from strengthening.human_annotation.h2_diabetes_reannotation_quality_check import analyze_session
from strengthening.human_annotation.h2_recompute_with_diabetes_reannotation import build_effective_annotator_2
from strengthening.human_annotation.h2_validate_diabetes_reannotation import (
    ReannotationValidationError,
    validate_diabetes_reannotation,
)
from strengthening.human_annotation.gui.adjudication_main import _resolve_paths

PKG_DIR = Path(__file__).resolve().parents[1] / "restricted_local" / "human_annotation" / "v1"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# -- Step 2: diabetes re-annotation validation ------------------------------

def _write_reannotation_workbook(path, diabetes_rows, ce_rows=()):
    wb = Workbook()
    wb.remove(wb.active)
    cols = ["pair_id", "domain", "string_a", "string_b", "label", "justification", "context_used"]
    for name, subset in (("Circular_Economy_400", ce_rows), ("Diabetes_500", diabetes_rows)):
        ws = wb.create_sheet(name)
        ws.append(cols)
        for r in subset:
            ws.append(list(r))
    wb.save(path)


CANONICAL_BIO = pd.DataFrame(
    [
        {"pair_id": "d1", "domain": "biomedical_diabetes_mellitus", "string_a": "a1", "string_b": "b1"},
        {"pair_id": "d2", "domain": "biomedical_diabetes_mellitus", "string_a": "a2", "string_b": "b2"},
    ]
)
VALID_ROWS = [
    ("d1", "biomedical_diabetes_mellitus", "a1", "b1", "non-match", "", "no"),
    ("d2", "biomedical_diabetes_mellitus", "a2", "b2", "match", "", "yes"),
]


def test_validate_diabetes_reannotation_passes_on_well_formed_workbook(tmp_path):
    p = tmp_path / "reann.xlsx"
    _write_reannotation_workbook(p, VALID_ROWS)
    result = validate_diabetes_reannotation(p, CANONICAL_BIO, expected_rows=2)
    assert result.ok
    assert result.row_count == 2
    assert result.missing_labels == 0


def test_validate_diabetes_reannotation_detects_wrong_row_count(tmp_path):
    p = tmp_path / "reann.xlsx"
    _write_reannotation_workbook(p, VALID_ROWS[:1])
    result = validate_diabetes_reannotation(p, CANONICAL_BIO, expected_rows=2)
    assert not result.ok
    assert any("expected 2" in i for i in result.issues)


def test_validate_diabetes_reannotation_detects_missing_label(tmp_path):
    rows = list(VALID_ROWS)
    rows[0] = (rows[0][0], rows[0][1], rows[0][2], rows[0][3], "", "", "no")
    p = tmp_path / "reann.xlsx"
    _write_reannotation_workbook(p, rows)
    result = validate_diabetes_reannotation(p, CANONICAL_BIO, expected_rows=2)
    assert not result.ok
    assert result.missing_labels == 1


def test_validate_diabetes_reannotation_detects_changed_string(tmp_path):
    rows = list(VALID_ROWS)
    rows[0] = (rows[0][0], rows[0][1], "CHANGED", rows[0][3], rows[0][4], "", "no")
    p = tmp_path / "reann.xlsx"
    _write_reannotation_workbook(p, rows)
    result = validate_diabetes_reannotation(p, CANONICAL_BIO, expected_rows=2)
    assert not result.ok
    assert "d1" in result.changed_strings


def test_validate_diabetes_reannotation_detects_duplicate_pair_id(tmp_path):
    rows = list(VALID_ROWS) + [VALID_ROWS[0]]
    p = tmp_path / "reann.xlsx"
    _write_reannotation_workbook(p, rows)
    result = validate_diabetes_reannotation(p, CANONICAL_BIO, expected_rows=2)
    assert not result.ok
    assert "d1" in result.duplicate_pair_ids


def test_validate_diabetes_reannotation_detects_forbidden_column():
    # simulate what load_workbook_data_tabs would hand back if a prior-label
    # or system-metadata column had leaked into the workbook
    import strengthening.human_annotation.h2_validate_diabetes_reannotation as mod

    df = pd.DataFrame(
        {
            "pair_id": ["d1"], "domain": ["biomedical_diabetes_mellitus"], "string_a": ["a1"], "string_b": ["b1"],
            "label": ["match"], "justification": [""], "context_used": ["no"],
            "annotator_1_label": ["match"],  # forbidden: A1 label must never appear here
        }
    )
    forbidden = [c for c in df.columns if c not in mod.REQUIRED_COLS and any(t in c.lower() for t in mod.FORBIDDEN_COLUMN_TERMS)]
    assert forbidden == ["annotator_1_label"]


def test_validate_diabetes_reannotation_missing_file_raises(tmp_path):
    with pytest.raises(ReannotationValidationError):
        validate_diabetes_reannotation(tmp_path / "nope.xlsx", CANONICAL_BIO)


# -- Step 3: session quality check (synthetic audit log) --------------------

def test_analyze_session_detects_degenerate_single_label():
    rows = [
        {"timestamp": f"2026-09-08T10:00:{i:02d}+00:00", "pair_id": f"p{i}", "old_label": "", "new_label": "match", "context_used": "no", "action": "label"}
        for i in range(5)
    ]
    s = analyze_session(rows)
    assert s["label_distribution_is_degenerate_single_class"]
    assert s["label_distribution"] == {"match": 5}


def test_analyze_session_varied_labels_not_degenerate():
    labels = ["match", "non-match", "uncertain", "non-match", "match"]
    rows = [
        {"timestamp": f"2026-09-08T10:00:{i:02d}+00:00", "pair_id": f"p{i}", "old_label": "", "new_label": lbl, "context_used": "no", "action": "label"}
        for i, lbl in enumerate(labels)
    ]
    s = analyze_session(rows)
    assert not s["label_distribution_is_degenerate_single_class"]
    assert s["relabel_count"] == 0
    assert s["skip_count"] == 0


def test_analyze_session_flags_stuck_key_signature():
    rows = [
        {"timestamp": "2026-09-08T10:00:00.000000+00:00", "pair_id": "p0", "old_label": "", "new_label": "match", "context_used": "no", "action": "label"},
        {"timestamp": "2026-09-08T10:00:00.010000+00:00", "pair_id": "p1", "old_label": "", "new_label": "match", "context_used": "no", "action": "label"},
    ]
    s = analyze_session(rows)
    assert s["evidence_of_stuck_key_or_autorepeat"]


def test_analyze_session_counts_relabels_correctly():
    rows = [
        {"timestamp": "2026-09-08T10:00:00+00:00", "pair_id": "p0", "old_label": "", "new_label": "match", "context_used": "no", "action": "label"},
        {"timestamp": "2026-09-08T10:00:05+00:00", "pair_id": "p0", "old_label": "match", "new_label": "non-match", "context_used": "no", "action": "relabel"},
    ]
    s = analyze_session(rows)
    assert s["relabel_count"] == 1
    assert s["n_distinct_pairs_decided"] == 1
    assert s["label_distribution"] == {"non-match": 1}  # final label only


# -- Step 4: corrected Annotator-2 composition (CE untouched) ---------------

def test_corrected_composition_preserves_ce_and_uses_reannotation_diabetes():
    ann2_original = pd.DataFrame(
        {
            "pair_id": ["ce1", "ce2", "bio1"],
            "domain": ["circular_economy", "circular_economy", "biomedical_diabetes_mellitus"],
            "string_a": ["a1", "a2", "b1"], "string_b": ["x1", "x2", "y1"],
            "label": ["match", "non-match", "match"], "justification": ["", "", ""], "context_used": ["no", "no", "no"],
        }
    )
    diabetes_reannotation = pd.DataFrame(
        {
            "pair_id": ["bio1"], "domain": ["biomedical_diabetes_mellitus"],
            "string_a": ["b1"], "string_b": ["y1"], "label": ["non-match"], "justification": [""], "context_used": ["no"],
        }
    )
    effective = build_effective_annotator_2(ann2_original, diabetes_reannotation, expected_total=3)
    effective["annotator_2_annotation_source"] = effective["domain"].map(
        {"circular_economy": "original_A2_H1", "biomedical_diabetes_mellitus": "A2_diabetes_reannotation"}
    )
    ce = effective[effective["domain"] == "circular_economy"].sort_values("pair_id")
    assert list(ce["label"]) == ["match", "non-match"]
    assert (ce["annotator_2_annotation_source"] == "original_A2_H1").all()
    bio = effective[effective["domain"] == "biomedical_diabetes_mellitus"]
    assert bio.iloc[0]["annotator_2_annotation_source"] == "A2_diabetes_reannotation"
    assert bio.iloc[0]["label"] == "non-match"


# -- original vs re-annotation audit -----------------------------------------

def test_build_old_vs_new_audit_counts_changed_labels():
    old_report = {
        "overall": {"n": 4, "agreements": 2, "disagreements": 2, "raw_agreement_proportion": 0.5, "cohens_kappa": 0.1},
        "biomedical_diabetes_mellitus": {
            "n": 2, "agreements": 1, "disagreements": 1, "raw_agreement_proportion": 0.5, "cohens_kappa": 0.0,
            "annotator_2_label_distribution": {"match": 2},
        },
    }
    new_report = {
        "overall": {"n": 4, "agreements": 3, "disagreements": 1, "raw_agreement_proportion": 0.75, "cohens_kappa": 0.4},
        "biomedical_diabetes_mellitus": {
            "n": 2, "agreements": 2, "disagreements": 0, "raw_agreement_proportion": 1.0, "cohens_kappa": 1.0,
            "annotator_2_label_distribution": {"match": 1, "non-match": 1},
        },
    }
    ann2_original = pd.DataFrame(
        {"pair_id": ["bio1", "bio2"], "domain": ["biomedical_diabetes_mellitus"] * 2, "label": ["match", "match"]}
    )
    diabetes_reannotation = pd.DataFrame({"pair_id": ["bio1", "bio2"], "label": ["match", "non-match"]})
    audit = _build_old_vs_new_audit(old_report, new_report, ann2_original, diabetes_reannotation)
    assert audit["n_a2_diabetes_labels_changed_between_original_and_redo"] == 1
    assert audit["n_a2_diabetes_common_pair_ids_compared"] == 2
    assert audit["old_diabetes"]["cohens_kappa"] == 0.0
    assert audit["corrected_diabetes"]["cohens_kappa"] == 1.0


# -- Step 9: per-row A/B anonymisation ---------------------------------------

def test_choose_ab_mapping_per_row_is_deterministic_given_seed():
    ids = [f"p{i}" for i in range(50)]
    m1 = choose_ab_mapping_per_row(ids, seed=123)
    m2 = choose_ab_mapping_per_row(ids, seed=123)
    assert m1 == m2


def test_choose_ab_mapping_per_row_is_not_globally_fixed():
    ids = [f"p{i}" for i in range(50)]
    mapping = choose_ab_mapping_per_row(ids, seed=99)
    orientations = {m["annotator_1"] for m in mapping.values()}
    assert orientations == {"A", "B"}  # both orientations actually occur -- not one fixed global mapping


def test_choose_ab_mapping_per_row_is_roughly_balanced():
    ids = [f"p{i}" for i in range(2000)]
    mapping = choose_ab_mapping_per_row(ids, seed=7)
    n_a = sum(1 for m in mapping.values() if m["annotator_1"] == "A")
    assert 0.40 < n_a / len(mapping) < 0.60


def test_build_adjudication_dataframe_per_row_pairs_fields_correctly():
    merged = pd.DataFrame(
        {
            "pair_id": ["p1", "p2"], "domain": ["circular_economy"] * 2, "string_a": ["a1", "a2"], "string_b": ["b1", "b2"],
            "annotator_1_label": ["match", "non-match"], "annotator_1_justification": ["j1", "j2"], "annotator_1_context_used": ["no", "no"],
            "annotator_2_label": ["non-match", "match"], "annotator_2_justification": ["k1", "k2"], "annotator_2_context_used": ["yes", "no"],
            "agree": [False, False],
        }
    )
    row_mapping = {"p1": {"annotator_1": "A", "annotator_2": "B"}, "p2": {"annotator_1": "B", "annotator_2": "A"}}
    adj = build_adjudication_dataframe_per_row(merged, row_mapping)
    assert len(adj) == 2
    r1 = adj[adj["pair_id"] == "p1"].iloc[0]
    assert r1["decision_A"] == "match" and r1["decision_B"] == "non-match"
    assert r1["justification_A"] == "j1" and r1["justification_B"] == "k1"
    r2 = adj[adj["pair_id"] == "p2"].iloc[0]
    # p2 has the REVERSED orientation -- annotator_1 (non-match) is now B
    assert r2["decision_A"] == "match" and r2["decision_B"] == "non-match"
    assert (adj["adjudicated_label"] == "").all()


def test_build_adjudication_dataframe_per_row_only_includes_disagreements():
    merged = pd.DataFrame(
        {
            "pair_id": ["p1", "p2"], "domain": ["circular_economy"] * 2, "string_a": ["a1", "a2"], "string_b": ["b1", "b2"],
            "annotator_1_label": ["match", "match"], "annotator_1_justification": ["", ""], "annotator_1_context_used": ["no", "no"],
            "annotator_2_label": ["match", "non-match"], "annotator_2_justification": ["", ""], "annotator_2_context_used": ["no", "no"],
            "agree": [True, False],
        }
    )
    row_mapping = {"p2": {"annotator_1": "A", "annotator_2": "B"}}
    adj = build_adjudication_dataframe_per_row(merged, row_mapping)
    assert len(adj) == 1
    assert adj.iloc[0]["pair_id"] == "p2"


# -- corrected adjudicator GUI: filename-prefix path resolution -------------

def test_resolve_paths_default_prefix_matches_original_filenames(tmp_path):
    working, completed, audit = _resolve_paths(tmp_path, "PRIMARY_ADJUDICATION")
    assert working.name == "PRIMARY_ADJUDICATION_WORKING.xlsx"
    assert completed.name == "PRIMARY_ADJUDICATION_COMPLETED.xlsx"
    assert audit.name == "PRIMARY_ADJUDICATION_audit_log.csv"


def test_resolve_paths_corrected_prefix_produces_distinct_filenames(tmp_path):
    working, completed, audit = _resolve_paths(tmp_path, "PRIMARY_ADJUDICATION_CORRECTED")
    assert working.name == "PRIMARY_ADJUDICATION_CORRECTED_WORKING.xlsx"
    assert completed.name == "PRIMARY_ADJUDICATION_CORRECTED_COMPLETED.xlsx"
    assert audit.name == "PRIMARY_ADJUDICATION_CORRECTED_audit_log.csv"


# -- finalise_primary_gold: new provenance columns (synthetic only) --------

def test_finalise_carries_annotator_2_source_and_superseded_label_without_affecting_gold():
    merged_900 = pd.DataFrame(
        {
            "pair_id": ["p1", "p2"],
            "domain": ["biomedical_diabetes_mellitus", "biomedical_diabetes_mellitus"],
            "string_a": ["a1", "a2"], "string_b": ["b1", "b2"],
            "annotator_1_label": ["match", "non-match"], "annotator_1_justification": ["", ""], "annotator_1_context_used": ["no", "no"],
            "annotator_2_label": ["match", "uncertain"], "annotator_2_justification": ["", ""], "annotator_2_context_used": ["no", "no"],
            "agree": [True, False],
            "annotator_2_annotation_source": ["A2_diabetes_reannotation", "A2_diabetes_reannotation"],
            "original_a2_diabetes_label": ["match", "match"],  # the superseded, degenerate original run
        }
    )
    adjudication_completed = pd.DataFrame(
        {"pair_id": ["p2"], "adjudicated_label": ["uncertain"], "adjudicator_notes": [""], "adjudicator_context_used": ["no"]}
    )
    gold = finalise(merged_900, adjudication_completed)
    p1 = gold[gold["pair_id"] == "p1"].iloc[0]
    p2 = gold[gold["pair_id"] == "p2"].iloc[0]
    assert p1["final_gold_label"] == "match" and p1["gold_source"] == "direct_agreement"
    assert p1["annotator_2_annotation_source"] == "A2_diabetes_reannotation"
    assert p1["superseded_original_a2_diabetes_label"] == "match"
    assert p2["final_gold_label"] == "uncertain"  # adjudicated, NOT the superseded original label
    assert p2["superseded_original_a2_diabetes_label"] == "match"  # preserved as audit-only provenance


def test_finalise_backward_compatible_when_provenance_columns_absent():
    # the ORIGINAL (pre-correction) H1 merge never had these columns --
    # finalise() must still work exactly as before.
    merged_900 = pd.DataFrame(
        {
            "pair_id": ["p1"], "domain": ["circular_economy"], "string_a": ["a"], "string_b": ["b"],
            "annotator_1_label": ["match"], "annotator_1_justification": [""], "annotator_1_context_used": ["no"],
            "annotator_2_label": ["match"], "annotator_2_justification": [""], "annotator_2_context_used": ["no"],
            "agree": [True],
        }
    )
    adjudication_completed = pd.DataFrame({"pair_id": [], "adjudicated_label": [], "adjudicator_notes": [], "adjudicator_context_used": []})
    gold = finalise(merged_900, adjudication_completed)
    assert gold.iloc[0]["annotator_2_annotation_source"] == ""
    assert gold.iloc[0]["superseded_original_a2_diabetes_label"] == ""


# -- real (never-modified) restricted evidence: hashes + structure ----------

def test_original_h1_and_reannotation_files_unchanged_by_this_task():
    expected = {
        "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx": "92aadca4785b21e2ce7ffaacd3754f8f7e43010fd7d2c25444029e6370f08759",
        "ANNOTATOR_2_PRIMARY_COMPLETED.xlsx": "760ec6b4c7395cce95ca2e4b07c3bbf97f92a4d9f1a40f15f8a16fc7f6228bdf",
    }
    for name, expected_hash in expected.items():
        path = PKG_DIR / name
        if not path.exists():
            pytest.skip(f"{name} not present in this environment")
        assert _sha256(path) == expected_hash, f"{name} hash changed -- original H1 evidence must never be modified"

    reann = PKG_DIR / "h2" / "diabetes_reannotation" / "DIABETES_REANNOTATION_ANNOTATOR_2_COMPLETED.xlsx"
    if reann.exists():
        assert _sha256(reann) == "b1c59782204aeaa3f0f3aa64005e3c7b368e45e58509553bce0a120f8cd5c8cd"

    old_adjudication = PKG_DIR / "h2" / "PRIMARY_ADJUDICATION.xlsx"
    if old_adjudication.exists():
        assert _sha256(old_adjudication) == "14a57b3d123b80f3c03036626464802d0b72a5ca7596db5912d5287e86b6022a"


def test_corrected_adjudication_package_all_blank_if_present():
    path = PKG_DIR / "h2" / "corrected" / "PRIMARY_ADJUDICATION_CORRECTED.xlsx"
    if not path.exists():
        pytest.skip("corrected adjudication package not present in this environment")
    wb = load_workbook(path, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header = rows[0]
    idx = {c: i for i, c in enumerate(header)}
    for r in rows[1:]:
        assert r[idx["adjudicated_label"]] in (None, "")


def test_corrected_launcher_bat_uses_the_fixed_pattern_and_filename_prefix():
    path = PKG_DIR / "h2" / "corrected" / "START_PRIMARY_ADJUDICATOR_CORRECTED.bat"
    if not path.exists():
        pytest.skip("corrected launcher not present in this environment")
    text = path.read_text(encoding="utf-8")
    assert 'if "%SCRIPT_DIR:~-1%"=="\\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"' in text
    assert 'start "" /min python.exe' in text
    assert "goto :launch_pythonw" in text
    assert "--filename-prefix PRIMARY_ADJUDICATION_CORRECTED" in text
    assert "PRIMARY_ADJUDICATION_CORRECTED.xlsx" in text


def test_corrected_restricted_directory_is_gitignored():
    worktree = Path(__file__).resolve().parents[2]
    if not (worktree / ".git").exists():
        pytest.skip("requires a git checkout to verify gitignore coverage via `git check-ignore`; not applicable to a plain source archive/tarball extraction")
    proc = subprocess.run(
        ["git", "check-ignore", "-v", "strengthening/restricted_local/human_annotation/v1/h2/corrected/probe.xlsx"],
        cwd=worktree, capture_output=True, text=True,
    )
    assert proc.returncode == 0
