"""C1 Task 3 (evaluation half) + Task 11 preparation: joins the frozen
B1-B5 predictions (already written to disk by b1_b5_baselines.py, with
no gold ever visible during prediction) against the frozen 900-pair gold,
strictly as a separate post-hoc step. Gold is used here ONLY to score
already-fixed predictions -- never to choose a threshold, a prompt, or
any other hyperparameter (all five methods' decision rules were fixed
before this module ever reads gold).

Produces, per partition (CE400/diabetes500/pooled900) and per baseline:
binary precision/recall/f1/coverage, a percentile bootstrap CI for F1,
and (for B3/B4/B5, which have a continuous similarity score) a
DEMONSTRATION selective-prediction report via strengthening/metrics/
selective.py, using a margin-based confidence proxy
(``|similarity - frozen_threshold|``, i.e. distance from the decision
boundary). This is explicitly NOT a genuine self-reported model
confidence -- B1-B5 have none -- and must not be presented as a headline
selective-prediction result; it exists only to demonstrate the module is
wired correctly ahead of the LLM-based methods (primary M7, OpenAI),
which DO produce a genuine guard-confidence field once real predictions
exist. Restricted to the gold match/non-match subset (gold-uncertain
rows excluded), matching strengthening/metrics/binary.py's own
convention -- the prospective gold has only 7 uncertain labels overall,
too few for a stable estimate on their own.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..metrics.binary import DEFAULT_SEED, bootstrap_ci, scores_from_pairs
from ..metrics.selective import selective_prediction_report
from .b1_b5_baselines import OUT_DIR as PREDICTIONS_DIR
from .frozen_inputs import GOLD_CSV, verify_gold_hash

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"

BASELINE_METHODS = ["B1_Exact", "B2_Normalised", "B3_JaroWinkler", "B4_TFIDF", "B5_Embedding"]
SCORED_METHODS = {"B3_JaroWinkler": "B3_JaroWinkler_score", "B4_TFIDF": "B4_TFIDF_score", "B5_Embedding": "B5_Embedding_score"}
FROZEN_THRESHOLDS = {"B3_JaroWinkler": 0.92, "B4_TFIDF": 0.68, "B5_Embedding": 0.85}


def load_gold_labels() -> pd.DataFrame:
    verify_gold_hash()
    gold = pd.read_csv(GOLD_CSV, dtype=str)
    return gold[["pair_id", "final_gold_label"]].rename(columns={"final_gold_label": "gold_label"})


def evaluate_partition(partition_name: str) -> dict:
    pred_path = PREDICTIONS_DIR / f"{partition_name}_b1_b5_predictions.csv"
    predictions = pd.read_csv(pred_path, dtype=str)
    for col in SCORED_METHODS.values():
        predictions[col] = predictions[col].astype(float)

    gold = load_gold_labels()
    merged = predictions.merge(gold, on="pair_id", how="inner", validate="one_to_one")
    if len(merged) != len(predictions):
        raise ValueError(f"{partition_name}: merge with gold dropped rows ({len(predictions)} -> {len(merged)})")

    result: dict = {"partition": partition_name, "n": len(merged), "methods": {}}
    for method in BASELINE_METHODS:
        pairs = list(zip(merged["gold_label"], merged[method]))
        scores = scores_from_pairs(pairs)
        ci = bootstrap_ci(pairs, metric="f1", n_resamples=10_000, seed=DEFAULT_SEED)
        method_result = {"binary": scores.to_dict(), "f1_bootstrap_ci": ci.to_dict()}

        if method in SCORED_METHODS:
            binary_subset = merged[merged["gold_label"].isin(["match", "non-match"])]
            score_col = SCORED_METHODS[method]
            threshold = FROZEN_THRESHOLDS[method]
            margin_confidence = (binary_subset[score_col] - threshold).abs().tolist()
            correct = (binary_subset["gold_label"] == binary_subset[method]).tolist()
            report = selective_prediction_report(confidences=margin_confidence, correct=correct)
            method_result["selective_prediction_demo"] = {
                "note": "margin-based confidence proxy (|similarity - frozen_threshold|), NOT a genuine self-reported model confidence -- demonstration only",
                "n_binary_subset": len(binary_subset),
                "n_total": report.n_total,
                "n_answered": report.n_answered,
                "coverage": report.coverage,
                "risk": report.risk,
                "aurc": report.aurc,
                "n_sweep_points": len(report.sweep),
                "n_curve_points": len(report.curve),
            }

        result["methods"][method] = method_result
    return result


def run() -> dict:
    all_results = {name: evaluate_partition(name) for name in ("ce400", "diabetes500", "pooled900")}
    out_json = REPORTS_DIR / "B1_B5_FROZEN_INFERENCE_EVALUATION.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    _write_markdown(all_results)
    return all_results


def _write_markdown(all_results: dict) -> None:
    lines = ["# B1-B5 frozen-inference evaluation (900 prospective pairs)", "", "Numbers only -- no keyword strings.", ""]
    for partition_name, result in all_results.items():
        lines += [f"## {partition_name} (N={result['n']})", "", "| Method | Precision | Recall | F1 | Coverage | F1 95% CI |", "|---|---:|---:|---:|---:|---:|"]
        for method, m in result["methods"].items():
            b = m["binary"]
            ci = m["f1_bootstrap_ci"]
            lines.append(f"| {method} | {b['precision']:.4f} | {b['recall']:.4f} | {b['f1']:.4f} | {b['coverage']:.4f} | [{ci['lower']:.4f}, {ci['upper']:.4f}] |")
        lines.append("")
        scored = {m: r for m, r in result["methods"].items() if "selective_prediction_demo" in r}
        if scored:
            lines += ["**Selective-prediction demonstration only** (margin-based proxy confidence, not a genuine model confidence):", "",
                      "| Method | AURC | Coverage@no-threshold | Risk@no-threshold |", "|---|---:|---:|---:|"]
            for method, m in scored.items():
                sp = m["selective_prediction_demo"]
                lines.append(f"| {method} | {sp['aurc']:.4f} | {sp['coverage']:.4f} | {sp['risk']:.4f} |")
            lines.append("")
    (REPORTS_DIR / "B1_B5_FROZEN_INFERENCE_EVALUATION.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
