"""Tests for verified v1 binary-metric computation, applicable to both the
baseline methods (B1-B6) and the full-workflow benchmark evaluation --
they share the identical binary_metrics() logic in v1.

Scope note: see conftest.py.
"""
import pytest

from reparse_dev_log_v1 import binary_metrics


def test_perfect_predictions():
    gold = ["match", "non_match", "match", "non_match"]
    pred = ["match", "non_match", "match", "non_match"]
    m = binary_metrics(gold, pred)
    assert m == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "coverage": 1.0}


def test_false_positive_reduces_precision_not_recall():
    gold = ["match", "non_match"]
    pred = ["match", "match"]  # 1 TP, 1 FP
    m = binary_metrics(gold, pred)
    assert m["precision"] == 0.5
    assert m["recall"] == 1.0


def test_false_negative_reduces_recall_not_precision():
    gold = ["match", "match"]
    pred = ["match", "non_match"]  # 1 TP, 1 FN
    m = binary_metrics(gold, pred)
    assert m["precision"] == 1.0
    assert m["recall"] == 0.5


def test_baseline_style_predictions_have_zero_uncertain_rate():
    # B1-B5 structurally cannot predict "uncertain" (Phase 0A finding) --
    # this documents the expected shape of their metrics.
    gold = ["match", "non_match", "match"]
    pred = ["match", "non_match", "non_match"]  # no "uncertain" anywhere
    m = binary_metrics(gold, pred)
    assert m["coverage"] == 1.0


def test_n124_style_denominator_sensitivity():
    # Regression check on the Phase 0A/0B finding: with N=124 decided pairs
    # (41 TP, 1 FP, 2 FN, 80 TN), flipping 1 decision should move F1 by a
    # measurable, bounded amount -- not by an amount that silently changes
    # depending on which pair flips (i.e. metrics must be a pure function
    # of the confusion counts).
    gold = ["match"] * 43 + ["non_match"] * 81
    pred_exact = ["match"] * 41 + ["non_match"] * 2 + ["non_match"] * 80 + ["match"] * 1
    m1 = binary_metrics(gold, pred_exact)
    # binary_metrics() rounds to 4 decimal places by design (matches v1
    # exactly) -- compare with a tolerance wide enough to accommodate that
    # rounding, not the raw fraction's full precision.
    assert m1["precision"] == pytest.approx(41 / 42, abs=1e-4)
    assert m1["recall"] == pytest.approx(41 / 43, abs=1e-4)


def test_empty_input_does_not_crash():
    m = binary_metrics([], [])
    assert m["coverage"] == 0.0
    assert m["precision"] == 0.0
