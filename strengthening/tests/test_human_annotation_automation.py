"""Synthetic-data tests for the post-annotation automation scripts.
Nothing here touches real annotator output -- all data is hand-
constructed and written to temporary files."""
from __future__ import annotations

import pandas as pd
import pytest
from openpyxl import Workbook

from strengthening.human_annotation.build_primary_adjudication_package import build as build_primary_adj
from strengthening.human_annotation.build_retrieval_adjudication_package import build as build_retrieval_adj
from strengthening.human_annotation.common import cohens_kappa, raw_agreement
from strengthening.human_annotation.evaluate_annotation_agreement import evaluate as evaluate_agreement
from strengthening.human_annotation.evaluate_retrieval_audit_escalation import evaluate_domain, select_additional_sample
from strengthening.human_annotation.merge_primary_annotations import merge as merge_primary
from strengthening.human_annotation.merge_retrieval_annotations import merge as merge_retrieval
from strengthening.human_annotation.validate_completed_workbooks import validate


def _write_workbook(path, sheets: dict[str, list[dict]]):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        if not rows:
            continue
        cols = list(rows[0].keys())
        ws.append(cols)
        for r in rows:
            ws.append([r[c] for c in cols])
    wb.save(path)


@pytest.fixture
def primary_source_csv(tmp_path):
    df = pd.DataFrame(
        {
            "pair_id": ["p1", "p2", "p3"],
            "domain": ["circular_economy"] * 3,
            "string_a": ["circular economy", "recycling", "waste"],
            "string_b": ["circular  economy", "upcycling", "trash"],
        }
    )
    path = tmp_path / "source.csv"
    df.to_csv(path, index=False)
    return path


def test_validate_completed_workbook_detects_missing_and_bad_label(tmp_path, primary_source_csv):
    good = tmp_path / "good.xlsx"
    _write_workbook(
        good,
        {
            "Data": [
                {"row_number": 1, "pair_id": "p1", "domain": "circular_economy", "string_a": "circular economy", "string_b": "circular  economy", "label": "match", "justification": "same", "context_used": "no"},
                {"row_number": 2, "pair_id": "p2", "domain": "circular_economy", "string_a": "recycling", "string_b": "upcycling", "label": "non-match", "justification": "different", "context_used": "no"},
                {"row_number": 3, "pair_id": "p3", "domain": "circular_economy", "string_a": "waste", "string_b": "trash", "label": "uncertain", "justification": "unsure", "context_used": "yes"},
            ]
        },
    )
    result = validate(good, primary_source_csv, "pair_id", ["string_a", "string_b"])
    assert result["valid"], result["issues"]
    assert result["rows_expected"] == 3
    assert result["rows_with_a_label"] == 3

    bad = tmp_path / "bad.xlsx"
    _write_workbook(
        bad,
        {
            "Data": [
                {"row_number": 1, "pair_id": "p1", "domain": "circular_economy", "string_a": "circular economy", "string_b": "circular  economy", "label": "definitely-match", "justification": "", "context_used": "no"},
                {"row_number": 2, "pair_id": "p2", "domain": "circular_economy", "string_a": "RECYCLING-CHANGED", "string_b": "upcycling", "label": "non-match", "justification": "", "context_used": "no"},
            ]
        },
    )
    result_bad = validate(bad, primary_source_csv, "pair_id", ["string_a", "string_b"])
    assert not result_bad["valid"]
    assert any("p3" in issue for issue in result_bad["issues"])  # missing row
    assert any("changed" in issue for issue in result_bad["issues"])  # string changed
    assert any("outside" in issue for issue in result_bad["issues"])  # bad label


def test_merge_primary_annotations_aligns_by_pair_id_regardless_of_order(tmp_path):
    ann1 = tmp_path / "ann1.xlsx"
    ann2 = tmp_path / "ann2.xlsx"
    _write_workbook(ann1, {"Data": [
        {"pair_id": "p1", "domain": "d", "string_a": "a1", "string_b": "b1", "label": "match", "justification": "j1", "context_used": "no"},
        {"pair_id": "p2", "domain": "d", "string_a": "a2", "string_b": "b2", "label": "non-match", "justification": "j2", "context_used": "no"},
    ]})
    _write_workbook(ann2, {"Data": [
        {"pair_id": "p2", "domain": "d", "string_a": "a2", "string_b": "b2", "label": "uncertain", "justification": "j2b", "context_used": "yes"},
        {"pair_id": "p1", "domain": "d", "string_a": "a1", "string_b": "b1", "label": "match", "justification": "j1b", "context_used": "no"},
    ]})
    merged = merge_primary(ann1, ann2)
    assert list(merged["pair_id"]) == ["p1", "p2"]
    row_p2 = merged[merged["pair_id"] == "p2"].iloc[0]
    assert row_p2["annotator_1_label"] == "non-match"
    assert row_p2["annotator_2_label"] == "uncertain"
    assert not row_p2["agree"]
    assert merged[merged["pair_id"] == "p1"].iloc[0]["agree"]


def test_merge_primary_annotations_raises_on_mismatched_id_sets(tmp_path):
    ann1 = tmp_path / "ann1.xlsx"
    ann2 = tmp_path / "ann2.xlsx"
    _write_workbook(ann1, {"Data": [{"pair_id": "p1", "domain": "d", "string_a": "a", "string_b": "b", "label": "match", "justification": "", "context_used": "no"}]})
    _write_workbook(ann2, {"Data": [{"pair_id": "p_renamed", "domain": "d", "string_a": "a", "string_b": "b", "label": "match", "justification": "", "context_used": "no"}]})
    with pytest.raises(ValueError):
        merge_primary(ann1, ann2)


def test_build_primary_adjudication_package_only_disagreements():
    merged = pd.DataFrame(
        {
            "pair_id": ["p1", "p2", "p3"],
            "domain": ["d"] * 3,
            "string_a": ["a1", "a2", "a3"],
            "string_b": ["b1", "b2", "b3"],
            "annotator_1_label": ["match", "non-match", "uncertain"],
            "annotator_1_justification": ["", "", ""],
            "annotator_2_label": ["match", "match", "uncertain"],
            "annotator_2_justification": ["", "", ""],
            "agree": [True, False, True],
        }
    )
    pkg = build_primary_adj(merged)
    assert list(pkg["pair_id"]) == ["p2"]
    assert (pkg["adjudicated_label"] == "").all()


def test_evaluate_agreement_matches_hand_computation():
    merged = pd.DataFrame(
        {
            "annotator_1_label": ["match", "match", "non-match", "uncertain"],
            "annotator_2_label": ["match", "non-match", "non-match", "uncertain"],
        }
    )
    result = evaluate_agreement(merged)
    assert result["n_double_coded"] == 4
    assert result["raw_agreement"] == 0.75
    assert result["n_disagreements"] == 1
    expected_kappa = cohens_kappa(merged["annotator_1_label"].tolist(), merged["annotator_2_label"].tolist(), classes=["match", "non-match", "uncertain"])
    assert result["cohens_kappa"] == pytest.approx(expected_kappa)


def test_cohens_kappa_perfect_agreement_is_one():
    labels = ["match", "non-match", "uncertain", "match", "non-match"]
    assert cohens_kappa(labels, labels) == pytest.approx(1.0)


def test_raw_agreement_hand_computed():
    assert raw_agreement(["match", "match", "non-match"], ["match", "non-match", "non-match"]) == pytest.approx(2 / 3)


def test_merge_retrieval_annotations_keeps_singly_coded_rows(tmp_path):
    ann1 = tmp_path / "r1.xlsx"
    ann2 = tmp_path / "r2.xlsx"
    _write_workbook(ann1, {"Data": [
        {"retrieval_pair_id": "r1", "domain": "d", "seed_string": "s1", "candidate_string": "c1", "label": "match", "justification": "", "context_used": "no"},
        {"retrieval_pair_id": "r2", "domain": "d", "seed_string": "s2", "candidate_string": "c2", "label": "non-match", "justification": "", "context_used": "no"},
    ]})
    _write_workbook(ann2, {"Data": [
        {"retrieval_pair_id": "r1", "domain": "d", "seed_string": "s1", "candidate_string": "c1", "label": "match", "justification": "", "context_used": "no"},
    ]})
    merged = merge_retrieval(ann1, ann2)
    r1_row = merged[merged["retrieval_pair_id"] == "r1"].iloc[0]
    r2_row = merged[merged["retrieval_pair_id"] == "r2"].iloc[0]
    assert r1_row["double_coded"] and r1_row["agree"]
    assert not r2_row["double_coded"]


def test_build_retrieval_adjudication_package_restricted_to_double_coded():
    merged = pd.DataFrame(
        {
            "retrieval_pair_id": ["r1", "r2", "r3"],
            "domain": ["d"] * 3,
            "seed_string": ["s1", "s2", "s3"],
            "candidate_string": ["c1", "c2", "c3"],
            "annotator_1_label": ["match", "non-match", "match"],
            "annotator_1_justification": ["", "", ""],
            "annotator_2_label": ["non-match", None, "match"],
            "annotator_2_justification": ["", None, ""],
            "double_coded": [True, False, True],
            "agree": [False, False, True],
        }
    )
    pkg = build_retrieval_adj(merged)
    assert list(pkg["retrieval_pair_id"]) == ["r1"]  # r2 not double-coded (excluded), r3 agrees (excluded)


def test_escalation_positive_miss_rate_hand_computed():
    # 5 in-pool double-coded rows, one domain, all outside_pool_sample=False.
    merged = pd.DataFrame(
        {
            "retrieval_pair_id": ["a", "b", "c", "d", "e"],
            "domain": ["circular_economy"] * 5,
            "annotator_1_label": ["non-match", "uncertain", "match", "match", "non-match"],
            "annotator_2_label": ["match", "match", "match", "non-match", "non-match"],
            "double_coded": [True, True, True, True, True],
            "agree": [False, False, True, False, True],
        }
    )
    master = pd.DataFrame(
        {
            "retrieval_pair_id": ["a", "b", "c", "d", "e"],
            "domain": ["circular_economy"] * 5,
            "outside_pool_sample": [False] * 5,
            "audit_sample_selected": [True] * 5,
        }
    )
    # a: ann1=non-match, ann2=match, disagree -> adjudicated match -> positive miss
    # b: ann1=uncertain, ann2=match, disagree -> adjudicated non-match -> NOT a positive miss
    # c: agree (match/match) -> final=match, but ann1 already match, not a "miss"
    # d: ann1=match, ann2=non-match, disagree -> adjudicated match -> not a miss (ann1 already match)
    # e: agree (non-match/non-match)
    adjudication_lookup = {"a": "match", "b": "non-match", "d": "match"}
    result = evaluate_domain(merged, master, adjudication_lookup, "circular_economy")
    assert result["n_audited_in_pool_rows"] == 5
    assert result["n_positive_misses"] == 1  # only row "a"
    assert result["adjudicated_positive_miss_rate"] == pytest.approx(0.2)
    assert result["escalation_triggered"]  # 20% > 2%


def test_escalation_not_triggered_below_threshold():
    merged = pd.DataFrame(
        {
            "retrieval_pair_id": [f"r{i}" for i in range(100)],
            "domain": ["d"] * 100,
            "annotator_1_label": ["match"] * 100,
            "annotator_2_label": ["match"] * 100,
            "double_coded": [True] * 100,
            "agree": [True] * 100,
        }
    )
    master = pd.DataFrame(
        {
            "retrieval_pair_id": [f"r{i}" for i in range(100)],
            "domain": ["d"] * 100,
            "outside_pool_sample": [False] * 100,
            "audit_sample_selected": [True] * 100,
        }
    )
    result = evaluate_domain(merged, master, {}, "d")
    assert result["n_positive_misses"] == 0
    assert not result["escalation_triggered"]


def test_select_additional_sample_excludes_already_selected_and_is_deterministic():
    master = pd.DataFrame(
        {
            "retrieval_pair_id": [f"r{i}" for i in range(20)],
            "domain": ["d"] * 20,
            "outside_pool_sample": [False] * 20,
            "route_signature": ["jaro_winkler"] * 10 + ["embedding"] * 10,
            "difficulty_band": ["x_weak_semantic_0.50_0.60"] * 20,
        }
    )
    already = {"r0", "r1", "r2"}
    sel1 = select_additional_sample(master, "d", already, 0.10, seed=42)
    sel2 = select_additional_sample(master, "d", already, 0.10, seed=42)
    assert sel1 == sel2  # deterministic
    assert sel1.isdisjoint(already)  # never re-selects already-double-coded rows
