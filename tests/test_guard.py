"""Tests for the verified v1 guard layer: G1-G4 only, symmetric threshold.

Scope note: see conftest.py. apply_guard() here is copied verbatim from
scripts/run_full_workflow.py's executed logic (independently confirmed in
Phase 0A/0B to reproduce results/tuned_thresholds.json and
results/dev_results_full_workflow.csv exactly from real evidence). G5 is
deliberately NOT tested because it was never implemented in v1 — see
docs/provenance/v1_retrospective_run_manifest.json.
"""
import json

from reparse_dev_log_v1 import apply_guard, raw_decision_of, binary_metrics


def _valid_response(decision="match", confidence=0.95, justification="test"):
    return json.dumps({"decision": decision, "confidence": confidence, "justification": justification})


def test_g1_malformed_json_routes_to_uncertain():
    g = apply_guard("not json at all {{{", 0.50)
    assert g["decision"] == "uncertain"
    assert g["guard_applied"] == "G1"


def test_g1_strips_markdown_fence_before_parsing():
    fenced = "```json\n" + _valid_response() + "\n```"
    g = apply_guard(fenced, 0.50)
    assert g["decision"] == "match"
    assert g["guard_applied"] is None


def test_g2_missing_required_field_routes_to_uncertain():
    malformed = json.dumps({"decision": "match", "confidence": 0.9})  # no justification
    g = apply_guard(malformed, 0.50)
    assert g["decision"] == "uncertain"
    assert g["guard_applied"] == "G2"


def test_g3_invalid_decision_value_routes_to_uncertain():
    bad = json.dumps({"decision": "definitely_yes", "confidence": 0.9, "justification": "x"})
    g = apply_guard(bad, 0.50)
    assert g["decision"] == "uncertain"
    assert g["guard_applied"] == "G3"


def test_g4_symmetric_threshold_050_is_verified_v1_value():
    # confidence just below 0.50 -> overridden to uncertain
    below = _valid_response(decision="match", confidence=0.49)
    g = apply_guard(below, 0.50)
    assert g["decision"] == "uncertain"
    assert g["guard_applied"] == "G4"

    # confidence exactly at threshold -> passes (>= not >)
    at = _valid_response(decision="match", confidence=0.50)
    g = apply_guard(at, 0.50)
    assert g["decision"] == "match"
    assert g["guard_applied"] is None


def test_g4_threshold_is_symmetric_not_asymmetric():
    # Legacy configs/guard_thresholds.yaml documents match=0.80/non_match=0.70
    # (never executed). Verify the SAME threshold value gates both decisions
    # identically -- this is what actually ran.
    match_low = _valid_response(decision="match", confidence=0.55)
    nonmatch_low = _valid_response(decision="non_match", confidence=0.55)
    g_match = apply_guard(match_low, 0.60)
    g_nonmatch = apply_guard(nonmatch_low, 0.60)
    assert g_match["decision"] == "uncertain"
    assert g_nonmatch["decision"] == "uncertain"  # would PASS under the never-executed
                                                     # asymmetric 0.70 non-match threshold


def test_uncertain_decision_never_gated_by_confidence():
    low_conf_uncertain = _valid_response(decision="uncertain", confidence=0.1)
    g = apply_guard(low_conf_uncertain, 0.50)
    assert g["decision"] == "uncertain"
    assert g["guard_applied"] is None  # not overridden -- already uncertain


def test_no_guard_failure_is_ever_dropped_always_routes_to_uncertain():
    for bad_input in ["{malformed", json.dumps({"decision": "match"}), json.dumps(
            {"decision": "bogus", "confidence": 0.9, "justification": "x"})]:
        g = apply_guard(bad_input, 0.50)
        assert g["decision"] == "uncertain"


def test_raw_decision_of_ignores_guard_bypasses_threshold():
    # raw_decision_of() reflects the LLM's own stated decision, pre-guard
    low_conf_match = _valid_response(decision="match", confidence=0.10)
    assert raw_decision_of(low_conf_match) == "match"


def test_binary_metrics_excludes_gold_uncertain_from_denominator():
    gold = ["match", "match", "non_match", "uncertain"]
    pred = ["match", "match", "non_match", "match"]
    m = binary_metrics(gold, pred)
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0


def test_binary_metrics_counts_missed_abstention_as_false_negative():
    gold = ["match"]
    pred = ["uncertain"]
    m = binary_metrics(gold, pred)
    assert m["recall"] == 0.0
    assert m["coverage"] == 0.0
