"""Tests for strengthening.metrics.selective (and the isolation of the
experimental conformal scaffold).

All expected risk / coverage / AURC values below are derived by hand in
comments before being asserted.
"""

from __future__ import annotations

import pytest

from strengthening.metrics import conformal_prediction, selective
from strengthening.metrics.selective import (
    aurc,
    aurc_from_curve,
    coverage_at_target_precision,
    coverage_from_counts,
    coverage_score,
    precision_operating_points,
    risk_coverage_curve,
    selective_prediction_report,
    selective_risk,
    selective_risk_from_counts,
    threshold_sensitivity,
    threshold_sweep,
    uncertain_class_scores,
)

MATCH = "match"
NON_MATCH = "non-match"
UNCERTAIN = "uncertain"

# ---------------------------------------------------------------------------
# Hand-constructed 8-item toy set
# ---------------------------------------------------------------------------
# Raw, self-reported model confidence (NOT a calibrated probability) and
# whether the prediction was actually correct:
#
#   conf   0.9  0.8  0.7  0.6  0.5  0.4  0.3  0.2
#   ok      T    T    F    T    F    T    F    F
#
# n_total = 8; 4 of the 8 predictions are wrong (conf 0.7, 0.5, 0.3, 0.2).
CONFIDENCES = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
CORRECT = [True, True, False, True, False, True, False, False]

# Threshold 0.75: answered = {0.9, 0.8}                     -> 2 of 8
#   coverage = 2/8 = 0.25 ; errors among answered = 0
#   risk = 0/2 = 0.0
# Threshold 0.55: answered = {0.9, 0.8, 0.7, 0.6}           -> 4 of 8
#   coverage = 4/8 = 0.5  ; errors among answered = 1 (the 0.7 item)
#   risk = 1/4 = 0.25
# Threshold 0.35: answered = {0.9 ... 0.4}                  -> 6 of 8
#   coverage = 6/8 = 0.75 ; errors = 2 (the 0.7 and 0.5 items)
#   risk = 2/6 = 1/3 = 0.3333...
# Threshold 0.15: answered = everything                     -> 8 of 8
#   coverage = 8/8 = 1.0  ; errors = 4
#   risk = 4/8 = 0.5
HAND_THRESHOLDS = [0.75, 0.55, 0.35, 0.15]
HAND_COVERAGE = [0.25, 0.5, 0.75, 1.0]
HAND_RISK = [0.0, 0.25, 1.0 / 3.0, 0.5]


def test_coverage_and_risk_scalars() -> None:
    assert coverage_from_counts(2, 8) == pytest.approx(0.25)
    assert selective_risk_from_counts(1, 4) == pytest.approx(0.25)
    # No items / nothing answered -> documented 0.0 convention, never NaN.
    assert coverage_from_counts(0, 0) == 0.0
    assert selective_risk_from_counts(0, 0) == 0.0
    assert coverage_score([True, False, True, True]) == pytest.approx(0.75)


def test_abstentions_are_excluded_from_both_terms_of_the_risk() -> None:
    # Answered: items 0 (correct) and 2 (wrong). Items 1 and 3 abstained --
    # item 3 is wrong but abstained, so it must NOT count as an error and
    # must NOT enlarge the denominator.
    answered = [True, False, True, False]
    correct = [True, False, False, False]
    # risk = 1 error / 2 answered = 0.5   (NOT 3/4, and NOT 1/4)
    assert selective_risk(answered, correct) == pytest.approx(0.5)


def test_threshold_sweep_matches_hand_computed_points() -> None:
    points = threshold_sweep(CONFIDENCES, CORRECT, HAND_THRESHOLDS)
    assert [p.threshold for p in points] == HAND_THRESHOLDS
    assert [p.n_answered for p in points] == [2, 4, 6, 8]
    assert [p.n_errors for p in points] == [0, 1, 2, 4]
    for point, coverage, risk in zip(points, HAND_COVERAGE, HAND_RISK):
        assert point.coverage == pytest.approx(coverage)
        assert point.risk == pytest.approx(risk)


def test_default_sweep_uses_every_attainable_operating_point() -> None:
    points = threshold_sweep(CONFIDENCES, CORRECT)
    # 8 distinct confidence values -> 8 operating points, coverage 1/8 .. 8/8.
    assert len(points) == 8
    assert [p.n_answered for p in points] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert points[-1].coverage == pytest.approx(1.0)
    # Cumulative errors as the threshold drops: the wrong items sit at
    # confidences 0.7, 0.5, 0.3, 0.2 -> ranks 3, 5, 7, 8.
    assert [p.n_errors for p in points] == [0, 0, 1, 1, 2, 2, 3, 4]


def test_risk_coverage_curve_is_sorted_by_ascending_coverage() -> None:
    curve = risk_coverage_curve(CONFIDENCES, CORRECT, HAND_THRESHOLDS)
    coverages = [c for c, _ in curve]
    assert coverages == sorted(coverages)
    assert coverages == pytest.approx(HAND_COVERAGE)
    assert [r for _, r in curve] == pytest.approx(HAND_RISK)


# ---------------------------------------------------------------------------
# AURC against known closed-form areas
# ---------------------------------------------------------------------------
def test_aurc_of_a_straight_line_matches_the_closed_form() -> None:
    # risk(coverage) = coverage on [0, 1].
    # closed form: integral_0^1 x dx = 1/2 = 0.5
    line = [(0.0, 0.0), (0.25, 0.25), (0.5, 0.5), (0.75, 0.75), (1.0, 1.0)]
    assert aurc_from_curve(line) == pytest.approx(0.5)
    # The trapezoid rule is exact on a straight line, so the sampling
    # density must not matter.
    assert aurc_from_curve([(0.0, 0.0), (1.0, 1.0)]) == pytest.approx(0.5)


def test_aurc_of_a_line_on_a_partial_span_matches_the_closed_form() -> None:
    # risk(coverage) = coverage on [0.2, 1.0] (no extrapolation below 0.2).
    # closed form: integral_0.2^1 x dx = (1^2 - 0.2^2)/2 = (1 - 0.04)/2 = 0.48
    line = [(0.2, 0.2), (0.6, 0.6), (1.0, 1.0)]
    assert aurc_from_curve(line) == pytest.approx(0.48)


def test_aurc_of_a_constant_risk_curve_matches_the_closed_form() -> None:
    # risk(coverage) = 0.2 on [0.25, 1.0].
    # closed form: 0.2 * (1.0 - 0.25) = 0.2 * 0.75 = 0.15
    flat = [(0.25, 0.2), (0.5, 0.2), (0.75, 0.2), (1.0, 0.2)]
    assert aurc_from_curve(flat) == pytest.approx(0.15)


def test_aurc_of_a_triangle_matches_the_closed_form() -> None:
    # risk(coverage) = 2 * (coverage - 0.5) on [0.5, 1.0], i.e. 0 -> 1.
    # closed form: area of the triangle = 0.5 * base * height
    #            = 0.5 * (1.0 - 0.5) * 1.0 = 0.25
    triangle = [(0.5, 0.0), (0.75, 0.5), (1.0, 1.0)]
    assert aurc_from_curve(triangle) == pytest.approx(0.25)


def test_aurc_input_order_does_not_matter_and_short_curves_are_zero_width() -> None:
    line = [(1.0, 1.0), (0.0, 0.0), (0.5, 0.5)]
    assert aurc_from_curve(line) == pytest.approx(0.5)
    assert aurc_from_curve([(0.5, 0.3)]) == 0.0
    assert aurc_from_curve([]) == 0.0


def test_aurc_on_the_toy_data_uses_the_documented_curve() -> None:
    # With the four hand thresholds, the curve is
    #   (0.25, 0)  (0.5, 0.25)  (0.75, 1/3)  (1.0, 0.5)
    # trapezoids over coverage:
    #   0.25 * (0 + 0.25)/2      = 0.25 * 0.125       = 0.03125
    #   0.25 * (0.25 + 1/3)/2    = 0.25 * 0.2916666.. = 0.0729166666..
    #   0.25 * (1/3 + 0.5)/2     = 0.25 * 0.4166666.. = 0.1041666666..
    #   total                                          = 0.2083333333..
    expected = 0.25 * (0.0 + 0.25) / 2
    expected += 0.25 * (0.25 + 1.0 / 3.0) / 2
    expected += 0.25 * (1.0 / 3.0 + 0.5) / 2
    assert expected == pytest.approx(0.2083333333333, abs=1e-9)
    assert aurc(CONFIDENCES, CORRECT, HAND_THRESHOLDS) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Threshold sensitivity
# ---------------------------------------------------------------------------
def test_threshold_sensitivity_is_hand_computed() -> None:
    steps = threshold_sensitivity(CONFIDENCES, CORRECT, HAND_THRESHOLDS)
    assert len(steps) == 3

    # Step 1: threshold 0.75 -> 0.55
    #   delta_threshold = 0.55 - 0.75 = -0.20
    #   delta_coverage  = 0.50 - 0.25 = +0.25
    #   delta_risk      = 0.25 - 0.00 = +0.25
    #   d coverage / d threshold = 0.25 / -0.20 = -1.25
    #   d risk     / d threshold = 0.25 / -0.20 = -1.25
    first = steps[0]
    assert first.delta_threshold == pytest.approx(-0.20)
    assert first.delta_coverage == pytest.approx(0.25)
    assert first.delta_risk == pytest.approx(0.25)
    assert first.d_coverage_d_threshold == pytest.approx(-1.25)
    assert first.d_risk_d_threshold == pytest.approx(-1.25)

    # Step 2: threshold 0.55 -> 0.35
    #   delta_risk = 1/3 - 1/4 = 4/12 - 3/12 = 1/12 = 0.0833333...
    #   d risk / d threshold = (1/12) / -0.20 = -0.4166666...
    second = steps[1]
    assert second.delta_risk == pytest.approx(1.0 / 12.0)
    assert second.d_risk_d_threshold == pytest.approx((1.0 / 12.0) / -0.20)


def test_repeated_threshold_gives_none_slope_not_a_fabricated_one() -> None:
    steps = threshold_sensitivity(CONFIDENCES, CORRECT, [0.5, 0.5])
    assert len(steps) == 1
    assert steps[0].delta_threshold == 0.0
    assert steps[0].d_coverage_d_threshold is None
    assert steps[0].d_risk_d_threshold is None


# ---------------------------------------------------------------------------
# Uncertain-class scores are delegated to three_way, not reimplemented
# ---------------------------------------------------------------------------
# Same 10-item example as test_metrics_three_way.py:
#   uncertain: TP = 1, FP = 2, FN = 1
#   P = 1/3 ; R = 1/2 ; F1 = 2*(1/3)*(1/2)/(1/3+1/2) = (1/3)/(5/6) = 2/5 = 0.4
THREE_WAY_PAIRS = [
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


def test_uncertain_class_scores_are_hand_computed() -> None:
    scores = uncertain_class_scores(THREE_WAY_PAIRS)
    assert scores.label == UNCERTAIN
    assert (scores.tp, scores.fp, scores.fn) == (1, 2, 1)
    assert scores.precision == pytest.approx(1.0 / 3.0)
    assert scores.recall == pytest.approx(0.5)
    assert scores.f1 == pytest.approx(0.4)


def test_uncertain_class_scores_actually_delegate_to_three_way(monkeypatch) -> None:
    # The per-class arithmetic must live in three_way, not be duplicated here:
    # if three_way.three_way_scores is not called, this test fails.
    calls: list[int] = []
    original = selective.three_way_scores

    def _spy(pairs):
        calls.append(1)
        return original(pairs)

    monkeypatch.setattr(selective, "three_way_scores", _spy)
    selective.uncertain_class_scores(THREE_WAY_PAIRS)
    assert calls == [1]


# ---------------------------------------------------------------------------
# coverage_at_target_precision
# ---------------------------------------------------------------------------
# Hand-constructed 6-item set. "conf" is the raw, self-reported confidence.
#
#   item  conf   gold        pred        cell
#     A   0.95   match       match       TP
#     B   0.90   match       match       TP
#     C   0.60   non-match   match       FP
#     D   0.85   non-match   non-match   TN
#     E   0.55   match       non-match   FN
#     F   0.50   non-match   non-match   TN
#
# Operating points (answered = conf >= t), match-precision over answered
# items predicted "match":
#   t = 0.95 -> answered {A}          cov 1/6  pm 1 tp 1  P = 1.0
#   t = 0.90 -> answered {A,B}        cov 2/6  pm 2 tp 2  P = 1.0
#   t = 0.85 -> answered {A,B,D}      cov 3/6  pm 2 tp 2  P = 1.0
#   t = 0.60 -> answered {A,B,D,C}    cov 4/6  pm 3 tp 2  P = 2/3
#   t = 0.55 -> answered +{E}         cov 5/6  pm 3 tp 2  P = 2/3
#   t = 0.50 -> answered all          cov 6/6  pm 3 tp 2  P = 2/3
EST_CONF = [0.95, 0.90, 0.60, 0.85, 0.55, 0.50]
EST_GOLD = [MATCH, MATCH, NON_MATCH, NON_MATCH, MATCH, NON_MATCH]
EST_PRED = [MATCH, MATCH, MATCH, NON_MATCH, NON_MATCH, NON_MATCH]


def test_precision_operating_points_are_hand_computed() -> None:
    points = precision_operating_points(EST_CONF, EST_GOLD, EST_PRED)
    assert [p.threshold for p in points] == [0.95, 0.90, 0.85, 0.60, 0.55, 0.50]
    assert [p.n_answered for p in points] == [1, 2, 3, 4, 5, 6]
    assert [p.n_predicted_match for p in points] == [1, 2, 2, 3, 3, 3]
    assert [p.n_true_positive for p in points] == [1, 2, 2, 2, 2, 2]
    assert [p.match_precision for p in points] == pytest.approx(
        [1.0, 1.0, 1.0, 2.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0]
    )


def test_coverage_at_target_precision_is_hand_computed() -> None:
    # Highest coverage whose match-precision reaches the target:
    #   target 1.00 -> the last point with P = 1.0 is t = 0.85, coverage 3/6 = 0.5
    #   target 0.90 -> same operating point, coverage 0.5
    #   target 0.65 -> 2/3 = 0.6666.. >= 0.65, so coverage reaches 6/6 = 1.0
    result = coverage_at_target_precision(
        EST_CONF, EST_GOLD, EST_PRED, [1.0, 0.90, 0.65]
    )
    assert result[1.0] == pytest.approx(0.5)
    assert result[0.90] == pytest.approx(0.5)
    assert result[0.65] == pytest.approx(1.0)


def test_coverage_at_target_precision_accepts_a_single_target() -> None:
    result = coverage_at_target_precision(EST_CONF, EST_GOLD, EST_PRED, 1.0)
    assert result == {1.0: pytest.approx(0.5)}


# Non-estimable set: every operating point tops out at precision 0.5.
#
#   item  conf   gold        pred     cell
#     A   0.9    non-match   match    FP
#     B   0.8    match       match    TP
#     C   0.7    non-match   match    FP
#     D   0.6    match       match    TP
#
#   t = 0.9 -> pm 1 tp 0 -> P = 0.0
#   t = 0.8 -> pm 2 tp 1 -> P = 0.5
#   t = 0.7 -> pm 3 tp 1 -> P = 1/3
#   t = 0.6 -> pm 4 tp 2 -> P = 0.5
#   max attainable precision = 0.5, so a 0.95 target is NOT estimable.
NON_EST_CONF = [0.9, 0.8, 0.7, 0.6]
NON_EST_GOLD = [NON_MATCH, MATCH, NON_MATCH, MATCH]
NON_EST_PRED = [MATCH, MATCH, MATCH, MATCH]


def test_coverage_at_target_precision_returns_none_when_not_estimable() -> None:
    result = coverage_at_target_precision(
        NON_EST_CONF, NON_EST_GOLD, NON_EST_PRED, [0.95, 0.99, 1.0]
    )
    # None, not 0.0 and not some plausible-looking fabricated coverage.
    assert result[0.95] is None
    assert result[0.99] is None
    assert result[1.0] is None
    # Sanity: a reachable target on the SAME data does return a number, so
    # the None above is a real "not estimable", not a broken function.
    reachable = coverage_at_target_precision(
        NON_EST_CONF, NON_EST_GOLD, NON_EST_PRED, 0.5
    )
    assert reachable[0.5] == pytest.approx(1.0)


def test_coverage_at_target_precision_none_on_empty_data() -> None:
    assert coverage_at_target_precision([], [], [], [0.9]) == {0.9: None}


def test_coverage_at_target_precision_respects_minimum_support() -> None:
    # Demanding more predicted matches than any operating point can offer
    # makes the target non-estimable rather than optimistically answered.
    result = coverage_at_target_precision(
        EST_CONF, EST_GOLD, EST_PRED, 1.0, min_predicted_matches=99
    )
    assert result[1.0] is None


def test_all_predictions_abstained_gives_zero_coverage_and_no_precision() -> None:
    points = precision_operating_points(
        [0.9, 0.8], [MATCH, NON_MATCH], [UNCERTAIN, UNCERTAIN]
    )
    assert all(p.n_answered == 0 for p in points)
    assert all(p.match_precision is None for p in points)
    assert coverage_at_target_precision(
        [0.9, 0.8], [MATCH, NON_MATCH], [UNCERTAIN, UNCERTAIN], 0.5
    ) == {0.5: None}


# ---------------------------------------------------------------------------
# Primary selective report
# ---------------------------------------------------------------------------
def test_selective_prediction_report_matches_hand_computed_values() -> None:
    report = selective_prediction_report(
        CONFIDENCES, CORRECT, threshold=0.55, thresholds=HAND_THRESHOLDS
    )
    assert report.n_total == 8
    assert report.n_answered == 4
    assert report.n_errors_answered == 1
    assert report.coverage == pytest.approx(0.5)
    assert report.risk == pytest.approx(0.25)
    assert len(report.sweep) == 4
    assert len(report.curve) == 4
    assert len(report.sensitivity) == 3
    assert report.conformal_prediction_used is False


def test_selective_prediction_report_without_a_threshold_answers_everything() -> None:
    report = selective_prediction_report(CONFIDENCES, CORRECT)
    assert report.coverage == pytest.approx(1.0)
    assert report.risk == pytest.approx(0.5)  # 4 wrong out of 8


# ---------------------------------------------------------------------------
# The conformal scaffold is opt-in ONLY and is never on the primary path
# ---------------------------------------------------------------------------
def test_primary_selective_api_never_invokes_the_conformal_scaffold(monkeypatch) -> None:
    calls: list[tuple] = []

    def _tripwire(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError(
            "the experimental conformal scaffold must never be reached from "
            "the primary selective-prediction path"
        )

    monkeypatch.setattr(conformal_prediction, "conformal_score_threshold", _tripwire)

    # Exercise the whole primary surface with the tripwire armed.
    selective_prediction_report(CONFIDENCES, CORRECT, threshold=0.55)
    threshold_sweep(CONFIDENCES, CORRECT)
    risk_coverage_curve(CONFIDENCES, CORRECT)
    aurc(CONFIDENCES, CORRECT)
    threshold_sensitivity(CONFIDENCES, CORRECT)
    selective_risk([True, True], [True, False])
    uncertain_class_scores(THREE_WAY_PAIRS)
    precision_operating_points(EST_CONF, EST_GOLD, EST_PRED)
    coverage_at_target_precision(EST_CONF, EST_GOLD, EST_PRED, [0.9])

    assert calls == []


def test_selective_module_holds_no_reference_to_the_conformal_module() -> None:
    # Structural check: nothing in selective's namespace is the conformal
    # module or anything defined in it.
    assert not hasattr(selective, "conformal_prediction")
    for name, value in vars(selective).items():
        module_name = getattr(value, "__module__", None) or getattr(
            value, "__name__", None
        )
        assert module_name != conformal_prediction.__name__, (
            f"selective.{name} comes from the conformal scaffold"
        )


def test_conformal_scaffold_is_disabled_by_default() -> None:
    assert conformal_prediction.CONFORMAL_ENABLED_BY_DEFAULT is False
    result = conformal_prediction.conformal_score_threshold([0.1, 0.2, 0.3])
    assert isinstance(result, conformal_prediction.DisabledResult)
    assert result.enabled is False
    assert result.computed is False
    assert result.threshold is None
    assert bool(result) is False
    assert "disabled by default" in result.reason


def test_conformal_scaffold_can_raise_instead_of_returning_a_flag() -> None:
    with pytest.raises(conformal_prediction.ConformalDisabledError):
        conformal_prediction.conformal_score_threshold([0.1, 0.2], strict=True)


def test_conformal_scaffold_only_computes_when_explicitly_enabled() -> None:
    # 9 reserved scores, alpha = 0.1:
    #   rank = ceil((9 + 1) * 0.9) = ceil(9.0) = 9 -> the 9th smallest = 0.9
    scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    result = conformal_prediction.conformal_score_threshold(
        scores, alpha=0.1, enabled=True
    )
    assert isinstance(result, conformal_prediction.ConformalScaffoldResult)
    assert result.computed is True
    assert result.experimental is True
    assert result.quantile_rank == 9
    assert result.threshold == pytest.approx(0.9)
    # No guarantee is claimed by this scaffold.
    assert result.guarantee_claimed is False


def test_selective_module_docstring_disclaims_calibration_guarantees() -> None:
    assert "No calibration" in selective.__doc__
    assert "EXPERIMENTAL" in conformal_prediction.__doc__
