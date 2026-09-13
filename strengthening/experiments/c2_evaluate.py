"""C2 Tasks 10-13: evaluation of all frozen predictions against the gold
labels -- joined strictly AFTER the prediction freeze (Task 9), never
before. Binary (excludes gold-uncertain) + three-way (includes all) per
CE400/diabetes500/pooled900 for every method; paired bootstrap
comparisons of Primary M7 vs B3/B5/B6/B7; selective-prediction analysis
restricted to the genuinely confidence-bearing methods (Primary M7,
OpenAI); and a re-run of the observed transitive-contradiction
diagnostic using real model predictions (never full B-cubed / a
manufactured gold partition).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..baselines.b8_retrieve_then_prompt.clustering import connected_components
from ..metrics import DEFAULT_SEED
from ..metrics.binary import bootstrap_ci, paired_bootstrap_difference, scores_from_pairs
from ..metrics.selective import selective_prediction_report
from ..metrics.three_way import three_way_scores
from .frozen_inputs import GOLD_CSV, verify_gold_hash
from .transitive_contradiction_diagnostic import count_closed_triangles

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
FREEZE_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution" / "frozen_predictions"

METHOD_LOAD_SPEC = {
    "B1_Exact": ("b1_b5_frozen.csv", "B1_Exact"),
    "B2_Normalised": ("b1_b5_frozen.csv", "B2_Normalised"),
    "B3_JaroWinkler": ("b1_b5_frozen.csv", "B3_JaroWinkler"),
    "B4_TFIDF": ("b1_b5_frozen.csv", "B4_TFIDF"),
    "B5_Embedding": ("b1_b5_frozen.csv", "B5_Embedding"),
    "Primary_M7": ("primary_m7_frozen.csv", "guard_decision"),
    "B6": ("b6_frozen.csv", "parsed_decision"),
    "B7": ("b7_frozen.csv", "binary_label"),
    "B8": ("b8_frozen.csv", "b8_predicted_label"),
    "OpenAI_Robustness": ("openai_frozen.csv", "guard_decision"),
}
CONFIDENCE_METHOD_SPEC = {
    "Primary_M7": ("primary_m7_frozen.csv", "guard_confidence"),
    "OpenAI_Robustness": ("openai_frozen.csv", "guard_confidence"),
}
BOOTSTRAP_BASELINE_COMPARISONS = ["B3_JaroWinkler", "B5_Embedding", "B6", "B7"]
N_RESAMPLES = 10_000


def normalise_label(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "uncertain"
    x = str(x)
    return "non-match" if x == "non_match" else x


def load_all_predictions() -> dict[str, pd.DataFrame]:
    out = {}
    for method, (filename, col) in METHOD_LOAD_SPEC.items():
        path = FREEZE_DIR / filename
        df = pd.read_csv(path, dtype=str)
        out[method] = pd.DataFrame({"pair_id": df["pair_id"], "label": df[col].apply(normalise_label)})
    return out


def load_confidences() -> dict[str, pd.DataFrame]:
    out = {}
    for method, (filename, col) in CONFIDENCE_METHOD_SPEC.items():
        path = FREEZE_DIR / filename
        df = pd.read_csv(path, dtype=str)
        out[method] = pd.DataFrame({"pair_id": df["pair_id"], "confidence": pd.to_numeric(df[col], errors="coerce")})
    return out


def load_gold() -> pd.DataFrame:
    verify_gold_hash()
    return pd.read_csv(GOLD_CSV, dtype=str)[["pair_id", "domain", "string_a", "string_b", "final_gold_label"]]


def _partitions(gold: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "ce400": gold[gold["domain"] == "circular_economy"],
        "diabetes500": gold[gold["domain"] == "biomedical_diabetes_mellitus"],
        "pooled900": gold,
    }


def evaluate_all(gold: pd.DataFrame, predictions: dict[str, pd.DataFrame]) -> dict:
    results = {}
    for partition_name, gpart in _partitions(gold).items():
        results[partition_name] = {}
        for method, pred_df in predictions.items():
            merged = gpart.merge(pred_df, on="pair_id", how="inner", validate="one_to_one")
            if len(merged) != len(gpart):
                raise ValueError(f"{method}/{partition_name}: merge dropped rows ({len(gpart)} -> {len(merged)})")
            gold_labels = merged["final_gold_label"].tolist()
            pred_labels = merged["label"].tolist()
            binary = scores_from_pairs(list(zip(gold_labels, pred_labels)))
            threeway = three_way_scores(list(zip(gold_labels, pred_labels)))
            results[partition_name][method] = {"binary": binary.to_dict(), "three_way": threeway.to_dict()}
    return results


def bootstrap_comparisons(gold: pd.DataFrame, predictions: dict[str, pd.DataFrame]) -> dict:
    comparisons = {}
    for partition_name, gpart in _partitions(gold).items():
        comparisons[partition_name] = {}
        base = gpart.merge(predictions["Primary_M7"], on="pair_id", how="inner").rename(columns={"label": "primary_label"})
        for baseline in BOOTSTRAP_BASELINE_COMPARISONS:
            merged = base.merge(predictions[baseline], on="pair_id", how="inner").rename(columns={"label": "baseline_label"})
            diff = paired_bootstrap_difference(
                gold=merged["final_gold_label"].tolist(),
                pred_a=merged["primary_label"].tolist(),
                pred_b=merged["baseline_label"].tolist(),
                metric="f1", n_resamples=N_RESAMPLES, seed=DEFAULT_SEED,
            )
            comparisons[partition_name][f"Primary_M7_vs_{baseline}"] = diff.to_dict()

        # Also a standalone bootstrap CI for Primary M7's own F1 per partition.
        primary_pairs = list(zip(base["final_gold_label"], base["primary_label"]))
        comparisons[partition_name]["Primary_M7_f1_ci"] = bootstrap_ci(primary_pairs, metric="f1", n_resamples=N_RESAMPLES, seed=DEFAULT_SEED).to_dict()
    return comparisons


def selective_prediction_analysis(gold: pd.DataFrame, predictions: dict[str, pd.DataFrame], confidences: dict[str, pd.DataFrame]) -> dict:
    results = {}
    for method, conf_df in confidences.items():
        results[method] = {}
        pred_df = predictions[method]
        for partition_name, gpart in _partitions(gold).items():
            merged = gpart.merge(pred_df, on="pair_id", how="inner").merge(conf_df, on="pair_id", how="inner")
            binary_subset = merged[merged["final_gold_label"].isin(["match", "non-match"])].copy()
            binary_subset["confidence"] = binary_subset["confidence"].fillna(0.0)
            correct = (binary_subset["final_gold_label"] == binary_subset["label"]).tolist()
            report = selective_prediction_report(confidences=binary_subset["confidence"].tolist(), correct=correct)
            results[method][partition_name] = {
                "n_binary_subset": len(binary_subset),
                "n_total": report.n_total, "n_answered": report.n_answered,
                "coverage": report.coverage, "risk": report.risk, "aurc": report.aurc,
                "n_sweep_points": len(report.sweep), "n_curve_points": len(report.curve),
            }
    return results


def transitivity_diagnostic(gold: pd.DataFrame, predictions: dict[str, pd.DataFrame]) -> dict:
    triangle_info = count_closed_triangles(gold)
    n_triangles = triangle_info["n_closed_triangles"]

    method_results = {}
    for method, pred_df in predictions.items():
        merged = gold.merge(pred_df, on="pair_id", how="inner", validate="one_to_one")
        matched = merged[merged["label"] == "match"]
        edges = list(zip(matched["string_a"], matched["string_b"]))
        all_nodes = set(merged["string_a"]) | set(merged["string_b"])
        clustering = connected_components(edges, nodes=all_nodes)

        non_match = merged[merged["final_gold_label"] == "non-match"]
        direct_match_pairs = {frozenset((a, b)) for a, b in edges}
        n_connected = n_direct = n_transitive_only = 0
        for _, row in non_match.iterrows():
            a, b = row["string_a"], row["string_b"]
            ca, cb = clustering.assignments.get(a), clustering.assignments.get(b)
            if ca is not None and ca == cb:
                n_connected += 1
                if frozenset((a, b)) in direct_match_pairs:
                    n_direct += 1
                else:
                    n_transitive_only += 1
        n_eval = len(non_match)
        method_results[method] = {
            "n_gold_non_match_evaluated": n_eval,
            "n_connected_incorrectly": n_connected,
            "proportion_connected_incorrectly": (n_connected / n_eval if n_eval else None),
            "n_direct_error": n_direct,
            "n_transitive_only_contradiction": n_transitive_only,
            "n_predicted_clusters": clustering.n_clusters,
        }

    return {
        "n_closed_triangles_observed": n_triangles,
        "closed_triangle_analysis_note": "descriptive only -- too few (6) to support a stable consistency estimate; not forced.",
        "methods": method_results,
    }


def run() -> dict:
    gold = load_gold()
    predictions = load_all_predictions()
    confidences = load_confidences()

    evaluation = evaluate_all(gold, predictions)
    bootstrap = bootstrap_comparisons(gold, predictions)
    selective = selective_prediction_analysis(gold, predictions, confidences)
    transitivity = transitivity_diagnostic(gold, predictions)

    result = {"evaluation": evaluation, "bootstrap": bootstrap, "selective_prediction": selective, "transitivity_diagnostic": transitivity}
    with open(REPORTS_DIR / "C2_EVALUATION_RESULTS.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    _write_markdown(result)
    return result


def _write_markdown(result: dict) -> None:
    lines = ["# C2 evaluation results (real predictions, joined strictly after prediction freeze)", ""]
    lines += ["## Binary evaluation (gold-uncertain excluded)", ""]
    for partition_name, methods in result["evaluation"].items():
        lines += [f"### {partition_name}", "", "| Method | TP | FP | FN | TN | Precision | Recall | F1 | Coverage |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for method, r in methods.items():
            b = r["binary"]
            lines.append(f"| {method} | {b['tp']} | {b['fp']} | {b['fn']} | {b['tn']} | {b['precision']:.4f} | {b['recall']:.4f} | {b['f1']:.4f} | {b['coverage']:.4f} |")
        lines.append("")

    lines += ["## Three-way evaluation (all gold labels included; uncertain treated descriptively)", ""]
    for partition_name, methods in result["evaluation"].items():
        lines += [f"### {partition_name}", "", "| Method | Accuracy | Macro-F1 |", "|---|---:|---:|"]
        for method, r in methods.items():
            t = r["three_way"]
            lines.append(f"| {method} | {t['accuracy']:.4f} | {t['macro_f1']:.4f} |")
        lines.append("")

    lines += ["## Paired bootstrap (Primary M7 vs. baselines, F1, N=10000, seed=42)", ""]
    for partition_name, comps in result["bootstrap"].items():
        lines += [f"### {partition_name}", ""]
        for name, c in comps.items():
            if name == "Primary_M7_f1_ci":
                lines.append(f"- Primary M7 F1 95% CI: [{c['lower']:.4f}, {c['upper']:.4f}] (point={c['point_estimate']:.4f})")
                continue
            lines.append(f"- {name}: diff={c['observed_difference']:.4f}, 95% CI=[{c['lower']:.4f}, {c['upper']:.4f}], excludes_zero={c['excludes_zero']}")
        lines.append("")

    lines += ["## Selective prediction (genuine confidence only: Primary M7, OpenAI)", ""]
    for method, partitions in result["selective_prediction"].items():
        lines += [f"### {method}", "", "| Partition | N (binary) | Coverage | Risk | AURC |", "|---|---:|---:|---:|---:|"]
        for partition_name, s in partitions.items():
            lines.append(f"| {partition_name} | {s['n_binary_subset']} | {s['coverage']:.4f} | {s['risk']:.4f} | {s['aurc']:.4f} |")
        lines.append("")

    lines += ["## Transitivity diagnostic (lower-bound safety diagnostic, not complete cluster metric)", "",
              f"Closed triangles observed: {result['transitivity_diagnostic']['n_closed_triangles_observed']} -- {result['transitivity_diagnostic']['closed_triangle_analysis_note']}",
              "", "| Method | Gold non-match evaluated | Connected incorrectly | Direct | Transitive-only |", "|---|---:|---:|---:|---:|"]
    for method, m in result["transitivity_diagnostic"]["methods"].items():
        lines.append(f"| {method} | {m['n_gold_non_match_evaluated']} | {m['n_connected_incorrectly']} | {m['n_direct_error']} | {m['n_transitive_only_contradiction']} |")

    (REPORTS_DIR / "C2_EVALUATION_RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
