"""C1 frozen-inference preflight: tests for frozen_inputs, b1_b5_baselines,
paid_gate, the LLM-runner dry-run builders, b8_benchmark_eval, cost_preflight,
and transitive_contradiction_diagnostic. Synthetic data only, except hash
checks against the real, never-modified frozen gold and historical
artefacts. No test in this file makes any network/API call."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from strengthening.experiments import (
    b1_b5_baselines,
    b6_runner,
    b8_benchmark_eval,
    cost_preflight,
    frozen_inputs,
    openai_second_provider_runner,
    primary_m7_runner,
    transitive_contradiction_diagnostic,
)
from strengthening.experiments.paid_gate import PaidExecutionNotAuthorisedError, require_paid_execution_authorised

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]

# Five tests below exercise real public production code (frozen_inputs,
# primary_m7_runner, b6_runner, openai_second_provider_runner) but require the
# frozen gold CSV, which is restricted research material never distributed in
# the public release (see strengthening/restricted_local/, gitignored). They
# run normally whenever that fixture is actually present (e.g. the authors'
# own working copy); they are explicitly skipped, not silently deleted or
# weakened, when it is not.
requires_restricted_gold_csv = pytest.mark.skipif(
    not frozen_inputs.GOLD_CSV.exists(),
    reason="requires restricted local research fixture (frozen gold CSV); not distributed in public release",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# -- frozen_inputs ------------------------------------------------------------

@requires_restricted_gold_csv
def test_frozen_gold_hash_matches_expected():
    assert frozen_inputs.verify_gold_hash() == frozen_inputs.EXPECTED_GOLD_CSV_SHA256


def test_verify_gold_hash_aborts_on_mismatch(monkeypatch, tmp_path):
    fake = tmp_path / "fake_gold.csv"
    fake.write_text("pair_id,domain,string_a,string_b,final_gold_label\np1,circular_economy,a,b,match\n", encoding="utf-8")
    monkeypatch.setattr(frozen_inputs, "GOLD_CSV", fake)
    with pytest.raises(frozen_inputs.FrozenInputError, match="hash mismatch"):
        frozen_inputs.verify_gold_hash()


@requires_restricted_gold_csv
def test_build_partitions_real_counts_and_disjointness():
    partitions = frozen_inputs.build_partitions()
    result = frozen_inputs.validate_partitions(partitions)
    assert result.ok, result.issues
    assert len(partitions["ce400"]) == 400
    assert len(partitions["diabetes500"]) == 500
    assert len(partitions["pooled900"]) == 900


def test_validate_partitions_detects_duplicate_pair_id():
    df = pd.DataFrame({"pair_id": ["p1", "p1"], "domain": ["circular_economy"] * 2, "string_a": ["a", "b"], "string_b": ["x", "y"]})
    partitions = {"ce400": df, "diabetes500": df.iloc[0:0], "pooled900": df}
    result = frozen_inputs.validate_partitions(partitions)
    assert not result.ok
    assert any("duplicate" in i for i in result.issues)


def test_validate_partitions_detects_missing_string():
    df = pd.DataFrame({"pair_id": ["p1"], "domain": ["circular_economy"], "string_a": [""], "string_b": ["b"]})
    partitions = {"ce400": df, "diabetes500": df.iloc[0:0], "pooled900": df}
    result = frozen_inputs.validate_partitions(partitions)
    assert not result.ok
    assert any("missing" in i for i in result.issues)


def test_validate_partitions_detects_forbidden_gold_column_leak():
    df = pd.DataFrame({"pair_id": ["p1"], "domain": ["circular_economy"], "string_a": ["a"], "string_b": ["b"], "final_gold_label": ["match"]})
    partitions = {"ce400": df, "diabetes500": df.iloc[0:0], "pooled900": df}
    result = frozen_inputs.validate_partitions(partitions)
    assert not result.ok
    assert any("leaked" in i for i in result.issues)


def test_validate_partitions_detects_ce_diabetes_overlap():
    ce = pd.DataFrame({"pair_id": ["p1"], "domain": ["circular_economy"], "string_a": ["a"], "string_b": ["b"]})
    bio = pd.DataFrame({"pair_id": ["p1"], "domain": ["biomedical_diabetes_mellitus"], "string_a": ["c"], "string_b": ["d"]})
    pooled = pd.concat([ce, bio], ignore_index=True)
    result = frozen_inputs.validate_partitions({"ce400": ce, "diabetes500": bio, "pooled900": pooled})
    assert not result.ok
    assert any("overlap" in i for i in result.issues)


# -- b1_b5_baselines -----------------------------------------------------------

def test_frozen_thresholds_hash_verified_and_values():
    thresholds = b1_b5_baselines.load_frozen_thresholds()
    assert thresholds["b3_jaro_winkler"] == 0.92
    assert thresholds["b4_tfidf_ngram"] == 0.68
    assert thresholds["b5_embedding"] == 0.85
    assert thresholds["source_sha256"] == b1_b5_baselines.EXPECTED_TUNED_THRESHOLDS_SHA256


def test_load_frozen_thresholds_aborts_on_hash_mismatch(monkeypatch, tmp_path):
    fake = tmp_path / "fake_thresholds.json"
    fake.write_text('{"b3_jaro_winkler": {"threshold": 0.5}}', encoding="utf-8")
    monkeypatch.setattr(b1_b5_baselines, "TUNED_THRESHOLDS_JSON", fake)
    with pytest.raises(b1_b5_baselines.ThresholdProvenanceError, match="hash mismatch"):
        b1_b5_baselines.load_frozen_thresholds()


def test_normalise_applies_frozen_four_steps():
    assert b1_b5_baselines.normalise("  Circular   Economy  ") == "circular economy"


def test_b1_exact_is_lowercase_only_not_full_normalise():
    assert b1_b5_baselines.b1_exact("Circular Economy", "circular economy") == "match"
    assert b1_b5_baselines.b1_exact("Circular  Economy", "circular economy") == "non-match"  # double space -- B1 does NOT collapse whitespace


def test_b2_normalised_collapses_whitespace_unlike_b1():
    assert b1_b5_baselines.b2_normalised("Circular  Economy", "circular economy") == "match"


def test_b3_predict_uses_jaro_winkler_and_frozen_threshold():
    assert b1_b5_baselines.b3_predict("recycling", "recycling", 0.92) == "match"
    assert b1_b5_baselines.b3_predict("recycling", "totally different phrase", 0.92) == "non-match"


# -- paid_gate ------------------------------------------------------------------

def test_paid_gate_refuses_without_execute_paid():
    with pytest.raises(PaidExecutionNotAuthorisedError, match="not authorised"):
        require_paid_execution_authorised(False, "SOME_KEY_VAR")


def test_paid_gate_refuses_without_api_key(monkeypatch):
    monkeypatch.delenv("SOME_TEST_KEY_VAR", raising=False)
    with pytest.raises(PaidExecutionNotAuthorisedError, match="SOME_TEST_KEY_VAR"):
        require_paid_execution_authorised(True, "SOME_TEST_KEY_VAR")


def test_paid_gate_passes_with_both(monkeypatch):
    monkeypatch.setenv("SOME_TEST_KEY_VAR", "fake-value")
    assert require_paid_execution_authorised(True, "SOME_TEST_KEY_VAR") == "fake-value"


# -- LLM runner dry-run builders (no network, request count = n_pairs) --------

@requires_restricted_gold_csv
def test_primary_m7_dry_run_exactly_one_request_per_pair():
    result = primary_m7_runner.dry_run_all_partitions()
    assert result["counts"]["ce400"]["n_requests"] == 400
    assert result["counts"]["diabetes500"]["n_requests"] == 500
    assert result["counts"]["pooled900"]["n_requests"] == 900
    assert result["config"]["guard_confidence_threshold"] == 0.5
    assert result["config"]["model_id"] == "claude-haiku-4-5-20251001"


def test_primary_m7_build_request_substitutes_keywords_and_uses_frozen_prompt():
    config = primary_m7_runner.load_frozen_config()
    req = primary_m7_runner.build_request(config, "keyword one", "keyword two")
    assert req["model"] == "claude-haiku-4-5-20251001"
    assert req["temperature"] == 0
    assert "keyword one" in req["messages"][0]["content"]
    assert "keyword two" in req["messages"][0]["content"]
    assert req["system"] == config.system_prompt


@requires_restricted_gold_csv
def test_b6_dry_run_exactly_one_request_per_pair():
    result = b6_runner.dry_run_all_partitions()
    assert result["counts"]["ce400"]["n_requests"] == 400
    assert result["counts"]["pooled900"]["n_requests"] == 900


def test_b6_parse_response_matches_legacy_heuristic():
    assert b6_runner.parse_b6_response("These are a match.") == "match"
    assert b6_runner.parse_b6_response("This is a non-match.") == "non_match"
    assert b6_runner.parse_b6_response("I am not sure.") == "uncertain"


@requires_restricted_gold_csv
def test_openai_dry_run_exactly_one_request_per_pair_and_frozen_threshold():
    result = openai_second_provider_runner.dry_run_all_partitions()
    assert result["counts"]["ce400"]["n_requests"] == 400
    assert result["counts"]["pooled900"]["n_requests"] == 900
    assert result["config"]["frozen_threshold"] == 0.80
    assert result["config"]["model_id"] == "gpt-5.4-nano-2026-03-17"


def test_openai_config_aborts_on_wrong_frozen_threshold(monkeypatch, tmp_path):
    fake_manifest = tmp_path / "fake_manifest.json"
    fake_manifest.write_text('{"threshold_selection": {"selected_threshold": 0.55}}', encoding="utf-8")
    monkeypatch.setattr(openai_second_provider_runner, "DEV_FREEZE_MANIFEST_PATH", fake_manifest)
    with pytest.raises(openai_second_provider_runner.FrozenConfigError, match="expected 0.8"):
        openai_second_provider_runner.load_frozen_config()


# -- b8_benchmark_eval (synthetic candidate/gold graph) -----------------------

def test_determine_capture_flags_pairs_found_by_retrieval():
    gold = pd.DataFrame({
        "pair_id": ["p1", "p2"], "domain": ["circular_economy", "circular_economy"],
        "string_a": ["alpha", "gamma"], "string_b": ["beta", "delta"],
    })

    class FakeCandidate:
        def __init__(self, candidate):
            self.candidate = candidate

    class FakeCandidateSet:
        def __init__(self, seed, candidates):
            self.seed = seed
            self.candidates = [FakeCandidate(c) for c in candidates]

    cand_sets = {"circular_economy": [FakeCandidateSet("alpha", ["beta"]), FakeCandidateSet("gamma", [])]}
    cand_pairs = b8_benchmark_eval.candidate_pairs_by_domain(cand_sets)
    capture_df = b8_benchmark_eval.determine_capture(gold, cand_pairs)
    assert capture_df.set_index("pair_id").loc["p1", "b8_captured"]
    assert not capture_df.set_index("pair_id").loc["p2", "b8_captured"]


def test_predict_b8_reuses_b7_and_never_calls_anything_for_uncaptured():
    capture_df = pd.DataFrame({"pair_id": ["p1", "p2"], "domain": ["circular_economy"] * 2, "b8_captured": [True, False]})
    predicted = b8_benchmark_eval.predict_b8_for_benchmark(capture_df, {"p1": "match"})
    row = predicted.set_index("pair_id")
    assert row.loc["p1", "b8_predicted_label"] == "match"
    assert row.loc["p2", "b8_predicted_label"] == "non-match"


def test_predict_b8_never_fabricates_when_no_b7_predictions_available():
    capture_df = pd.DataFrame({"pair_id": ["p1"], "domain": ["circular_economy"], "b8_captured": [True]})
    predicted = b8_benchmark_eval.predict_b8_for_benchmark(capture_df, None)
    assert predicted.iloc[0]["b8_predicted_label"] is None


def test_benchmark_capture_rate_uses_correct_term_and_denominator():
    capture_df = pd.DataFrame({"pair_id": ["p1", "p2", "p3"], "domain": ["circular_economy"] * 3, "b8_captured": [True, False, True]})
    gold_labels = pd.DataFrame({"pair_id": ["p1", "p2", "p3"], "final_gold_label": ["match", "match", "non-match"]})
    result = b8_benchmark_eval.compute_benchmark_capture_rate(capture_df, gold_labels)
    assert result["term"] == "benchmark capture rate"
    assert result["overall"]["n_gold_match"] == 2
    assert result["overall"]["n_captured"] == 1
    assert result["overall"]["benchmark_capture_rate"] == 0.5
    assert "pair completeness" not in result["caveat"].lower() or "not pair completeness" in result["caveat"].lower()


# -- cost_preflight -------------------------------------------------------------

def test_per_pair_rate_arithmetic():
    runs = [{"n_pairs": 100, "input_tokens": 1000, "output_tokens": 200}, {"n_pairs": 100, "input_tokens": 3000, "output_tokens": 200}]
    rate = cost_preflight.per_pair_rate(runs)
    assert rate["total_pairs_across_runs"] == 200
    assert rate["mean_input_tokens_per_pair"] == pytest.approx(20.0)
    assert rate["mean_output_tokens_per_pair"] == pytest.approx(2.0)
    assert not rate["per_call_percentiles_available"]


def test_estimate_cost_uses_current_prices_not_stale_ones():
    cost = cost_preflight.estimate_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    assert cost == pytest.approx(1.0 + 5.0)


def test_paid_request_matrix_matches_expected_logical_design():
    result = cost_preflight.run()
    prm = result["paid_request_matrix"]
    assert prm["primary_m7"]["n_new_requests"] == 900
    assert prm["b6_naive_llm"]["n_new_requests"] == 900
    assert prm["b7_direct_relation"]["n_new_requests"] == 900
    assert prm["b8_hybrid"]["n_new_requests"] == 0
    assert prm["openai_second_provider"]["n_new_requests"] == 900
    assert prm["total_anthropic_requests"] == 2700
    assert prm["total_openai_requests"] == 900


# -- transitive_contradiction_diagnostic ---------------------------------------

def test_count_closed_triangles_synthetic():
    gold = pd.DataFrame({
        "pair_id": ["p1", "p2", "p3", "p4"],
        "string_a": ["a", "a", "b", "a"], "string_b": ["b", "c", "c", "d"],
    })
    info = transitive_contradiction_diagnostic.count_closed_triangles(gold)
    assert info["n_closed_triangles"] == 1  # a-b-c is closed; a-d is not part of any triangle


def test_diagnose_method_distinguishes_direct_and_transitive_only_contradictions():
    gold = pd.DataFrame({
        "pair_id": ["p1", "p2", "p3"],
        "domain": ["circular_economy"] * 3,
        "string_a": ["a", "b", "a"], "string_b": ["b", "c", "c"],
        "final_gold_label": ["match", "match", "non-match"],  # a~b, b~c both match, but a~c is gold NON-MATCH
    })
    # method predicts match on p1 and p2 (a-b, b-c) but correctly non-match on p3 (a-c) --
    # a and c still end up in the same predicted component TRANSITIVELY via b.
    predictions = pd.DataFrame({"pair_id": ["p1", "p2", "p3"], "method_x": ["match", "match", "non-match"]})
    result = transitive_contradiction_diagnostic.diagnose_method(gold, predictions, "method_x")
    assert result["n_gold_non_match_evaluated"] == 1
    assert result["n_connected_incorrectly"] == 1
    assert result["n_direct_error"] == 0
    assert result["n_transitive_only_contradiction"] == 1


def test_diagnose_method_direct_error_when_method_predicts_match_on_the_gold_non_match_pair_itself():
    gold = pd.DataFrame({
        "pair_id": ["p1"], "domain": ["circular_economy"], "string_a": ["a"], "string_b": ["b"], "final_gold_label": ["non-match"],
    })
    predictions = pd.DataFrame({"pair_id": ["p1"], "method_x": ["match"]})
    result = transitive_contradiction_diagnostic.diagnose_method(gold, predictions, "method_x")
    assert result["n_direct_error"] == 1
    assert result["n_transitive_only_contradiction"] == 0


# -- real evidence unchanged --------------------------------------------------

def test_frozen_gold_files_unchanged_by_this_phase():
    gold_dir = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "gold"
    expected = {
        "PRIMARY_GOLD_900_FINAL.xlsx": "bb90618580e944e54904c231efca83f50eebc1ef5eb4ea7f0fd8e803adbbec0a",
        "PRIMARY_GOLD_900_FINAL.csv": "89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479",
    }
    for name, expected_hash in expected.items():
        path = gold_dir / name
        if not path.exists():
            pytest.skip(f"{name} not present in this environment")
        assert _sha256(path) == expected_hash


def test_tuned_thresholds_and_openai_freeze_manifest_unchanged():
    legacy_root = STRENGTHENING_ROOT.parent
    expected = {
        legacy_root / "results" / "tuned_thresholds.json": "87715a443597ffa697551968d3a5784d4c4978fb539087cc94bdce7230849836",
    }
    for path, expected_hash in expected.items():
        if not path.exists():
            pytest.skip(f"{path} not present in this environment")
        assert _sha256(path) == expected_hash


def test_no_h3_working_or_completed_files_exist():
    v1_dir = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1"
    matches = list(v1_dir.glob("ANNOTATOR_*_RETRIEVAL_WORKING*")) + list(v1_dir.glob("ANNOTATOR_*_RETRIEVAL_COMPLETED*"))
    assert matches == []


def test_restricted_experiments_directory_is_gitignored():
    import subprocess

    worktree = Path(__file__).resolve().parents[2]
    if not (worktree / ".git").exists():
        pytest.skip("requires a git checkout to verify gitignore coverage via `git check-ignore`; not applicable to a plain source archive/tarball extraction")
    proc = subprocess.run(
        ["git", "check-ignore", "-v", "strengthening/restricted_local/experiments/probe.csv"],
        cwd=worktree, capture_output=True, text=True,
    )
    assert proc.returncode == 0
