"""
three_way_analysis.py
========================
PHASE 1A / TASK 5 — secondary three-way (match/non_match/uncertain)
evaluation for Full LLM-DAG on the frozen 149-pair test set.

Reads results/test_predictions.csv from the historical evidence tree,
read-only. Writes aggregate-only outputs (confusion matrix counts, no
keyword strings).
"""
import csv
import json
import os
import sys
from pathlib import Path

LABELS = ["match", "non_match", "uncertain"]


def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    return "non_match" if lbl in ("non-match", "non_match") else lbl


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"))
    args = ap.parse_args()
    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")
    pred_path = Path(args.evidence_root) / "results" / "test_predictions.csv"
    if not pred_path.exists():
        sys.exit(f"ERROR: {pred_path} not found")

    gold, pred = [], []
    with open(pred_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            gold.append(norm_label(r["gold_label"]))
            pred.append(norm_label(r["Full_LLM_DAG"]))
    n = len(gold)

    # 3x3 confusion matrix: rows = gold, cols = pred
    cm = {g: {p: 0 for p in LABELS} for g in LABELS}
    for g, p in zip(gold, pred):
        cm[g][p] += 1

    accuracy = sum(1 for g, p in zip(gold, pred) if g == p) / n

    per_class = {}
    for cls in LABELS:
        tp = cm[cls][cls]
        fp = sum(cm[g][cls] for g in LABELS if g != cls)
        fn = sum(cm[cls][p] for p in LABELS if p != cls)
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * precision * recall / (precision + recall)
              if (precision is not None and recall is not None and (precision + recall) > 0) else
              (0.0 if precision is not None and recall is not None else None))
        per_class[cls] = {"tp": tp, "fp": fp, "fn": fn,
                           "precision": round(precision, 4) if precision is not None else None,
                           "recall": round(recall, 4) if recall is not None else None,
                           "f1": round(f1, 4) if f1 is not None else None,
                           "support_gold": sum(cm[cls][p] for p in LABELS)}

    valid_f1 = [v["f1"] for v in per_class.values() if v["f1"] is not None]
    macro_f1 = sum(valid_f1) / len(valid_f1) if valid_f1 else None

    report = {
        "n": n,
        "confusion_matrix_gold_rows_pred_cols": cm,
        "accuracy": round(accuracy, 4),
        "per_class": per_class,
        "macro_f1": round(macro_f1, 4) if macro_f1 is not None else None,
        "uncertain_class_precision": per_class["uncertain"]["precision"],
        "uncertain_class_recall": per_class["uncertain"]["recall"],
    }

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "results" / "current_paper"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "three_way_evaluation.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    out_csv = out_dir / "three_way_confusion_matrix.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gold\\pred"] + LABELS)
        for g in LABELS:
            w.writerow([g] + [cm[g][p] for p in LABELS])

    print(json.dumps(report, indent=2))
    print(f"\nWrote: {out_json}")
    print(f"Wrote: {out_csv}")


if __name__ == "__main__":
    main()
