"""C2 tests: guard/retry logic, resumability, freeze-manifest and cost-
report arithmetic, and the evaluation/bootstrap/selective/transitivity
logic. All synthetic -- no test in this file makes a network/API call."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from strengthening.experiments import c2_cost_report, c2_evaluate
from strengthening.experiments.paid_execution_common import apply_guard, call_with_retries, load_completed_pair_ids


# -- guard logic ---------------------------------------------------------

def test_apply_guard_valid_response_above_threshold():
    r = apply_guard('{"decision":"match","confidence":0.9,"justification":"x"}', 0.5)
    assert r["decision"] == "match" and not r["guard_applied"]


def test_apply_guard_g1_malformed_json():
    r = apply_guard("not json", 0.5)
    assert r["decision"] == "uncertain" and r["guard_reason"] == "G1_json_parse_failure"


def test_apply_guard_g2_missing_fields():
    r = apply_guard('{"decision":"match"}', 0.5)
    assert r["decision"] == "uncertain" and r["guard_reason"] == "G2_missing_required_fields"


def test_apply_guard_g3_invalid_decision():
    r = apply_guard('{"decision":"maybe","confidence":0.9,"justification":"x"}', 0.5)
    assert r["decision"] == "uncertain" and r["guard_reason"] == "G3_invalid_decision_enum"


def test_apply_guard_g4_confidence_below_threshold():
    r = apply_guard('{"decision":"match","confidence":0.3,"justification":"x"}', 0.5)
    assert r["decision"] == "uncertain" and r["guard_reason"] == "G4_confidence_below_threshold"


def test_apply_guard_does_not_override_a_genuine_uncertain_decision():
    r = apply_guard('{"decision":"uncertain","confidence":0.2,"justification":"x"}', 0.5)
    assert r["decision"] == "uncertain" and not r["guard_applied"]


def test_apply_guard_strips_markdown_fence():
    r = apply_guard('```json\n{"decision":"non_match","confidence":0.99,"justification":"x"}\n```', 0.5)
    assert r["decision"] == "non_match"


# -- retry logic -----------------------------------------------------------

def test_call_with_retries_succeeds_first_try():
    result, attempts, error = call_with_retries(lambda: "ok", max_retries=3, delays=(0, 0, 0))
    assert result == "ok" and attempts == 1 and error is None


def test_call_with_retries_succeeds_after_transient_failures():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    result, attempts, error = call_with_retries(flaky, max_retries=3, delays=(0, 0, 0))
    assert result == "ok" and attempts == 3 and error is None


def test_call_with_retries_exhausts_and_reports_error():
    def always_fails():
        raise RuntimeError("permanent failure")

    result, attempts, error = call_with_retries(always_fails, max_retries=3, delays=(0, 0, 0))
    assert result is None and attempts == 3 and "permanent failure" in error


# -- resumability ------------------------------------------------------------

def test_load_completed_pair_ids_only_counts_successful_records(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text(
        json.dumps({"pair_id": "p1", "error": None}) + "\n"
        + json.dumps({"pair_id": "p2", "error": "boom"}) + "\n"
        + json.dumps({"pair_id": "p3"}) + "\n",
        encoding="utf-8",
    )
    completed = load_completed_pair_ids(log)
    assert completed == {"p1", "p3"}


def test_load_completed_pair_ids_missing_file_returns_empty(tmp_path):
    assert load_completed_pair_ids(tmp_path / "does_not_exist.jsonl") == set()


# -- label normalisation ------------------------------------------------------

def test_normalise_label_maps_underscore_to_hyphen():
    assert c2_evaluate.normalise_label("non_match") == "non-match"
    assert c2_evaluate.normalise_label("match") == "match"


def test_normalise_label_maps_missing_to_uncertain():
    assert c2_evaluate.normalise_label(None) == "uncertain"
    assert c2_evaluate.normalise_label(float("nan")) == "uncertain"


# -- evaluation logic (synthetic) --------------------------------------------

def _synthetic_gold():
    return pd.DataFrame({
        "pair_id": ["p1", "p2", "p3", "p4"],
        "domain": ["circular_economy", "circular_economy", "biomedical_diabetes_mellitus", "biomedical_diabetes_mellitus"],
        "string_a": ["a1", "a2", "b1", "b2"], "string_b": ["c1", "c2", "d1", "d2"],
        "final_gold_label": ["match", "non-match", "match", "uncertain"],
    })


def test_evaluate_all_binary_excludes_uncertain_and_three_way_includes_all():
    gold = _synthetic_gold()
    predictions = {"MethodX": pd.DataFrame({"pair_id": ["p1", "p2", "p3", "p4"], "label": ["match", "match", "match", "non-match"]})}
    result = c2_evaluate.evaluate_all(gold, predictions)
    pooled = result["pooled900"]["MethodX"]
    # binary subset excludes p4 (gold-uncertain): p1 TP, p2 FP, p3 TP -> tp=2, fp=1, fn=0, tn=0
    assert pooled["binary"]["tp"] == 2 and pooled["binary"]["fp"] == 1
    # three-way includes all 4 items
    assert pooled["three_way"]["n_items"] == 4


def test_evaluate_all_raises_on_incomplete_merge():
    gold = _synthetic_gold()
    predictions = {"MethodX": pd.DataFrame({"pair_id": ["p1", "p2"], "label": ["match", "match"]})}
    with pytest.raises(ValueError):
        c2_evaluate.evaluate_all(gold, predictions)


def test_bootstrap_comparisons_synthetic():
    gold = _synthetic_gold()
    predictions = {
        "Primary_M7": pd.DataFrame({"pair_id": ["p1", "p2", "p3", "p4"], "label": ["match", "non-match", "match", "non-match"]}),
        "B3_JaroWinkler": pd.DataFrame({"pair_id": ["p1", "p2", "p3", "p4"], "label": ["non-match", "non-match", "non-match", "non-match"]}),
        "B5_Embedding": pd.DataFrame({"pair_id": ["p1", "p2", "p3", "p4"], "label": ["match", "match", "match", "match"]}),
        "B6": pd.DataFrame({"pair_id": ["p1", "p2", "p3", "p4"], "label": ["match", "non-match", "match", "match"]}),
        "B7": pd.DataFrame({"pair_id": ["p1", "p2", "p3", "p4"], "label": ["match", "non-match", "non-match", "non-match"]}),
    }
    result = c2_evaluate.bootstrap_comparisons(gold, predictions)
    assert "Primary_M7_vs_B3_JaroWinkler" in result["pooled900"]
    assert "Primary_M7_f1_ci" in result["pooled900"]
    diff = result["pooled900"]["Primary_M7_vs_B3_JaroWinkler"]
    assert "excludes_zero" in diff


def test_selective_prediction_analysis_synthetic():
    gold = _synthetic_gold()
    predictions = {"Primary_M7": pd.DataFrame({"pair_id": ["p1", "p2", "p3", "p4"], "label": ["match", "non-match", "match", "non-match"]})}
    confidences = {"Primary_M7": pd.DataFrame({"pair_id": ["p1", "p2", "p3", "p4"], "confidence": [0.9, 0.8, 0.95, 0.4]})}
    result = c2_evaluate.selective_prediction_analysis(gold, predictions, confidences)
    pooled = result["Primary_M7"]["pooled900"]
    assert pooled["n_binary_subset"] == 3  # p4 is gold-uncertain, excluded
    assert 0.0 <= pooled["coverage"] <= 1.0


def test_transitivity_diagnostic_synthetic():
    gold = pd.DataFrame({
        "pair_id": ["p1", "p2", "p3"], "domain": ["circular_economy"] * 3,
        "string_a": ["a", "b", "a"], "string_b": ["b", "c", "c"],
        "final_gold_label": ["match", "match", "non-match"],
    })
    predictions = {"MethodX": pd.DataFrame({"pair_id": ["p1", "p2", "p3"], "label": ["match", "match", "non-match"]})}
    result = c2_evaluate.transitivity_diagnostic(gold, predictions)
    m = result["methods"]["MethodX"]
    assert m["n_gold_non_match_evaluated"] == 1
    assert m["n_connected_incorrectly"] == 1
    assert m["n_transitive_only_contradiction"] == 1
    assert m["n_direct_error"] == 0


# -- cost report arithmetic ---------------------------------------------------

def test_cost_report_uses_current_prices_not_stale_ones():
    cost = c2_cost_report._cost("anthropic", 1_000_000, 1_000_000)
    assert cost == pytest.approx(1.0 + 5.0)
    cost_openai = c2_cost_report._cost("openai", 1_000_000, 1_000_000)
    assert cost_openai == pytest.approx(0.20 + 1.25)


def test_cost_report_run_synthetic(tmp_path, monkeypatch):
    manifest = {
        "entries": [
            {"method": "primary_m7", "rows": 900, "n_requests_logged": 900, "total_input_tokens": 1_000_000, "total_output_tokens": 200_000, "total_attempts": 900, "n_errors": 0},
            {"method": "openai", "rows": 900, "n_requests_logged": 900, "total_input_tokens": 500_000, "total_output_tokens": 100_000, "total_attempts": 900, "n_errors": 0},
            {"method": "b8", "rows": 900},
            {"method": "b1_b5", "rows": 900},
        ]
    }
    manifest_path = tmp_path / "freeze_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(c2_cost_report, "FREEZE_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(c2_cost_report, "REPORTS_DIR", tmp_path)

    result = c2_cost_report.run()
    assert result["per_method"]["primary_m7"]["cost_usd"] == pytest.approx(1.0 + 1.0, abs=0.01)
    assert result["per_method"]["b8"]["cost_usd"] == 0.0
    assert result["api_keys_exposed"] is False
