"""Selective prediction: coverage, selective risk, risk-coverage curves, AURC.

This is the PRIMARY selective-prediction path for the protocol. It is built
entirely on abstention thresholds over the model's own RAW, SELF-REPORTED
confidence scores. No calibration procedure is applied and no calibration
guarantee is claimed.

This module deliberately does NOT import
:mod:`strengthening.metrics.conformal_prediction`. That module is an
experimental, opt-in scaffold and is not wired into anything here; see
``test_metrics_selective.py`` for the assertion that enforces the separation.

Core definitions
----------------
An item is ANSWERED at threshold ``t`` when::

    confidence >= t   AND   predicted_label not in abstain_labels

and ABSTAINED otherwise. Then::

    coverage       = n_answered / n_total
    selective_risk = n_errors_among_answered / n_answered

Abstentions are excluded from BOTH the numerator and the denominator of the
selective risk -- an abstention is neither a hit nor a miss.

AURC integration convention
---------------------------
:func:`aurc_from_curve` is the raw (un-normalised) trapezoidal integral of
risk with respect to coverage::

    AURC = sum_i  0.5 * (r_i + r_{i+1}) * (c_{i+1} - c_i)

over the observed points sorted by ascending coverage. There is NO
extrapolation: the integral spans only ``[min(coverage), max(coverage)]``.
When the curve is produced by :func:`risk_coverage_curve` the upper end is
always coverage ``1.0``, while the lower end is the smallest coverage
actually achievable on the data (the top confidence tier) -- the region
below that is not observed and is not invented. Fewer than two points means
a zero-width span, for which the area is ``0.0``.

Zero-denominator convention: ``0.0`` (see the package docstring). The single
exception is :func:`coverage_at_target_precision`, which returns ``None`` for
targets that are not estimable from the data -- it never fabricates a number.

Pure computation; no network access anywhere in this module.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from . import DEFAULT_ABSTAIN_LABELS, LABEL_MATCH, LABEL_UNCERTAIN
from .three_way import ClassScores, three_way_scores

__all__ = [
    "PrecisionOperatingPoint",
    "SelectiveReport",
    "SensitivityStep",
    "SweepPoint",
    "aurc",
    "aurc_from_curve",
    "coverage_at_target_precision",
    "coverage_from_counts",
    "coverage_score",
    "precision_operating_points",
    "risk_coverage_curve",
    "selective_prediction_report",
    "selective_risk",
    "selective_risk_from_counts",
    "threshold_sensitivity",
    "threshold_sweep",
    "uncertain_class_scores",
]

#: Tolerance used when comparing a computed precision against a target, so
#: that e.g. 2/3 counts as reaching a target of exactly 2/3.
PRECISION_TOLERANCE = 1e-12


# --------------------------------------------------------------------------
# Coverage and selective risk
# --------------------------------------------------------------------------
def coverage_from_counts(n_answered: int, n_total: int) -> float:
    """``answered / total``; ``0.0`` when there are no items."""
    if n_answered < 0 or n_total < 0:
        raise ValueError("counts must be non-negative")
    if n_answered > n_total:
        raise ValueError(
            f"n_answered ({n_answered}) cannot exceed n_total ({n_total})"
        )
    return float(n_answered) / n_total if n_total > 0 else 0.0


def coverage_score(answered: Sequence[bool]) -> float:
    """Fraction of items that were answered (i.e. not abstained on)."""
    answered = list(answered)
    return coverage_from_counts(sum(1 for a in answered if a), len(answered))


def selective_risk_from_counts(n_errors: int, n_answered: int) -> float:
    """``errors_among_answered / answered``; ``0.0`` when nothing was answered.

    Risk at zero coverage is genuinely undefined; ``0.0`` is returned for
    consistency with the module's zero-denominator convention, and callers
    that care should check ``coverage > 0`` first.
    """
    if n_errors < 0 or n_answered < 0:
        raise ValueError("counts must be non-negative")
    if n_errors > n_answered:
        raise ValueError(
            f"n_errors ({n_errors}) cannot exceed n_answered ({n_answered})"
        )
    return float(n_errors) / n_answered if n_answered > 0 else 0.0


def selective_risk(answered: Sequence[bool], correct: Sequence[bool]) -> float:
    """Error rate among answered items only; abstentions excluded from both terms."""
    answered = list(answered)
    correct = list(correct)
    if len(answered) != len(correct):
        raise ValueError(
            f"answered and correct must have equal length; got {len(answered)} and {len(correct)}"
        )
    n_answered = 0
    n_errors = 0
    for is_answered, is_correct in zip(answered, correct):
        if is_answered:
            n_answered += 1
            if not is_correct:
                n_errors += 1
    return selective_risk_from_counts(n_errors, n_answered)


# --------------------------------------------------------------------------
# Threshold sweep / risk-coverage curve
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SweepPoint:
    """Coverage and selective risk at a single abstention threshold."""

    threshold: float
    n_answered: int
    n_total: int
    n_errors: int
    coverage: float
    risk: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "threshold": self.threshold,
            "n_answered": self.n_answered,
            "n_total": self.n_total,
            "n_errors": self.n_errors,
            "coverage": self.coverage,
            "risk": self.risk,
        }


def _default_thresholds(confidences: Sequence[float]) -> list[float]:
    """Unique confidence values, descending: every attainable operating point."""
    return sorted({float(c) for c in confidences}, reverse=True)


def _check_aligned(
    confidences: Sequence[float], other: Sequence[object], other_name: str
) -> None:
    if len(confidences) != len(other):
        raise ValueError(
            f"confidences and {other_name} must have equal length; "
            f"got {len(confidences)} and {len(other)}"
        )


def threshold_sweep(
    confidences: Sequence[float],
    correct: Sequence[bool],
    thresholds: Iterable[float] | None = None,
) -> list[SweepPoint]:
    """Sweep an abstention threshold and report coverage and risk at each value.

    An item is answered at threshold ``t`` when ``confidence >= t``. When
    ``thresholds`` is ``None`` the sweep uses every unique confidence value,
    descending -- i.e. every distinct operating point the data can express,
    ending at coverage 1.0.

    Returns points in the order the thresholds were swept (descending
    threshold / ascending coverage for the default).
    """
    confidences = [float(c) for c in confidences]
    correct = [bool(c) for c in correct]
    _check_aligned(confidences, correct, "correct")

    grid = (
        _default_thresholds(confidences)
        if thresholds is None
        else [float(t) for t in thresholds]
    )
    n_total = len(confidences)
    points: list[SweepPoint] = []
    for threshold in grid:
        n_answered = 0
        n_errors = 0
        for confidence, is_correct in zip(confidences, correct):
            if confidence >= threshold:
                n_answered += 1
                if not is_correct:
                    n_errors += 1
        points.append(
            SweepPoint(
                threshold=threshold,
                n_answered=n_answered,
                n_total=n_total,
                n_errors=n_errors,
                coverage=coverage_from_counts(n_answered, n_total),
                risk=selective_risk_from_counts(n_errors, n_answered),
            )
        )
    return points


def risk_coverage_curve(
    confidences: Sequence[float],
    correct: Sequence[bool],
    thresholds: Iterable[float] | None = None,
) -> list[tuple[float, float]]:
    """``(coverage, risk)`` points sorted by ascending coverage.

    Points with zero coverage are dropped (risk is undefined there and is not
    invented). Duplicate coverages keep their first occurrence.
    """
    points = threshold_sweep(confidences, correct, thresholds)
    seen: set[float] = set()
    curve: list[tuple[float, float]] = []
    for point in sorted(points, key=lambda p: p.coverage):
        if point.coverage <= 0.0 or point.coverage in seen:
            continue
        seen.add(point.coverage)
        curve.append((point.coverage, point.risk))
    return curve


def aurc_from_curve(points: Sequence[tuple[float, float]]) -> float:
    """Trapezoidal area under a risk-coverage curve.

    ``points`` are ``(coverage, risk)`` pairs, in any order; they are sorted
    by coverage before integrating. See the module docstring for the exact
    integration convention (raw area, no extrapolation). Fewer than two
    distinct points spans zero width and returns ``0.0``.
    """
    ordered = sorted((float(c), float(r)) for c, r in points)
    if len(ordered) < 2:
        return 0.0
    area = 0.0
    for (c0, r0), (c1, r1) in zip(ordered, ordered[1:]):
        area += 0.5 * (r0 + r1) * (c1 - c0)
    return area


def aurc(
    confidences: Sequence[float],
    correct: Sequence[bool],
    thresholds: Iterable[float] | None = None,
) -> float:
    """Area under the risk-coverage curve of the given per-item data."""
    return aurc_from_curve(risk_coverage_curve(confidences, correct, thresholds))


# --------------------------------------------------------------------------
# Threshold sensitivity
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SensitivityStep:
    """Change in coverage and risk between two consecutive thresholds."""

    threshold_from: float
    threshold_to: float
    delta_threshold: float
    delta_coverage: float
    delta_risk: float
    d_coverage_d_threshold: float | None
    d_risk_d_threshold: float | None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "threshold_from": self.threshold_from,
            "threshold_to": self.threshold_to,
            "delta_threshold": self.delta_threshold,
            "delta_coverage": self.delta_coverage,
            "delta_risk": self.delta_risk,
            "d_coverage_d_threshold": self.d_coverage_d_threshold,
            "d_risk_d_threshold": self.d_risk_d_threshold,
        }


def threshold_sensitivity(
    confidences: Sequence[float],
    correct: Sequence[bool],
    thresholds: Iterable[float] | None = None,
) -> list[SensitivityStep]:
    """Change in risk and coverage per unit change in threshold.

    Consecutive sweep points are differenced. The per-unit rates are ``None``
    when two consecutive thresholds are identical (division by zero is not
    papered over with a fabricated slope).
    """
    points = threshold_sweep(confidences, correct, thresholds)
    steps: list[SensitivityStep] = []
    for first, second in zip(points, points[1:]):
        delta_threshold = second.threshold - first.threshold
        delta_coverage = second.coverage - first.coverage
        delta_risk = second.risk - first.risk
        if delta_threshold == 0.0:
            slope_coverage: float | None = None
            slope_risk: float | None = None
        else:
            slope_coverage = delta_coverage / delta_threshold
            slope_risk = delta_risk / delta_threshold
        steps.append(
            SensitivityStep(
                threshold_from=first.threshold,
                threshold_to=second.threshold,
                delta_threshold=delta_threshold,
                delta_coverage=delta_coverage,
                delta_risk=delta_risk,
                d_coverage_d_threshold=slope_coverage,
                d_risk_d_threshold=slope_risk,
            )
        )
    return steps


# --------------------------------------------------------------------------
# Uncertain-class scores (delegated to three_way)
# --------------------------------------------------------------------------
def uncertain_class_scores(pairs: Iterable[tuple[str, str]]) -> ClassScores:
    """Precision / recall / F1 for the ``"uncertain"`` class.

    This is a thin delegation to :func:`strengthening.metrics.three_way.three_way_scores`
    -- the per-class arithmetic lives there and is deliberately not
    duplicated here.
    """
    return three_way_scores(pairs).per_class[LABEL_UNCERTAIN]


# --------------------------------------------------------------------------
# Coverage at a target match-precision
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PrecisionOperatingPoint:
    """Coverage and match-precision at one abstention threshold.

    ``match_precision`` is ``None`` when no answered item was predicted
    ``"match"`` at this threshold -- precision is not estimable there and no
    value is invented.
    """

    threshold: float
    n_total: int
    n_answered: int
    coverage: float
    n_predicted_match: int
    n_true_positive: int
    match_precision: float | None

    def to_dict(self) -> dict[str, float | int | None]:
        return {
            "threshold": self.threshold,
            "n_total": self.n_total,
            "n_answered": self.n_answered,
            "coverage": self.coverage,
            "n_predicted_match": self.n_predicted_match,
            "n_true_positive": self.n_true_positive,
            "match_precision": self.match_precision,
        }


def precision_operating_points(
    confidences: Sequence[float],
    gold_labels: Sequence[str],
    pred_labels: Sequence[str],
    thresholds: Iterable[float] | None = None,
    abstain_labels: Iterable[str] = DEFAULT_ABSTAIN_LABELS,
) -> list[PrecisionOperatingPoint]:
    """Match-precision and coverage at each abstention threshold.

    An item is answered when ``confidence >= threshold`` AND its predicted
    label is not an abstention. Match-precision is computed over answered
    items predicted ``"match"``.
    """
    confidences = [float(c) for c in confidences]
    gold_labels = list(gold_labels)
    pred_labels = list(pred_labels)
    _check_aligned(confidences, gold_labels, "gold_labels")
    _check_aligned(confidences, pred_labels, "pred_labels")
    abstain = frozenset(abstain_labels)

    grid = (
        _default_thresholds(confidences)
        if thresholds is None
        else [float(t) for t in thresholds]
    )
    n_total = len(confidences)
    points: list[PrecisionOperatingPoint] = []
    for threshold in grid:
        n_answered = 0
        n_predicted_match = 0
        n_true_positive = 0
        for confidence, gold, pred in zip(confidences, gold_labels, pred_labels):
            if confidence < threshold or pred in abstain:
                continue
            n_answered += 1
            if pred == LABEL_MATCH:
                n_predicted_match += 1
                if gold == LABEL_MATCH:
                    n_true_positive += 1
        precision = (
            float(n_true_positive) / n_predicted_match
            if n_predicted_match > 0
            else None
        )
        points.append(
            PrecisionOperatingPoint(
                threshold=threshold,
                n_total=n_total,
                n_answered=n_answered,
                coverage=coverage_from_counts(n_answered, n_total),
                n_predicted_match=n_predicted_match,
                n_true_positive=n_true_positive,
                match_precision=precision,
            )
        )
    return points


def coverage_at_target_precision(
    confidences: Sequence[float],
    gold_labels: Sequence[str],
    pred_labels: Sequence[str],
    targets: float | Iterable[float],
    thresholds: Iterable[float] | None = None,
    abstain_labels: Iterable[str] = DEFAULT_ABSTAIN_LABELS,
    min_predicted_matches: int = 1,
) -> dict[float, float | None]:
    """Highest achievable coverage at each target match-precision level.

    For every target, the answer is the maximum coverage over all operating
    points whose match-precision reaches the target with at least
    ``min_predicted_matches`` predicted matches behind the estimate.

    Returns a dict keyed by the requested targets. A target maps to ``None``
    -- never to a fabricated number -- whenever it is not estimable from the
    data, i.e. when

    * no operating point reaches that precision at all, or
    * every operating point that would reach it rests on fewer than
      ``min_predicted_matches`` predicted matches, or
    * there are no items / no operating points to begin with.

    ``targets`` accepts a single float or an iterable of floats; the return
    value is always a dict.
    """
    if isinstance(targets, (int, float)) and not isinstance(targets, bool):
        target_list = [float(targets)]
    else:
        target_list = [float(t) for t in targets]  # type: ignore[union-attr]

    points = precision_operating_points(
        confidences, gold_labels, pred_labels, thresholds, abstain_labels
    )

    result: dict[float, float | None] = {}
    for target in target_list:
        best: float | None = None
        for point in points:
            if point.match_precision is None:
                continue
            if point.n_predicted_match < min_predicted_matches:
                continue
            if point.coverage <= 0.0:
                continue
            if point.match_precision + PRECISION_TOLERANCE >= target:
                if best is None or point.coverage > best:
                    best = point.coverage
        result[target] = best
    return result


# --------------------------------------------------------------------------
# Primary selective-prediction API
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SelectiveReport:
    """Primary selective-prediction summary at one operating threshold.

    ``conformal_prediction_used`` is always False: the conformal scaffold in
    :mod:`strengthening.metrics.conformal_prediction` is opt-in only and is
    never reached from this path.
    """

    threshold: float | None
    n_total: int
    n_answered: int
    n_errors_answered: int
    coverage: float
    risk: float
    sweep: tuple[SweepPoint, ...]
    curve: tuple[tuple[float, float], ...]
    aurc: float
    sensitivity: tuple[SensitivityStep, ...]
    conformal_prediction_used: bool = field(default=False, init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "n_total": self.n_total,
            "n_answered": self.n_answered,
            "n_errors_answered": self.n_errors_answered,
            "coverage": self.coverage,
            "risk": self.risk,
            "sweep": [p.to_dict() for p in self.sweep],
            "curve": [list(point) for point in self.curve],
            "aurc": self.aurc,
            "sensitivity": [s.to_dict() for s in self.sensitivity],
            "conformal_prediction_used": self.conformal_prediction_used,
        }


def selective_prediction_report(
    confidences: Sequence[float],
    correct: Sequence[bool],
    threshold: float | None = None,
    thresholds: Iterable[float] | None = None,
) -> SelectiveReport:
    """Primary selective-prediction entry point.

    Computes coverage and selective risk at ``threshold`` (when given),
    together with the full threshold sweep, the risk-coverage curve, its
    AURC and the threshold-sensitivity steps.

    ``confidences`` are the model's own raw, self-reported confidence scores.
    No calibration is performed and none is claimed. This function does not
    touch the experimental conformal scaffold in any way.
    """
    confidences = [float(c) for c in confidences]
    correct = [bool(c) for c in correct]
    _check_aligned(confidences, correct, "correct")

    sweep = threshold_sweep(confidences, correct, thresholds)
    curve = risk_coverage_curve(confidences, correct, thresholds)
    sensitivity = threshold_sensitivity(confidences, correct, thresholds)

    if threshold is None:
        n_answered = len(confidences)
        n_errors = sum(1 for is_correct in correct if not is_correct)
    else:
        n_answered = 0
        n_errors = 0
        for confidence, is_correct in zip(confidences, correct):
            if confidence >= threshold:
                n_answered += 1
                if not is_correct:
                    n_errors += 1

    return SelectiveReport(
        threshold=threshold,
        n_total=len(confidences),
        n_answered=n_answered,
        n_errors_answered=n_errors,
        coverage=coverage_from_counts(n_answered, len(confidences)),
        risk=selective_risk_from_counts(n_errors, n_answered),
        sweep=tuple(sweep),
        curve=tuple(curve),
        aurc=aurc_from_curve(curve),
        sensitivity=tuple(sensitivity),
    )
