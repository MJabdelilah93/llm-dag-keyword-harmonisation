"""Tests for strengthening.metrics.three_way.

The 3x3 example below is worked out by hand in comments before any
assertion is made; nothing here was read back out of the implementation.
"""

from __future__ import annotations

import pytest

from strengthening.metrics.three_way import (
    CLASS_ORDER,
    three_way_scores,
    three_way_scores_from_labels,
)

MATCH = "match"
NON_MATCH = "non-match"
UNCERTAIN = "uncertain"

# ---------------------------------------------------------------------------
# Hand-constructed 10-item example
# ---------------------------------------------------------------------------
#  #   gold        predicted
#  1   match       match
#  2   match       match
#  3   match       non-match
#  4   match       uncertain
#  5   non-match   non-match
#  6   non-match   non-match
#  7   non-match   match
#  8   non-match   uncertain
#  9   uncertain   uncertain
# 10   uncertain   match
#
# Confusion matrix, rows = gold, cols = predicted, order (match, non-match,
# uncertain):
#
#                  pred match   pred non-match   pred uncertain   row sum
#   gold match          2             1                1             4
#   gold non-match      1             2                1             4
#   gold uncertain      1             0                1             2
#   col sum             4             3                3            10
#
# accuracy = (2 + 2 + 1) / 10 = 5/10 = 0.5
#
# match:      TP = 2, FP = col(4) - 2 = 2, FN = row(4) - 2 = 2
#             P = 2/4 = 0.5 ; R = 2/4 = 0.5 ; F1 = 0.5
# non-match:  TP = 2, FP = col(3) - 2 = 1, FN = row(4) - 2 = 2
#             P = 2/3 = 0.6666... ; R = 2/4 = 0.5
#             F1 = 2*(2/3)*(1/2) / (2/3 + 1/2) = (2/3) / (7/6)
#                = (2/3)*(6/7) = 12/21 = 4/7 = 0.5714285714...
# uncertain:  TP = 1, FP = col(3) - 1 = 2, FN = row(2) - 1 = 1
#             P = 1/3 = 0.3333... ; R = 1/2 = 0.5
#             F1 = 2*(1/3)*(1/2) / (1/3 + 1/2) = (1/3) / (5/6)
#                = (1/3)*(6/5) = 6/15 = 2/5 = 0.4
#
# macro precision = (1/2 + 2/3 + 1/3) / 3 = (1/2 + 1) / 3 = 1.5/3 = 0.5
# macro recall    = (1/2 + 1/2 + 1/2) / 3 = 0.5
# macro F1        = (1/2 + 4/7 + 2/5) / 3
#                 = (35/70 + 40/70 + 28/70) / 3
#                 = (103/70) / 3 = 103/210 = 0.4904761904...
PAIRS: list[tuple[str, str]] = [
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

EXPECTED_MATRIX = (
    (2, 1, 1),
    (1, 2, 1),
    (1, 0, 1),
)


def test_class_order_is_the_documented_protocol_order() -> None:
    assert CLASS_ORDER == (MATCH, NON_MATCH, UNCERTAIN)


def test_confusion_matrix_rows_are_gold_and_columns_are_predicted() -> None:
    result = three_way_scores(PAIRS)
    assert result.confusion_matrix == EXPECTED_MATRIX
    assert result.n_items == 10
    # Row sums are gold supports; column sums are prediction counts.
    assert [sum(row) for row in result.confusion_matrix] == [4, 4, 2]
    assert [
        sum(row[j] for row in result.confusion_matrix) for j in range(3)
    ] == [4, 3, 3]
    # Explicit orientation check: gold uncertain / predicted non-match is 0,
    # while gold uncertain / predicted match is 1. A transposed matrix would
    # fail this.
    assert result.matrix_cell(UNCERTAIN, NON_MATCH) == 0
    assert result.matrix_cell(UNCERTAIN, MATCH) == 1


def test_accuracy_is_hand_computed() -> None:
    assert three_way_scores(PAIRS).accuracy == pytest.approx(0.5)


def test_per_class_scores_are_hand_computed() -> None:
    per_class = three_way_scores(PAIRS).per_class

    match = per_class[MATCH]
    assert (match.tp, match.fp, match.fn, match.support) == (2, 2, 2, 4)
    assert match.precision == pytest.approx(0.5)
    assert match.recall == pytest.approx(0.5)
    assert match.f1 == pytest.approx(0.5)

    non_match = per_class[NON_MATCH]
    assert (non_match.tp, non_match.fp, non_match.fn, non_match.support) == (2, 1, 2, 4)
    assert non_match.precision == pytest.approx(2.0 / 3.0)
    assert non_match.recall == pytest.approx(0.5)
    assert non_match.f1 == pytest.approx(4.0 / 7.0)

    uncertain = per_class[UNCERTAIN]
    assert (uncertain.tp, uncertain.fp, uncertain.fn, uncertain.support) == (1, 2, 1, 2)
    assert uncertain.precision == pytest.approx(1.0 / 3.0)
    assert uncertain.recall == pytest.approx(0.5)
    assert uncertain.f1 == pytest.approx(0.4)


def test_macro_averages_are_hand_computed() -> None:
    result = three_way_scores(PAIRS)
    assert result.macro_precision == pytest.approx(0.5)
    assert result.macro_recall == pytest.approx(0.5)
    assert result.macro_f1 == pytest.approx(103.0 / 210.0)


def test_from_labels_matches_from_pairs() -> None:
    gold = [g for g, _ in PAIRS]
    predicted = [p for _, p in PAIRS]
    assert three_way_scores_from_labels(gold, predicted).to_dict() == three_way_scores(
        PAIRS
    ).to_dict()


def test_perfect_prediction_scores_one_everywhere() -> None:
    pairs = [(MATCH, MATCH), (NON_MATCH, NON_MATCH), (UNCERTAIN, UNCERTAIN)]
    result = three_way_scores(pairs)
    assert result.accuracy == pytest.approx(1.0)
    assert result.macro_f1 == pytest.approx(1.0)
    assert result.confusion_matrix == ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def test_absent_class_gets_zero_not_nan() -> None:
    # No item is gold-"uncertain" and none is predicted "uncertain", so that
    # class has a zero denominator for both precision and recall.
    pairs = [(MATCH, MATCH), (NON_MATCH, NON_MATCH)]
    uncertain = three_way_scores(pairs).per_class[UNCERTAIN]
    assert (uncertain.precision, uncertain.recall, uncertain.f1) == (0.0, 0.0, 0.0)
    assert uncertain.support == 0
    # macro F1 = (1 + 1 + 0) / 3 = 2/3
    assert three_way_scores(pairs).macro_f1 == pytest.approx(2.0 / 3.0)


def test_empty_input_is_all_zero() -> None:
    result = three_way_scores([])
    assert result.n_items == 0
    assert result.accuracy == 0.0
    assert result.macro_f1 == 0.0
    assert result.confusion_matrix == ((0, 0, 0), (0, 0, 0), (0, 0, 0))


def test_unknown_labels_are_rejected() -> None:
    with pytest.raises(ValueError):
        three_way_scores([("Match", MATCH)])
    with pytest.raises(ValueError):
        three_way_scores([(MATCH, "non match")])  # space instead of hyphen
    with pytest.raises(ValueError):
        three_way_scores_from_labels([MATCH], [MATCH, MATCH])
