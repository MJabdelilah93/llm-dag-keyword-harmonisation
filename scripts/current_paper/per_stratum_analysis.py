"""
per_stratum_analysis.py
=========================
PHASE 1A / TASK 4 — per-stratum benchmark analysis for the primary model
(Full LLM-DAG) on the frozen 149-pair test set.

Reads results/test_predictions.csv and data/benchmark/test_set.csv (for
the stratum column) from the historical evidence tree, read-only. Writes
an aggregate-only CSV (counts and rates, no keyword strings).

Metrics are reported ONLY where mathematically meaningful: precision
requires at least one predicted match in the stratum; recall requires at
least one gold match. Where a denominator is zero, the field is written as
an empty string (not 0.0 or NaN, to avoid a misleading point estimate) and
the raw counts are always reported regardless.
"""
import csv
import os
import sys
from collections import defaultdict
from pathlib import Path


def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    return "non_match" if lbl in ("non-match", "non_match") else lbl


def main():
    evidence_root = os.environ.get("V1_EVIDENCE_ROOT")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=evidence_root)
    args = ap.parse_args()
    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")
    evidence_root = Path(args.evidence_root)

    pred_path = evidence_root / "results" / "test_predictions.csv"
    test_set_path = evidence_root / "data" / "benchmark" / "test_set.csv"
    for p in (pred_path, test_set_path):
        if not p.exists():
            sys.exit(f"ERROR: {p} not found")

    stratum_by_pair = {}
    with open(test_set_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            stratum_by_pair[r["pair_id"]] = r["stratum"]

    rows = []
    with open(pred_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["stratum"] = stratum_by_pair.get(r["pair_id"], "UNKNOWN")
            rows.append(r)

    by_stratum = defaultdict(list)
    for r in rows:
        by_stratum[r["stratum"]].append(r)

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "results" / "current_paper"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "per_stratum_performance.csv"

    fieldnames = ["stratum", "n_total", "n_gold_match", "n_gold_nonmatch", "n_gold_uncertain",
                  "pred_match", "pred_nonmatch", "pred_uncertain",
                  "TP", "FP", "FN", "TN", "precision", "recall", "f1", "coverage", "note"]

    out_rows = []
    for stratum in sorted(by_stratum.keys()):
        subset = by_stratum[stratum]
        n_total = len(subset)
        gold = [norm_label(r["gold_label"]) for r in subset]
        pred = [norm_label(r["Full_LLM_DAG"]) for r in subset]

        n_gold_match = sum(1 for g in gold if g == "match")
        n_gold_nonmatch = sum(1 for g in gold if g == "non_match")
        n_gold_uncertain = sum(1 for g in gold if g == "uncertain")
        pred_match = sum(1 for p in pred if p == "match")
        pred_nonmatch = sum(1 for p in pred if p == "non_match")
        pred_uncertain = sum(1 for p in pred if p == "uncertain")

        binary_pairs = [(g, p) for g, p in zip(gold, pred) if g != "uncertain"]
        decided_pairs = [(g, p) for g, p in binary_pairs if p != "uncertain"]
        tp = sum(1 for g, p in decided_pairs if g == "match" and p == "match")
        fp = sum(1 for g, p in decided_pairs if g != "match" and p == "match")
        fn_decided = sum(1 for g, p in decided_pairs if g == "match" and p != "match")
        fn_abstain = sum(1 for g, p in binary_pairs if g == "match" and p == "uncertain")
        fn = fn_decided + fn_abstain
        tn = sum(1 for g, p in decided_pairs if g != "match" and p != "match")

        coverage = (n_total - pred_uncertain) / n_total if n_total else 0.0

        notes = []
        precision = recall = f1 = ""
        if (tp + fp) > 0:
            precision = round(tp / (tp + fp), 4)
        else:
            notes.append("precision undefined: no predicted matches in stratum")
        if (tp + fn) > 0:
            recall = round(tp / (tp + fn), 4)
        else:
            notes.append("recall undefined: no gold matches in stratum")
        if precision != "" and recall != "":
            f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0
        else:
            notes.append("F1 not computed: precision or recall undefined")

        if n_total < 10:
            notes.append(f"SMALL SAMPLE (n={n_total}) -- point estimates unstable, counts are primary evidence")

        out_rows.append({
            "stratum": stratum, "n_total": n_total, "n_gold_match": n_gold_match,
            "n_gold_nonmatch": n_gold_nonmatch, "n_gold_uncertain": n_gold_uncertain,
            "pred_match": pred_match, "pred_nonmatch": pred_nonmatch, "pred_uncertain": pred_uncertain,
            "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": precision, "recall": recall, "f1": f1,
            "coverage": round(coverage, 4), "note": "; ".join(notes),
        })

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    print(f"Wrote: {out_csv}")
    for r in out_rows:
        print(f"  {r['stratum']}: n={r['n_total']} P={r['precision']} R={r['recall']} F1={r['f1']} cov={r['coverage']} | {r['note']}")


if __name__ == "__main__":
    main()
