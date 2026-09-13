"""Binary (match / non-match) classification metrics with paired bootstrap CIs.

Positive class is ``"match"``.

Scope of the binary evaluation
------------------------------
The binary view is defined on the *match / non-match subset of the gold
labels*. Items whose GOLD label is ``"uncertain"`` are outside the binary
question entirely and are excluded from every count; they are reported
separately as :attr:`BinaryScores.excluded_gold_uncertain` so nothing is
silently dropped.

Within that subset an item is ANSWERED when the predicted label is not an
abstention (by default ``"uncertain"``), and ABSTAINED otherwise::

    total    = tp + fp + fn + tn + abstained
    answered = tp + fp + fn + tn
    coverage = answered / total

Zero-denominator convention
---------------------------
Every metric in this module returns ``0.0`` when its denominator is zero
(no predicted positives, no gold positives, no items at all). This is a
deliberate, uniform choice for the binary/three-way/selective/cluster
modules; it is *not* the convention used by :mod:`strengthening.metrics.retrieval`,
which returns ``None`` for metrics that cannot be estimated without gold
retrieval annotations.

Bootstrap
---------
Confidence intervals use the non-parametric percentile bootstrap over
*items*: item indices are resampled WITH replacement, and the metric is
recomputed on the resampled multiset. Resampling is driven by
``random.Random(seed)`` so a given seed reproduces byte-identical bounds.
:func:`paired_bootstrap_difference` evaluates two methods on the SAME
resampled indices at every replicate -- that pairing is what makes the
difference interval a paired one.

No network access, no credentials, no model calls anywhere in this module.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from . import (
    ALLOWED_LABELS,
    DEFAULT_ABSTAIN_LABELS,
    DEFAULT_SEED,
    LABEL_MATCH,
    LABEL_NON_MATCH,
)

__all__ = [
    "BinaryScores",
    "BootstrapCI",
    "METRIC_NAMES",
    "PairedBootstrapDifference",
    "bootstrap_ci",
    "coverage_score",
    "f1_score",
    "paired_bootstrap_difference",
    "precision_score",
    "recall_score",
    "scores_from_counts",
    "scores_from_pairs",
]

#: Metric names accepted by the bootstrap helpers.
METRIC_NAMES: tuple[str, ...] = ("precision", "recall", "f1", "coverage")

# Per-item confusion cell codes used by the bootstrap inner loop.
_TP, _FP, _FN, _TN, _ABSTAIN = 0, 1, 2, 3, 4


# --------------------------------------------------------------------------
# Scalar metrics
# --------------------------------------------------------------------------
def precision_score(tp: int, fp: int) -> float:
    """``tp / (tp + fp)``; returns ``0.0`` when there are no predicted positives."""
    denominator = tp + fp
    return float(tp) / denominator if denominator > 0 else 0.0


def recall_score(tp: int, fn: int) -> float:
    """``tp / (tp + fn)``; returns ``0.0`` when there are no gold positives."""
    denominator = tp + fn
    return float(tp) / denominator if denominator > 0 else 0.0


def f1_score(tp: int, fp: int, fn: int) -> float:
    """Harmonic mean of precision and recall.

    Equivalent to ``2 * tp / (2 * tp + fp + fn)``. Returns ``0.0`` when
    precision and recall are both zero (including the all-zero-counts case).
    """
    precision = precision_score(tp, fp)
    recall = recall_score(tp, fn)
    total = precision + recall
    return (2.0 * precision * recall / total) if total > 0 else 0.0


def coverage_score(n_answered: int, n_total: int) -> float:
    """``answered / total``; returns ``0.0`` when there are no items at all."""
    return float(n_answered) / n_total if n_total > 0 else 0.0


# --------------------------------------------------------------------------
# Result container
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class BinaryScores:
    """Binary scores plus the counts they were derived from.

    ``excluded_gold_uncertain`` counts items removed *before* the binary
    evaluation because their gold label was ``"uncertain"``; it is not part
    of ``n_total`` and therefore does not affect coverage.
    """

    tp: int
    fp: int
    fn: int
    tn: int
    abstained: int = 0
    excluded_gold_uncertain: int = 0
    precision: float = field(init=False)
    recall: float = field(init=False)
    f1: float = field(init=False)
    coverage: float = field(init=False)

    def __post_init__(self) -> None:
        for name in ("tp", "fp", "fn", "tn", "abstained", "excluded_gold_uncertain"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative int, got {value!r}")
        object.__setattr__(self, "precision", precision_score(self.tp, self.fp))
        object.__setattr__(self, "recall", recall_score(self.tp, self.fn))
        object.__setattr__(self, "f1", f1_score(self.tp, self.fp, self.fn))
        object.__setattr__(
            self, "coverage", coverage_score(self.n_answered, self.n_total)
        )

    @property
    def n_answered(self) -> int:
        """Items in the binary subset that received a match/non-match prediction."""
        return self.tp + self.fp + self.fn + self.tn

    @property
    def n_total(self) -> int:
        """Items in the binary subset, answered or abstained."""
        return self.n_answered + self.abstained

    def to_dict(self) -> dict[str, float | int]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "abstained": self.abstained,
            "excluded_gold_uncertain": self.excluded_gold_uncertain,
            "n_answered": self.n_answered,
            "n_total": self.n_total,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "coverage": self.coverage,
        }


# --------------------------------------------------------------------------
# Entry point 1: explicit counts
# --------------------------------------------------------------------------
def scores_from_counts(
    tp: int,
    fp: int,
    fn: int,
    tn: int,
    abstained: int = 0,
    excluded_gold_uncertain: int = 0,
) -> BinaryScores:
    """Build :class:`BinaryScores` from an explicit confusion-matrix count input."""
    return BinaryScores(
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        abstained=abstained,
        excluded_gold_uncertain=excluded_gold_uncertain,
    )


# --------------------------------------------------------------------------
# Entry point 2: (gold, pred) pairs
# --------------------------------------------------------------------------
def _validate_label(label: str, role: str) -> str:
    if label not in ALLOWED_LABELS:
        raise ValueError(
            f"unknown {role} label {label!r}; allowed labels are {list(ALLOWED_LABELS)}"
        )
    return label


def _cell_code(
    gold: str, pred: str, abstain_labels: frozenset[str]
) -> int | None:
    """Confusion cell for one item, or ``None`` if the item is out of scope."""
    if gold not in (LABEL_MATCH, LABEL_NON_MATCH):
        return None
    if pred in abstain_labels:
        return _ABSTAIN
    if gold == LABEL_MATCH:
        return _TP if pred == LABEL_MATCH else _FN
    return _FP if pred == LABEL_MATCH else _TN


def _pair_codes(
    pairs: Iterable[tuple[str, str]],
    abstain_labels: frozenset[str] = DEFAULT_ABSTAIN_LABELS,
) -> tuple[list[int], int]:
    """Return (per-item cell codes for in-scope items, n gold-uncertain excluded)."""
    codes: list[int] = []
    excluded = 0
    for index, pair in enumerate(pairs):
        try:
            gold, pred = pair
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError(
                f"item {index}: expected a (gold, pred) 2-tuple, got {pair!r}"
            ) from exc
        _validate_label(gold, "gold")
        _validate_label(pred, "predicted")
        code = _cell_code(gold, pred, abstain_labels)
        if code is None:
            excluded += 1
        else:
            codes.append(code)
    return codes, excluded


def _scores_from_codes(codes: Sequence[int], excluded: int = 0) -> BinaryScores:
    tally = [0, 0, 0, 0, 0]
    for code in codes:
        tally[code] += 1
    return BinaryScores(
        tp=tally[_TP],
        fp=tally[_FP],
        fn=tally[_FN],
        tn=tally[_TN],
        abstained=tally[_ABSTAIN],
        excluded_gold_uncertain=excluded,
    )


def scores_from_pairs(
    pairs: Iterable[tuple[str, str]],
    abstain_labels: Iterable[str] = DEFAULT_ABSTAIN_LABELS,
) -> BinaryScores:
    """Build :class:`BinaryScores` from ``(gold_label, predicted_label)`` pairs.

    Only items whose gold label is ``"match"`` or ``"non-match"`` enter the
    binary evaluation; gold-``"uncertain"`` items are counted in
    ``excluded_gold_uncertain``. Predicted labels in ``abstain_labels``
    (default: just ``"uncertain"``) are abstentions and lower coverage.

    Raises ``ValueError`` for any label outside the protocol vocabulary.
    """
    codes, excluded = _pair_codes(pairs, frozenset(abstain_labels))
    return _scores_from_codes(codes, excluded)


# --------------------------------------------------------------------------
# Bootstrap machinery
# --------------------------------------------------------------------------
def _metric_from_tally(tally: Sequence[int], metric: str) -> float:
    tp, fp, fn, tn, abstained = tally
    if metric == "precision":
        return precision_score(tp, fp)
    if metric == "recall":
        return recall_score(tp, fn)
    if metric == "f1":
        return f1_score(tp, fp, fn)
    if metric == "coverage":
        answered = tp + fp + fn + tn
        return coverage_score(answered, answered + abstained)
    raise ValueError(f"unknown metric {metric!r}; expected one of {list(METRIC_NAMES)}")


def _check_metric(metric: str) -> str:
    if metric not in METRIC_NAMES:
        raise ValueError(
            f"unknown metric {metric!r}; expected one of {list(METRIC_NAMES)}"
        )
    return metric


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile of an already-sorted sequence.

    ``q`` is in [0, 100]. Matches the standard "linear" / type-7 definition,
    implemented here in pure Python so the result does not depend on any
    third-party interpolation default.
    """
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_values[0])
    position = (q / 100.0) * (n - 1)
    lower = int(position)
    if lower >= n - 1:
        return float(sorted_values[-1])
    frac = position - lower
    low_value = float(sorted_values[lower])
    high_value = float(sorted_values[lower + 1])
    return low_value + frac * (high_value - low_value)


@dataclass(frozen=True)
class BootstrapCI:
    """Percentile bootstrap interval for a single method's metric."""

    metric: str
    point_estimate: float
    lower: float
    upper: float
    confidence: float
    n_resamples: int
    seed: int
    n_items: int

    @property
    def width(self) -> float:
        return self.upper - self.lower

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "metric": self.metric,
            "point_estimate": self.point_estimate,
            "lower": self.lower,
            "upper": self.upper,
            "width": self.width,
            "confidence": self.confidence,
            "n_resamples": self.n_resamples,
            "seed": self.seed,
            "n_items": self.n_items,
        }


@dataclass(frozen=True)
class PairedBootstrapDifference:
    """Paired bootstrap interval for ``metric(a) - metric(b)``.

    Both methods are scored on the SAME resampled item indices at every
    replicate, so the interval reflects the paired difference rather than
    two independent intervals.
    """

    metric: str
    point_estimate_a: float
    point_estimate_b: float
    observed_difference: float
    lower: float
    upper: float
    confidence: float
    n_resamples: int
    seed: int
    n_items: int

    @property
    def width(self) -> float:
        return self.upper - self.lower

    @property
    def excludes_zero(self) -> bool:
        """True when the interval lies entirely above or entirely below zero."""
        return self.lower > 0.0 or self.upper < 0.0

    def to_dict(self) -> dict[str, float | int | str | bool]:
        return {
            "metric": self.metric,
            "point_estimate_a": self.point_estimate_a,
            "point_estimate_b": self.point_estimate_b,
            "observed_difference": self.observed_difference,
            "lower": self.lower,
            "upper": self.upper,
            "width": self.width,
            "excludes_zero": self.excludes_zero,
            "confidence": self.confidence,
            "n_resamples": self.n_resamples,
            "seed": self.seed,
            "n_items": self.n_items,
        }


def _check_bootstrap_args(n_resamples: int, confidence: float) -> tuple[float, float]:
    if not isinstance(n_resamples, int) or isinstance(n_resamples, bool) or n_resamples < 1:
        raise ValueError(f"n_resamples must be a positive int, got {n_resamples!r}")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must lie strictly in (0, 1), got {confidence!r}")
    alpha = 1.0 - confidence
    return 100.0 * (alpha / 2.0), 100.0 * (1.0 - alpha / 2.0)


def bootstrap_ci(
    pairs: Iterable[tuple[str, str]],
    metric: str = "f1",
    n_resamples: int = 10_000,
    confidence: float = 0.95,
    seed: int = DEFAULT_SEED,
    abstain_labels: Iterable[str] = DEFAULT_ABSTAIN_LABELS,
) -> BootstrapCI:
    """Percentile bootstrap CI for one metric over ``(gold, pred)`` pairs.

    Item indices are resampled with replacement (``random.Random(seed)``)
    and the metric is recomputed on each resampled multiset. The default
    ``n_resamples=10000`` and ``seed`` (the protocol seed, 42) make results
    reproducible; tests may lower ``n_resamples`` for speed.

    An empty input yields a degenerate ``0.0 / 0.0 / 0.0`` interval rather
    than an error, consistent with the module's zero-denominator convention.
    """
    _check_metric(metric)
    low_q, high_q = _check_bootstrap_args(n_resamples, confidence)
    codes, excluded = _pair_codes(pairs, frozenset(abstain_labels))
    n = len(codes)
    point = _metric_from_tally(_tally(codes), metric)

    if n == 0:
        return BootstrapCI(
            metric=metric,
            point_estimate=point,
            lower=0.0,
            upper=0.0,
            confidence=confidence,
            n_resamples=n_resamples,
            seed=seed,
            n_items=0,
        )

    rng = random.Random(seed)
    population = range(n)
    replicates: list[float] = []
    for _ in range(n_resamples):
        indices = rng.choices(population, k=n)
        tally = [0, 0, 0, 0, 0]
        for index in indices:
            tally[codes[index]] += 1
        replicates.append(_metric_from_tally(tally, metric))
    replicates.sort()

    return BootstrapCI(
        metric=metric,
        point_estimate=point,
        lower=_percentile(replicates, low_q),
        upper=_percentile(replicates, high_q),
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
        n_items=n,
    )


def _tally(codes: Sequence[int]) -> list[int]:
    tally = [0, 0, 0, 0, 0]
    for code in codes:
        tally[code] += 1
    return tally


def paired_bootstrap_difference(
    gold: Sequence[str],
    pred_a: Sequence[str],
    pred_b: Sequence[str],
    metric: str = "f1",
    n_resamples: int = 10_000,
    confidence: float = 0.95,
    seed: int = DEFAULT_SEED,
    abstain_labels: Iterable[str] = DEFAULT_ABSTAIN_LABELS,
) -> PairedBootstrapDifference:
    """Paired bootstrap CI for ``metric(pred_a) - metric(pred_b)``.

    ``gold``, ``pred_a`` and ``pred_b`` must be equal-length and aligned
    item-by-item. At each replicate one set of item indices is drawn with
    replacement and BOTH methods are scored on exactly those indices; the
    replicate value is the difference of the two metric values. The reported
    interval is the percentile interval of that difference distribution.

    Items whose gold label is ``"uncertain"`` are dropped from both methods
    together, so the pairing is preserved.
    """
    _check_metric(metric)
    low_q, high_q = _check_bootstrap_args(n_resamples, confidence)
    gold = list(gold)
    pred_a = list(pred_a)
    pred_b = list(pred_b)
    if not (len(gold) == len(pred_a) == len(pred_b)):
        raise ValueError(
            "gold, pred_a and pred_b must have equal length; got "
            f"{len(gold)}, {len(pred_a)}, {len(pred_b)}"
        )

    abstain = frozenset(abstain_labels)
    codes_a: list[int] = []
    codes_b: list[int] = []
    for gold_label, label_a, label_b in zip(gold, pred_a, pred_b):
        _validate_label(gold_label, "gold")
        _validate_label(label_a, "predicted")
        _validate_label(label_b, "predicted")
        code_a = _cell_code(gold_label, label_a, abstain)
        code_b = _cell_code(gold_label, label_b, abstain)
        if code_a is None or code_b is None:
            # gold == "uncertain": out of scope for BOTH methods.
            continue
        codes_a.append(code_a)
        codes_b.append(code_b)

    n = len(codes_a)
    point_a = _metric_from_tally(_tally(codes_a), metric)
    point_b = _metric_from_tally(_tally(codes_b), metric)
    observed = point_a - point_b

    if n == 0:
        return PairedBootstrapDifference(
            metric=metric,
            point_estimate_a=point_a,
            point_estimate_b=point_b,
            observed_difference=observed,
            lower=0.0,
            upper=0.0,
            confidence=confidence,
            n_resamples=n_resamples,
            seed=seed,
            n_items=0,
        )

    rng = random.Random(seed)
    population = range(n)
    replicates: list[float] = []
    for _ in range(n_resamples):
        indices = rng.choices(population, k=n)
        tally_a = [0, 0, 0, 0, 0]
        tally_b = [0, 0, 0, 0, 0]
        for index in indices:
            tally_a[codes_a[index]] += 1
            tally_b[codes_b[index]] += 1
        replicates.append(
            _metric_from_tally(tally_a, metric) - _metric_from_tally(tally_b, metric)
        )
    replicates.sort()

    return PairedBootstrapDifference(
        metric=metric,
        point_estimate_a=point_a,
        point_estimate_b=point_b,
        observed_difference=observed,
        lower=_percentile(replicates, low_q),
        upper=_percentile(replicates, high_q),
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
        n_items=n,
    )
