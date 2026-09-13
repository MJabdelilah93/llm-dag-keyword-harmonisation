"""C1B tests: genuine domain universe reconstruction, benchmark coverage
reporting, candidate-set hashing, and the final capture-by-partition
computation. Synthetic logic tests plus real hash/count checks against
the actual (never-modified) legacy/local keyword-frequency source files."""
from __future__ import annotations

import pandas as pd
import pytest

from strengthening.experiments import b8_benchmark_eval_dense as dense_eval


# -- genuine universe reconstruction (real files, read-only) -----------------

def test_build_genuine_domain_universes_real_counts_and_source_hashes():
    try:
        universes = dense_eval.build_genuine_domain_universes()
    except FileNotFoundError:
        pytest.skip("legacy CE keyword-frequency file not present in this environment")

    ce = universes["circular_economy"]
    bio = universes["biomedical_diabetes_mellitus"]
    assert len(ce["universe"]) == 4000
    assert len(bio["universe"]) == 4092
    # deterministic given the fixed seed/construction -- exact hashes computed
    # once and pinned here as a regression check
    assert ce["universe_hash_sha256"] == "fa78ca42c33900aaca34cc1c6c70f2b7acd716e8d046a1ef4e5d3abcb72db613"
    assert bio["universe_hash_sha256"] == "8e776457b0b4bbb726f731a0c3186cb01d3b060e57fe2d6d1255605a9efbb597"
    assert ce["source_sha256"] == "8fd003c60195565a6df6d6d5fbe2204d3df179d80cbe2c41cb997a82d8edd829"
    assert bio["source_sha256"] == "c1e5090f1b13144aaf393bd2384e19d728d730d6c8bc3a27aabaf57a179778a9"


def test_build_genuine_domain_universes_is_deterministic():
    try:
        u1 = dense_eval.build_genuine_domain_universes()
        u2 = dense_eval.build_genuine_domain_universes()
    except FileNotFoundError:
        pytest.skip("legacy CE keyword-frequency file not present in this environment")
    assert u1["circular_economy"]["universe"] == u2["circular_economy"]["universe"]
    assert u1["biomedical_diabetes_mellitus"]["universe"] == u2["biomedical_diabetes_mellitus"]["universe"]


def test_real_benchmark_coverage_matches_documented_gap():
    try:
        universes = dense_eval.build_genuine_domain_universes()
    except FileNotFoundError:
        pytest.skip("legacy CE keyword-frequency file not present in this environment")
    from strengthening.experiments.frozen_inputs import load_gold_stringonly

    gold_stringonly = load_gold_stringonly()
    coverage = dense_eval.check_benchmark_coverage(universes, gold_stringonly)
    # documented in the module docstring: 249/687 CE strings missing, 0/769 diabetes missing
    assert coverage["circular_economy"]["n_benchmark_strings"] == 687
    assert coverage["circular_economy"]["n_missing"] == 249
    assert coverage["biomedical_diabetes_mellitus"]["n_benchmark_strings"] == 769
    assert coverage["biomedical_diabetes_mellitus"]["n_missing"] == 0


# -- synthetic logic: coverage/hash/capture computation -----------------------

def test_check_benchmark_coverage_synthetic():
    universes = {"circular_economy": {"universe": ["a", "b", "c"]}}
    gold = pd.DataFrame({"domain": ["circular_economy"] * 2, "string_a": ["a", "d"], "string_b": ["b", "e"]})
    coverage = dense_eval.check_benchmark_coverage(universes, gold)
    assert coverage["circular_economy"]["n_benchmark_strings"] == 4  # a,b,d,e
    assert coverage["circular_economy"]["n_in_universe"] == 2  # a,b
    assert coverage["circular_economy"]["n_missing"] == 2  # d,e


def test_candidate_set_hash_is_order_independent_but_content_sensitive():
    class FakeCandidate:
        def __init__(self, candidate, routes):
            self.candidate = candidate
            self.routes = routes

    class FakeCandidateSet:
        def __init__(self, seed, candidates):
            self.seed = seed
            self.candidates = candidates

    set_a = [FakeCandidateSet("x", [FakeCandidate("y", ("lexical_exact",))]), FakeCandidateSet("z", [])]
    set_b = [FakeCandidateSet("z", []), FakeCandidateSet("x", [FakeCandidate("y", ("lexical_exact",))])]
    set_c = [FakeCandidateSet("x", [FakeCandidate("w", ("lexical_exact",))]), FakeCandidateSet("z", [])]

    assert dense_eval.candidate_set_hash(set_a) == dense_eval.candidate_set_hash(set_b)
    assert dense_eval.candidate_set_hash(set_a) != dense_eval.candidate_set_hash(set_c)


def test_compute_capture_by_partition_synthetic():
    capture_df = pd.DataFrame({
        "pair_id": ["p1", "p2", "p3", "p4"],
        "domain": ["circular_economy", "circular_economy", "biomedical_diabetes_mellitus", "biomedical_diabetes_mellitus"],
        "b8_captured": [True, False, True, True],
    })
    gold_labels = pd.DataFrame({
        "pair_id": ["p1", "p2", "p3", "p4"],
        "domain": ["circular_economy", "circular_economy", "biomedical_diabetes_mellitus", "biomedical_diabetes_mellitus"],
        "final_gold_label": ["match", "match", "match", "non-match"],
    })
    result = dense_eval._compute_capture_by_partition(capture_df, gold_labels)
    assert result["ce400"]["n_gold_match_pairs"] == 2
    assert result["ce400"]["n_gold_match_pairs_captured"] == 1
    assert result["ce400"]["benchmark_capture_rate"] == 0.5
    assert result["diabetes500"]["n_gold_match_pairs"] == 1
    assert result["diabetes500"]["n_gold_match_pairs_captured"] == 1
    assert result["diabetes500"]["benchmark_capture_rate"] == 1.0
    assert result["diabetes500"]["n_gold_non_match_pairs"] == 1
    assert result["diabetes500"]["n_gold_non_match_pairs_captured"] == 1
    assert result["pooled900"]["n_gold_match_pairs"] == 3
    assert result["pooled900"]["n_gold_match_pairs_captured"] == 2
