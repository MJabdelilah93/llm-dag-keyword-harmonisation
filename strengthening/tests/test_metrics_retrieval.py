"""Tests for strengthening.metrics.retrieval.

Two things are pinned here:

1. the "insufficient gold data" behaviour -- every gold-dependent metric
   returns ``None``, never a fabricated number, when gold retrieval
   annotations are absent; and
2. the arithmetic, on a small hand-computed synthetic gold example.
"""

from __future__ import annotations

import pytest

from strengthening.metrics.retrieval import (
    candidate_count,
    exhaustive_comparisons,
    normalise_pair,
    normalise_pairs,
    pair_completeness,
    pairs_quality,
    reduction_ratio,
    retrieval_audit,
)

# ---------------------------------------------------------------------------
# Hand-constructed synthetic example
# ---------------------------------------------------------------------------
# Four items: a, b, c, d.
#   exhaustive comparisons = 4 * 3 / 2 = 6
#
# Candidate generation produced 4 distinct pairs:
#   (a,b) (a,c) (b,c) (a,d)
#
# Gold-relevant pairs (3):
#   (a,b) (b,c) (c,d)
#
# Overlap = {(a,b), (b,c)} -> 2 pairs.
#
#   pair_completeness = |gold & candidates| / |gold| = 2 / 3 = 0.6666...
#   pairs_quality     = |gold & candidates| / |candidates| = 2 / 4 = 0.5
#   reduction_ratio   = 1 - 4 / 6 = 1 - 0.6666... = 1/3 = 0.3333...
N_ITEMS = 4
CANDIDATES = [("a", "b"), ("a", "c"), ("b", "c"), ("a", "d")]
GOLD = [("a", "b"), ("b", "c"), ("c", "d")]


# ---------------------------------------------------------------------------
# Pair normalisation
# ---------------------------------------------------------------------------
def test_pairs_are_unordered_and_normalised() -> None:
    assert normalise_pair(("b", "a")) == ("a", "b")
    assert normalise_pair(("a", "b")) == ("a", "b")
    assert normalise_pairs([("a", "b"), ("b", "a")]) == {("a", "b")}
    with pytest.raises(ValueError):
        normalise_pair(("a", "a"))  # self-pair
    with pytest.raises(ValueError):
        normalise_pair(("a", "b", "c"))


# ---------------------------------------------------------------------------
# pair_completeness
# ---------------------------------------------------------------------------
def test_pair_completeness_arithmetic() -> None:
    assert pair_completeness(CANDIDATES, GOLD) == pytest.approx(2.0 / 3.0)
    # A candidate set that contains every gold pair is complete.
    assert pair_completeness(GOLD, GOLD) == pytest.approx(1.0)
    # A candidate set that contains none of them is genuinely zero -- a real
    # estimate, and therefore 0.0 rather than None.
    assert pair_completeness([("x", "y")], GOLD) == 0.0


def test_pair_completeness_is_none_without_gold() -> None:
    # Gold retrieval annotations do not exist yet.
    assert pair_completeness(CANDIDATES, gold=None) is None
    assert pair_completeness(CANDIDATES) is None
    # An empty gold set is also not estimable (nothing to be complete of).
    assert pair_completeness(CANDIDATES, gold=[]) is None


# ---------------------------------------------------------------------------
# candidate_count
# ---------------------------------------------------------------------------
def test_candidate_count_counts_distinct_unordered_pairs() -> None:
    assert candidate_count(CANDIDATES) == 4
    # Duplicates and reversed duplicates collapse: 3 inputs, 2 distinct pairs.
    assert candidate_count([("a", "b"), ("b", "a"), ("a", "c")]) == 2
    assert candidate_count([]) == 0


# ---------------------------------------------------------------------------
# exhaustive_comparisons
# ---------------------------------------------------------------------------
def test_exhaustive_comparisons_arithmetic() -> None:
    assert exhaustive_comparisons(4) == 6  # 4 * 3 / 2
    assert exhaustive_comparisons(100) == 4950  # 100 * 99 / 2
    # 1049 * 1048 = 1_099_352 ; / 2 = 549_676
    assert exhaustive_comparisons(1049) == 549_676
    # Fewer than two items means no comparisons at all.
    assert exhaustive_comparisons(1) == 0
    assert exhaustive_comparisons(0) == 0
    with pytest.raises(ValueError):
        exhaustive_comparisons(-1)


# ---------------------------------------------------------------------------
# reduction_ratio
# ---------------------------------------------------------------------------
def test_reduction_ratio_arithmetic() -> None:
    assert reduction_ratio(4, N_ITEMS) == pytest.approx(1.0 / 3.0)  # 1 - 4/6
    assert reduction_ratio(0, N_ITEMS) == pytest.approx(1.0)  # nothing generated
    assert reduction_ratio(6, N_ITEMS) == pytest.approx(0.0)  # all pairs generated


def test_reduction_ratio_is_none_when_the_baseline_is_undefined() -> None:
    # Fewer than 2 items -> exhaustive_comparisons == 0 -> undefined, not zero.
    assert reduction_ratio(0, 1) is None
    assert reduction_ratio(0, 0) is None


# ---------------------------------------------------------------------------
# pairs_quality (PLACEHOLDER)
# ---------------------------------------------------------------------------
def test_pairs_quality_arithmetic() -> None:
    assert pairs_quality(CANDIDATES, GOLD) == pytest.approx(0.5)  # 2 / 4
    assert pairs_quality(GOLD, GOLD) == pytest.approx(1.0)
    assert pairs_quality([("x", "y")], GOLD) == 0.0


def test_pairs_quality_is_none_without_gold_or_without_candidates() -> None:
    assert pairs_quality(CANDIDATES, gold=None) is None
    assert pairs_quality(CANDIDATES) is None
    assert pairs_quality([], gold=GOLD) is None  # empty denominator


def test_pairs_quality_is_documented_as_a_placeholder() -> None:
    assert "PLACEHOLDER" in (pairs_quality.__doc__ or "")


# ---------------------------------------------------------------------------
# retrieval_audit bundle
# ---------------------------------------------------------------------------
def test_retrieval_audit_without_gold_leaves_gold_metrics_none() -> None:
    audit = retrieval_audit(
        CANDIDATES, n_items=N_ITEMS, latency_seconds=12.5, cost_usd=0.42
    )
    assert audit.gold_available is False
    # Not estimable -> None. Not 0.0, and not a placeholder number.
    assert audit.pair_completeness is None
    assert audit.pairs_quality is None
    # Gold-independent metrics are still computed.
    assert audit.candidate_count == 4
    assert audit.exhaustive_comparisons == 6
    assert audit.reduction_ratio == pytest.approx(1.0 / 3.0)
    # Latency and cost are pure pass-through.
    assert audit.latency_seconds == 12.5
    assert audit.cost_usd == 0.42


def test_retrieval_audit_with_gold_matches_the_hand_arithmetic() -> None:
    audit = retrieval_audit(
        CANDIDATES,
        n_items=N_ITEMS,
        gold=GOLD,
        latency_seconds=3.0,
        cost_usd=None,
        notes="synthetic",
    )
    assert audit.gold_available is True
    assert audit.pair_completeness == pytest.approx(2.0 / 3.0)
    assert audit.pairs_quality == pytest.approx(0.5)
    assert audit.reduction_ratio == pytest.approx(1.0 / 3.0)
    assert audit.candidate_count == 4
    assert audit.exhaustive_comparisons == 6
    assert audit.latency_seconds == 3.0
    assert audit.cost_usd is None
    assert audit.notes == "synthetic"


def test_retrieval_audit_accepts_one_shot_iterators_for_gold() -> None:
    audit = retrieval_audit(iter(CANDIDATES), n_items=N_ITEMS, gold=iter(GOLD))
    assert audit.pair_completeness == pytest.approx(2.0 / 3.0)
    assert audit.pairs_quality == pytest.approx(0.5)


def test_retrieval_audit_serialises_none_faithfully() -> None:
    payload = retrieval_audit(CANDIDATES, n_items=N_ITEMS).to_dict()
    assert payload["pair_completeness"] is None
    assert payload["pairs_quality"] is None
    assert payload["gold_available"] is False
