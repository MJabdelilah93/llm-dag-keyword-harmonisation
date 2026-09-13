"""Tests for strengthening.metrics.binary.

Every expected value below is derived BY HAND in a comment first; nothing
here was copied out of the implementation's output.
"""

from __future__ import annotations

import pytest

from strengthening.metrics import DEFAULT_SEED
from strengthening.metrics.binary import (
    bootstrap_ci,
    coverage_score,
    f1_score,
    paired_bootstrap_difference,
    precision_score,
    recall_score,
    scores_from_counts,
    scores_from_pairs,
)

MATCH = "match"
NON_MATCH = "non-match"
UNCERTAIN = "uncertain"


# ---------------------------------------------------------------------------
# Hand-computed toy confusion matrix
# ---------------------------------------------------------------------------
# Toy counts: TP = 6, FP = 2, FN = 3, TN = 9, abstained = 5.
#
#   precision = TP / (TP + FP) = 6 / (6 + 2) = 6 / 8  = 0.75
#   recall    = TP / (TP + FN) = 6 / (6 + 3) = 6 / 9  = 2/3 = 0.666666...
#   F1        = 2 * P * R / (P + R)
#             = 2 * (3/4) * (2/3) / (3/4 + 2/3)
#             = (2 * 1/2) / (9/12 + 8/12)
#             = 1 / (17/12)
#             = 12/17 = 0.7058823529...
#     cross-check via 2TP / (2TP + FP + FN) = 12 / (12 + 2 + 3) = 12/17  OK
#
#   answered  = TP + FP + FN + TN = 6 + 2 + 3 + 9 = 20
#   total     = answered + abstained = 20 + 5 = 25
#   coverage  = 20 / 25 = 0.8
TOY_TP, TOY_FP, TOY_FN, TOY_TN, TOY_ABSTAINED = 6, 2, 3, 9, 5
TOY_PRECISION = 0.75
TOY_RECALL = 2.0 / 3.0
TOY_F1 = 12.0 / 17.0
TOY_COVERAGE = 0.8


def _toy_pairs() -> list[tuple[str, str]]:
    """A pair list that reproduces the toy counts above exactly."""
    pairs: list[tuple[str, str]] = []
    pairs += [(MATCH, MATCH)] * TOY_TP  # 6 true positives
    pairs += [(NON_MATCH, MATCH)] * TOY_FP  # 2 false positives
    pairs += [(MATCH, NON_MATCH)] * TOY_FN  # 3 false negatives
    pairs += [(NON_MATCH, NON_MATCH)] * TOY_TN  # 9 true negatives
    pairs += [(MATCH, UNCERTAIN)] * 3  # abstentions (3 + 2 = 5)
    pairs += [(NON_MATCH, UNCERTAIN)] * 2
    # Gold-"uncertain" items: outside the binary question entirely.
    pairs += [(UNCERTAIN, MATCH), (UNCERTAIN, UNCERTAIN)]
    return pairs


def test_scores_from_counts_matches_hand_arithmetic() -> None:
    scores = scores_from_counts(
        tp=TOY_TP, fp=TOY_FP, fn=TOY_FN, tn=TOY_TN, abstained=TOY_ABSTAINED
    )
    assert scores.precision == pytest.approx(TOY_PRECISION)
    assert scores.recall == pytest.approx(TOY_RECALL)
    assert scores.f1 == pytest.approx(TOY_F1)
    assert scores.coverage == pytest.approx(TOY_COVERAGE)
    assert scores.n_answered == 20
    assert scores.n_total == 25


def test_scores_from_pairs_matches_the_same_hand_arithmetic() -> None:
    scores = scores_from_pairs(_toy_pairs())
    assert (scores.tp, scores.fp, scores.fn, scores.tn) == (
        TOY_TP,
        TOY_FP,
        TOY_FN,
        TOY_TN,
    )
    assert scores.abstained == TOY_ABSTAINED
    assert scores.excluded_gold_uncertain == 2
    assert scores.precision == pytest.approx(TOY_PRECISION)
    assert scores.recall == pytest.approx(TOY_RECALL)
    assert scores.f1 == pytest.approx(TOY_F1)
    assert scores.coverage == pytest.approx(TOY_COVERAGE)


def test_both_entry_points_agree() -> None:
    from_pairs = scores_from_pairs(_toy_pairs())
    from_counts = scores_from_counts(
        tp=from_pairs.tp,
        fp=from_pairs.fp,
        fn=from_pairs.fn,
        tn=from_pairs.tn,
        abstained=from_pairs.abstained,
    )
    assert from_pairs.f1 == from_counts.f1
    assert from_pairs.coverage == from_counts.coverage


# ---------------------------------------------------------------------------
# A second, independent hand check on a different matrix
# ---------------------------------------------------------------------------
# 10 items, gold-uncertain excluded (items 9-10):
#   (match, match) x 2                -> TP = 2
#   (match, non-match) x 1            -> FN = 1
#   (match, uncertain) x 1            -> abstained
#   (non-match, non-match) x 2        -> TN = 2
#   (non-match, match) x 1            -> FP = 1
#   (non-match, uncertain) x 1        -> abstained
#   precision = 2 / (2 + 1) = 2/3
#   recall    = 2 / (2 + 1) = 2/3
#   F1        = 2/3 (precision == recall)
#   answered  = 2 + 1 + 1 + 2 = 6, total = 8, coverage = 6/8 = 0.75
def test_second_hand_computed_matrix() -> None:
    pairs = [
        (MATCH, MATCH),
        (MATCH, MATCH),
        (MATCH, NON_MATCH),
        (MATCH, UNCERTAIN),
        (NON_MATCH, NON_MATCH),
        (NON_MATCH, NON_MATCH),
        (NON_MATCH, MATCH),
        (NON_MATCH, UNCERTAIN),
        (UNCERTAIN, UNCERTAIN),
        (UNCERTAIN, MATCH),
    ]
    scores = scores_from_pairs(pairs)
    assert (scores.tp, scores.fp, scores.fn, scores.tn) == (2, 1, 1, 2)
    assert scores.abstained == 2
    assert scores.excluded_gold_uncertain == 2
    assert scores.precision == pytest.approx(2.0 / 3.0)
    assert scores.recall == pytest.approx(2.0 / 3.0)
    assert scores.f1 == pytest.approx(2.0 / 3.0)
    assert scores.coverage == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Zero-denominator convention: documented as 0.0 everywhere in this module
# ---------------------------------------------------------------------------
def test_zero_denominators_return_zero_not_nan() -> None:
    # No predicted positives -> precision denominator is 0.
    assert precision_score(0, 0) == 0.0
    # No gold positives -> recall denominator is 0.
    assert recall_score(0, 0) == 0.0
    # Both zero -> F1 denominator is 0.
    assert f1_score(0, 0, 0) == 0.0
    # No items at all -> coverage denominator is 0.
    assert coverage_score(0, 0) == 0.0

    empty = scores_from_counts(0, 0, 0, 0)
    assert (empty.precision, empty.recall, empty.f1, empty.coverage) == (
        0.0,
        0.0,
        0.0,
        0.0,
    )

    # A model that never predicts "match": precision denominator is 0.
    never_positive = scores_from_pairs([(MATCH, NON_MATCH), (NON_MATCH, NON_MATCH)])
    assert never_positive.precision == 0.0
    assert never_positive.f1 == 0.0
    # Coverage is still well defined here: 2 answered out of 2.
    assert never_positive.coverage == 1.0

    # Everything abstained -> coverage 0, and no answered items at all.
    all_abstain = scores_from_pairs([(MATCH, UNCERTAIN), (NON_MATCH, UNCERTAIN)])
    assert all_abstain.coverage == 0.0
    assert all_abstain.n_answered == 0

    assert scores_from_pairs([]).coverage == 0.0


def test_unknown_label_is_rejected() -> None:
    with pytest.raises(ValueError):
        scores_from_pairs([("MATCH", MATCH)])
    with pytest.raises(ValueError):
        scores_from_pairs([(MATCH, "non match")])  # space, not hyphen


# ---------------------------------------------------------------------------
# Bootstrap determinism
# ---------------------------------------------------------------------------
def _repeated(pattern: list[tuple[str, str]], times: int) -> list[tuple[str, str]]:
    return pattern * times


# One 20-item block: 8 TP, 2 FP, 2 FN, 8 TN.
#   precision = 8 / 10 = 0.8, recall = 8 / 10 = 0.8, F1 = 0.8
BLOCK_20 = (
    [(MATCH, MATCH)] * 8
    + [(NON_MATCH, MATCH)] * 2
    + [(MATCH, NON_MATCH)] * 2
    + [(NON_MATCH, NON_MATCH)] * 8
)


def test_block_point_estimate_is_hand_checked() -> None:
    scores = scores_from_pairs(BLOCK_20)
    assert scores.precision == pytest.approx(0.8)
    assert scores.recall == pytest.approx(0.8)
    assert scores.f1 == pytest.approx(0.8)


def test_bootstrap_ci_is_deterministic_for_a_fixed_seed() -> None:
    first = bootstrap_ci(BLOCK_20, metric="f1", n_resamples=200, seed=DEFAULT_SEED)
    second = bootstrap_ci(BLOCK_20, metric="f1", n_resamples=200, seed=DEFAULT_SEED)
    # Strict equality, not approx: the same seed must reproduce the bounds exactly.
    assert first.lower == second.lower
    assert first.upper == second.upper
    assert first.point_estimate == second.point_estimate
    assert first.seed == DEFAULT_SEED == 42


def test_bootstrap_ci_brackets_the_point_estimate() -> None:
    result = bootstrap_ci(BLOCK_20, metric="f1", n_resamples=300, seed=DEFAULT_SEED)
    assert result.point_estimate == pytest.approx(0.8)
    assert result.lower <= result.point_estimate <= result.upper
    assert 0.0 <= result.lower <= result.upper <= 1.0
    assert result.n_items == 20


def test_bootstrap_ci_seed_is_actually_used() -> None:
    # Loose assertion only: two different seeds are *allowed* to coincide, so
    # we assert nothing about inequality. We assert instead that the seed is
    # recorded and that re-running with the alternative seed is itself stable.
    alt_a = bootstrap_ci(BLOCK_20, metric="f1", n_resamples=200, seed=7)
    alt_b = bootstrap_ci(BLOCK_20, metric="f1", n_resamples=200, seed=7)
    assert alt_a.seed == 7
    assert (alt_a.lower, alt_a.upper) == (alt_b.lower, alt_b.upper)


def test_larger_sample_yields_a_narrower_ci() -> None:
    # Same underlying rates (the 20-item block repeated), so the same point
    # estimate; only n changes. Bootstrap spread shrinks roughly like
    # 1/sqrt(n), so 400 items must give a clearly narrower interval than 20.
    small = bootstrap_ci(BLOCK_20, metric="f1", n_resamples=400, seed=DEFAULT_SEED)
    large = bootstrap_ci(
        _repeated(BLOCK_20, 20), metric="f1", n_resamples=400, seed=DEFAULT_SEED
    )
    assert small.n_items == 20
    assert large.n_items == 400
    assert small.point_estimate == pytest.approx(large.point_estimate)
    assert large.width < small.width


def test_bootstrap_rejects_bad_arguments() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci(BLOCK_20, metric="accuracy", n_resamples=10)
    with pytest.raises(ValueError):
        bootstrap_ci(BLOCK_20, n_resamples=0)
    with pytest.raises(ValueError):
        bootstrap_ci(BLOCK_20, n_resamples=10, confidence=1.0)


def test_bootstrap_on_empty_input_is_degenerate_not_an_error() -> None:
    result = bootstrap_ci([], n_resamples=10)
    assert result.n_items == 0
    assert (result.lower, result.upper) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# Paired bootstrap difference
# ---------------------------------------------------------------------------
GOLD = [MATCH] * 10 + [NON_MATCH] * 10
# Method A: 9/10 gold matches recovered, 1 false positive.
PRED_A = [MATCH] * 9 + [NON_MATCH] + [MATCH] + [NON_MATCH] * 9
# Method B: 5/10 gold matches recovered, 4 false positives.
PRED_B = [MATCH] * 5 + [NON_MATCH] * 5 + [MATCH] * 4 + [NON_MATCH] * 6


def test_paired_difference_point_estimates_are_hand_computed() -> None:
    # Method A: TP = 9, FN = 1, FP = 1, TN = 9
    #   precision = 9/10 = 0.9, recall = 9/10 = 0.9, F1 = 0.9
    # Method B: TP = 5, FN = 5, FP = 4, TN = 6
    #   precision = 5/9 = 0.5555..., recall = 5/10 = 0.5
    #   F1 = 2 * (5/9) * (1/2) / (5/9 + 1/2)
    #      = (5/9) / (10/18 + 9/18)
    #      = (5/9) / (19/18)
    #      = (5/9) * (18/19) = 90/171 = 10/19 = 0.5263157894...
    #   cross-check 2TP / (2TP + FP + FN) = 10 / (10 + 4 + 5) = 10/19  OK
    # difference (A - B) = 0.9 - 10/19 = (17.1 - 10)/19 = 7.1/19 = 0.373684210...
    result = paired_bootstrap_difference(
        GOLD, PRED_A, PRED_B, metric="f1", n_resamples=200, seed=DEFAULT_SEED
    )
    assert result.point_estimate_a == pytest.approx(0.9)
    assert result.point_estimate_b == pytest.approx(10.0 / 19.0)
    assert result.observed_difference == pytest.approx(0.9 - 10.0 / 19.0)
    assert result.n_items == 20


def test_paired_difference_is_deterministic_for_a_fixed_seed() -> None:
    first = paired_bootstrap_difference(
        GOLD, PRED_A, PRED_B, metric="f1", n_resamples=200, seed=DEFAULT_SEED
    )
    second = paired_bootstrap_difference(
        GOLD, PRED_A, PRED_B, metric="f1", n_resamples=200, seed=DEFAULT_SEED
    )
    assert first.lower == second.lower
    assert first.upper == second.upper


def test_pairing_is_real_identical_methods_give_a_degenerate_zero_interval() -> None:
    # THE point of "paired": both methods are scored on the SAME resampled
    # indices. If A and B are the same predictions, every replicate difference
    # must be exactly 0.0 and the interval must collapse onto zero. With
    # independent (unpaired) resampling this interval would be wide.
    result = paired_bootstrap_difference(
        GOLD, PRED_A, list(PRED_A), metric="f1", n_resamples=200, seed=DEFAULT_SEED
    )
    assert result.observed_difference == 0.0
    assert result.lower == 0.0
    assert result.upper == 0.0
    assert result.excludes_zero is False


def test_paired_difference_interval_brackets_the_observed_difference() -> None:
    result = paired_bootstrap_difference(
        GOLD, PRED_A, PRED_B, metric="f1", n_resamples=500, seed=DEFAULT_SEED
    )
    assert result.lower <= result.observed_difference <= result.upper
    # A is much better than B here, so the interval should sit above zero.
    assert result.lower > 0.0
    assert result.excludes_zero is True


def test_paired_difference_drops_gold_uncertain_from_both_methods() -> None:
    gold = [MATCH, NON_MATCH, UNCERTAIN, UNCERTAIN]
    pred_a = [MATCH, NON_MATCH, MATCH, NON_MATCH]
    pred_b = [MATCH, MATCH, NON_MATCH, MATCH]
    result = paired_bootstrap_difference(
        gold, pred_a, pred_b, metric="f1", n_resamples=20, seed=DEFAULT_SEED
    )
    assert result.n_items == 2  # the two gold-uncertain items are out of scope


def test_paired_difference_requires_equal_lengths() -> None:
    with pytest.raises(ValueError):
        paired_bootstrap_difference([MATCH], [MATCH], [MATCH, MATCH], n_resamples=10)
