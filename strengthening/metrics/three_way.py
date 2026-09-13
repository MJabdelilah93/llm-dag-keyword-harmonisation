"""Three-way (match / non-match / uncertain) classification metrics.

The ``"uncertain"`` label is treated as a genuine third class here, not as an
abstention. (For the abstention view -- coverage, selective risk -- see
:mod:`strengthening.metrics.selective`.)

Matrix ordering (stable and documented)
---------------------------------------
:data:`CLASS_ORDER` is ``("match", "non-match", "uncertain")`` and fixes the
ordering of both axes of the 3x3 confusion matrix::

    confusion_matrix[i][j] = number of items with
        gold      == CLASS_ORDER[i]      (ROWS  = gold / true label)
        predicted == CLASS_ORDER[j]      (COLS  = predicted label)

So a row sum is a class's gold support and a column sum is the number of
times that class was predicted.

Per-class counts follow the usual one-vs-rest reading of that matrix::

    tp(c) = M[c][c]
    fp(c) = column_sum(c) - tp(c)
    fn(c) = row_sum(c)    - tp(c)

Zero-denominator convention: ``0.0`` (see the package docstring).
Pure computation; no network access anywhere in this module.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from . import LABEL_MATCH, LABEL_NON_MATCH, LABEL_UNCERTAIN

__all__ = [
    "CLASS_ORDER",
    "ClassScores",
    "ThreeWayResult",
    "three_way_scores",
    "three_way_scores_from_labels",
]

#: Fixed ordering of the 3x3 confusion-matrix rows (gold) and columns (pred).
CLASS_ORDER: tuple[str, str, str] = (LABEL_MATCH, LABEL_NON_MATCH, LABEL_UNCERTAIN)

_CLASS_INDEX: dict[str, int] = {label: i for i, label in enumerate(CLASS_ORDER)}


@dataclass(frozen=True)
class ClassScores:
    """One-vs-rest precision / recall / F1 for a single class."""

    label: str
    tp: int
    fp: int
    fn: int
    support: int
    precision: float
    recall: float
    f1: float

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "label": self.label,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "support": self.support,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass(frozen=True)
class ThreeWayResult:
    """Full three-way result: 3x3 matrix, per-class scores and macro averages."""

    class_order: tuple[str, ...]
    confusion_matrix: tuple[tuple[int, ...], ...]
    per_class: dict[str, ClassScores]
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    n_items: int

    def matrix_cell(self, gold: str, predicted: str) -> int:
        """Count of items with the given gold and predicted labels."""
        return self.confusion_matrix[_class_index(gold)][_class_index(predicted)]

    def to_dict(self) -> dict[str, object]:
        return {
            "class_order": list(self.class_order),
            "confusion_matrix": [list(row) for row in self.confusion_matrix],
            "per_class": {k: v.to_dict() for k, v in self.per_class.items()},
            "accuracy": self.accuracy,
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "n_items": self.n_items,
        }


def _class_index(label: str) -> int:
    try:
        return _CLASS_INDEX[label]
    except KeyError as exc:
        raise ValueError(
            f"unknown label {label!r}; allowed labels are {list(CLASS_ORDER)}"
        ) from exc


def _safe_ratio(numerator: int, denominator: int) -> float:
    """``numerator / denominator``, or ``0.0`` when the denominator is zero."""
    return float(numerator) / denominator if denominator > 0 else 0.0


def _harmonic(precision: float, recall: float) -> float:
    total = precision + recall
    return (2.0 * precision * recall / total) if total > 0 else 0.0


def three_way_scores(pairs: Iterable[tuple[str, str]]) -> ThreeWayResult:
    """Compute the three-way result from ``(gold_label, predicted_label)`` pairs.

    Raises ``ValueError`` for any label outside
    ``("match", "non-match", "uncertain")``. An empty input yields an
    all-zero matrix with all metrics at ``0.0``.
    """
    matrix = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    n_items = 0
    for index, pair in enumerate(pairs):
        try:
            gold, predicted = pair
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"item {index}: expected a (gold, pred) 2-tuple, got {pair!r}"
            ) from exc
        matrix[_class_index(gold)][_class_index(predicted)] += 1
        n_items += 1

    correct = sum(matrix[i][i] for i in range(3))
    accuracy = _safe_ratio(correct, n_items)

    per_class: dict[str, ClassScores] = {}
    for i, label in enumerate(CLASS_ORDER):
        tp = matrix[i][i]
        row_sum = sum(matrix[i])
        col_sum = sum(matrix[r][i] for r in range(3))
        fp = col_sum - tp
        fn = row_sum - tp
        precision = _safe_ratio(tp, tp + fp)
        recall = _safe_ratio(tp, tp + fn)
        per_class[label] = ClassScores(
            label=label,
            tp=tp,
            fp=fp,
            fn=fn,
            support=row_sum,
            precision=precision,
            recall=recall,
            f1=_harmonic(precision, recall),
        )

    n_classes = len(CLASS_ORDER)
    macro_precision = sum(s.precision for s in per_class.values()) / n_classes
    macro_recall = sum(s.recall for s in per_class.values()) / n_classes
    macro_f1 = sum(s.f1 for s in per_class.values()) / n_classes

    return ThreeWayResult(
        class_order=CLASS_ORDER,
        confusion_matrix=tuple(tuple(row) for row in matrix),
        per_class=per_class,
        accuracy=accuracy,
        macro_precision=macro_precision,
        macro_recall=macro_recall,
        macro_f1=macro_f1,
        n_items=n_items,
    )


def three_way_scores_from_labels(
    gold: Sequence[str], predicted: Sequence[str]
) -> ThreeWayResult:
    """Same as :func:`three_way_scores` for two aligned equal-length sequences."""
    if len(gold) != len(predicted):
        raise ValueError(
            f"gold and predicted must have equal length; got {len(gold)} and {len(predicted)}"
        )
    return three_way_scores(zip(gold, predicted))
