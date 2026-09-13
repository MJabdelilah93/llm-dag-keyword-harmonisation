"""C3 Tasks 2 & 3: independent metric recomputation from the frozen
prediction snapshots ONLY. Deliberately does NOT import or call
metrics/binary.py, metrics/three_way.py, or c2_evaluate.py's own counting
logic -- confusion-matrix and coverage arithmetic here is written fresh
in plain pandas/numpy so it is a genuine cross-check, not a re-display of
the same code path. Compares every recomputed number against
C2_EVALUATION_RESULTS.json and fails loudly (raises) on any discrepancy
beyond floating-point rounding (1e-9).

Task 3: additionally determines, from first principles on the frozen
data (not from reading metrics/binary.py's source), how predicted
"uncertain" is handled, and computes the abstention-as-wrong / answered-
only accuracy views requested for claim-boundary purposes. Does not
replace the protocol's primary F1 metric.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
FREEZE_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution" / "frozen_predictions"

GOLD_CSV = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "gold" / "PRIMARY_GOLD_900_FINAL.csv"

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


class C3DiscrepancyError(Exception):
    pass


def _norm_label(x) -> str:
    """Independent normaliser, written fresh (not imported from c2_evaluate.py)."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "uncertain"
    x = str(x)
    if x == "non_match":
        return "non-match"
    return x


def load_gold() -> pd.DataFrame:
    gold = pd.read_csv(GOLD_CSV, dtype=str)[["pair_id", "domain", "final_gold_label"]]
    if len(gold) != 900:
        raise C3DiscrepancyError(f"expected 900 gold rows, got {len(gold)}")
    return gold


def load_predictions() -> dict[str, pd.DataFrame]:
    out = {}
    for method, (filename, col) in METHOD_LOAD_SPEC.items():
        df = pd.read_csv(FREEZE_DIR / filename, dtype=str)
        out[method] = pd.DataFrame({"pair_id": df["pair_id"], "label": df[col].apply(_norm_label)})
    return out


def _partitions(merged: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "ce400": merged[merged["domain"] == "circular_economy"],
        "diabetes500": merged[merged["domain"] == "biomedical_diabetes_mellitus"],
        "pooled900": merged,
    }


def independent_binary_and_threeway(gold: pd.DataFrame, pred: pd.DataFrame) -> dict:
    merged = gold.merge(pred, on="pair_id", how="inner", validate="one_to_one")
    if len(merged) != len(gold):
        raise C3DiscrepancyError(f"merge dropped rows: {len(gold)} -> {len(merged)}")

    out = {}
    for pname, part in _partitions(merged).items():
        g = part["final_gold_label"]
        p = part["label"]

        binary_eligible = part[g.isin(["match", "non-match"])]
        gb, pb = binary_eligible["final_gold_label"], binary_eligible["label"]
        tp = int(((gb == "match") & (pb == "match")).sum())
        fp = int(((gb == "non-match") & (pb == "match")).sum())
        fn = int(((gb == "match") & (pb == "non-match")).sum())
        tn = int(((gb == "non-match") & (pb == "non-match")).sum())
        abstained = int((pb == "uncertain").sum())
        n_binary_eligible = len(binary_eligible)
        answered = tp + fp + fn + tn
        if answered + abstained != n_binary_eligible:
            raise C3DiscrepancyError(f"{pname}: answered+abstained ({answered}+{abstained}) != n_binary_eligible ({n_binary_eligible})")

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        coverage = answered / n_binary_eligible if n_binary_eligible else 0.0

        n_gold_match_binary = int((gb == "match").sum())
        n_gold_non_match_binary = int((gb == "non-match").sum())

        # -- Task 3 additional abstention-handling views --
        correct_among_answered = tp + tn
        accuracy_conditional_on_answering = correct_among_answered / answered if answered else 0.0
        # counting abstentions (and any wrong answer) as NOT correct, over the full binary-eligible set:
        accuracy_abstain_as_wrong = correct_among_answered / n_binary_eligible if n_binary_eligible else 0.0
        fp_rate_of_gold_non_match = fp / n_gold_non_match_binary if n_gold_non_match_binary else 0.0
        fp_rate_of_answered_non_match = fp / (fp + tn) if (fp + tn) else 0.0

        # -- three-way (independent 3x3 confusion, all 900/partition items, "uncertain" as a genuine class) --
        classes = ["match", "non-match", "uncertain"]
        matrix = {gc: {pc: int(((g == gc) & (p == pc)).sum()) for pc in classes} for gc in classes}
        n_items = len(part)
        correct_3way = sum(matrix[c][c] for c in classes)
        accuracy_3way = correct_3way / n_items if n_items else 0.0
        per_class_f1 = {}
        for c in classes:
            tp_c = matrix[c][c]
            col_sum = sum(matrix[r][c] for r in classes)
            row_sum = sum(matrix[c][pc] for pc in classes)
            fp_c = col_sum - tp_c
            fn_c = row_sum - tp_c
            prec_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) else 0.0
            rec_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) else 0.0
            per_class_f1[c] = 2 * prec_c * rec_c / (prec_c + rec_c) if (prec_c + rec_c) else 0.0
        macro_f1_3way = sum(per_class_f1.values()) / len(classes)

        out[pname] = {
            "binary": {
                "tp": tp, "fp": fp, "fn": fn, "tn": tn, "abstained": abstained,
                "n_binary_eligible": n_binary_eligible, "n_answered": answered,
                "precision": precision, "recall": recall, "f1": f1, "coverage": coverage,
                "uncertain_count": abstained, "uncertain_rate": abstained / n_binary_eligible if n_binary_eligible else 0.0,
            },
            "task3_abstention_handling": {
                "n_answered": answered, "n_abstained": abstained, "coverage": coverage,
                "n_correct_among_893_abstain_as_wrong": correct_among_answered,
                "accuracy_abstain_as_wrong_over_binary_eligible": accuracy_abstain_as_wrong,
                "accuracy_conditional_on_answering": accuracy_conditional_on_answering,
                "fp_count": fp,
                "fp_rate_of_gold_non_match_binary_eligible": fp_rate_of_gold_non_match,
                "fp_rate_of_answered_non_match": fp_rate_of_answered_non_match,
            },
            "three_way": {"accuracy": accuracy_3way, "macro_f1": macro_f1_3way, "n_items": n_items, "confusion_matrix": matrix},
        }
    return out


def compare_to_c2(independent: dict) -> dict:
    with open(REPORTS_DIR / "C2_EVALUATION_RESULTS.json", encoding="utf-8") as f:
        c2 = json.load(f)

    discrepancies = []
    for method, by_partition in independent.items():
        for pname, r in by_partition.items():
            c2_binary = c2["evaluation"][pname][method]["binary"]
            c2_three = c2["evaluation"][pname][method]["three_way"]
            for field in ("tp", "fp", "fn", "tn"):
                if r["binary"][field] != c2_binary[field]:
                    discrepancies.append(f"{method}/{pname}/binary.{field}: independent={r['binary'][field]} vs C2={c2_binary[field]}")
            for field in ("precision", "recall", "f1", "coverage"):
                if abs(r["binary"][field] - c2_binary[field]) > 1e-9:
                    discrepancies.append(f"{method}/{pname}/binary.{field}: independent={r['binary'][field]} vs C2={c2_binary[field]}")
            if abs(r["three_way"]["accuracy"] - c2_three["accuracy"]) > 1e-9:
                discrepancies.append(f"{method}/{pname}/three_way.accuracy: independent={r['three_way']['accuracy']} vs C2={c2_three['accuracy']}")
            if abs(r["three_way"]["macro_f1"] - c2_three["macro_f1"]) > 1e-9:
                discrepancies.append(f"{method}/{pname}/three_way.macro_f1: independent={r['three_way']['macro_f1']} vs C2={c2_three['macro_f1']}")

    result = {"n_discrepancies": len(discrepancies), "discrepancies": discrepancies, "all_match": len(discrepancies) == 0}
    if discrepancies:
        raise C3DiscrepancyError(f"{len(discrepancies)} discrepancies found between independent recomputation and C2_EVALUATION_RESULTS: {discrepancies}")
    return result


def run() -> dict:
    gold = load_gold()
    predictions = load_predictions()
    independent = {method: independent_binary_and_threeway(gold, pred) for method, pred in predictions.items()}
    comparison = compare_to_c2(independent)
    result = {"independent_recomputation": independent, "comparison_to_c2_evaluation_results": comparison}
    with open(REPORTS_DIR / "C3_TASK2_3_INDEPENDENT_METRICS.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    return result


if __name__ == "__main__":
    result = run()
    print(f"all_match: {result['comparison_to_c2_evaluation_results']['all_match']}")
    # Task 3 focal claim check: pooled Primary_M7 coverage
    pm7_pooled = result["independent_recomputation"]["Primary_M7"]["pooled900"]["binary"]
    print(f"Primary_M7 pooled900: tp={pm7_pooled['tp']} fp={pm7_pooled['fp']} fn={pm7_pooled['fn']} tn={pm7_pooled['tn']} "
          f"precision={pm7_pooled['precision']:.4f} recall={pm7_pooled['recall']:.4f} f1={pm7_pooled['f1']:.4f} coverage={pm7_pooled['coverage']:.4f}")
