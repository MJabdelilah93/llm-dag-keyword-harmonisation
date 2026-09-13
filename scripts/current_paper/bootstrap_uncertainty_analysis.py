"""
bootstrap_uncertainty_analysis.py
====================================
PHASE 1A / TASK 2 — full uncertainty analysis for all 7 methods, plus
paired-difference CIs for Full_LLM_DAG vs. B3 and vs. B6.

Reads results/test_predictions.csv from the historical evidence tree
read-only (contains real keyword strings — not copied out). Writes
aggregate-only CSV outputs (no keyword strings) into the repair branch's
results/current_paper/.

Bootstrap procedure (documented, fixed seed, reproducible):
  - Pair-level resampling WITH replacement over all 149 test pairs
    (not just the "decided" subset -- this correctly propagates
    uncertainty in coverage/abstention into the resampled metrics).
  - N = 10,000 resamples, seed = 42 (Python's random.Random(42), NOT
    numpy's, to keep this dependency-light and independently checkable).
  - Per resample, per method: recompute the full binary_metrics() (gold-
    uncertain excluded from the binary denominator, exactly as in v1).
  - 95% CI = 2.5th/97.5th percentile of the resampled statistic
    (percentile bootstrap -- the simplest defensible choice given n=149;
    not bias-corrected, which is noted explicitly in the summary as a
    conservative-not-precise choice).
  - Paired differences (Full_LLM_DAG - B3, Full_LLM_DAG - B6) use the
    SAME resample index list per iteration for both methods, so the CI on
    the difference correctly accounts for the pairing (same test pairs).
"""
import argparse
import csv
import os
import random
import sys
from pathlib import Path

METHODS = ["Full_LLM_DAG", "B1_Exact", "B2_Normalised", "B3_JaroWinkler",
           "B4_TFIDF", "B5_Embedding", "B6_NaiveLLM"]
N_BOOT = 10000
SEED = 42


def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    return "non_match" if lbl in ("non-match", "non_match") else lbl


def binary_metrics(gold, pred):
    n = len(gold)
    n_uncertain_pred = sum(1 for p in pred if p == "uncertain")
    coverage = (n - n_uncertain_pred) / n if n else 0.0
    binary_pairs = [(g, p) for g, p in zip(gold, pred) if g != "uncertain"]
    decided_pairs = [(g, p) for g, p in binary_pairs if p != "uncertain"]
    n_decided = len(decided_pairs)
    gold_match_n = sum(1 for g, _ in binary_pairs if g == "match")
    pred_match_n = sum(1 for _, p in decided_pairs if p == "match")
    if not decided_pairs:
        precision = recall = 0.0
    else:
        tp = sum(1 for g, p in decided_pairs if g == "match" and p == "match")
        fp = sum(1 for g, p in decided_pairs if g != "match" and p == "match")
        fn_decided = sum(1 for g, p in decided_pairs if g == "match" and p != "match")
        fn_abstain = sum(1 for g, p in binary_pairs if g == "match" and p == "uncertain")
        fn = fn_decided + fn_abstain
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "coverage": coverage,
            "n_decided": n_decided, "gold_match_n": gold_match_n, "pred_match_n": pred_match_n}


def percentile(sorted_vals, p):
    idx = int(round(p * (len(sorted_vals) - 1)))
    return sorted_vals[idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"))
    args = ap.parse_args()
    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")

    evidence_root = Path(args.evidence_root)
    pred_path = evidence_root / "results" / "test_predictions.csv"
    if not pred_path.exists():
        sys.exit(f"ERROR: {pred_path} not found")

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "results" / "current_paper"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    with open(pred_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    n = len(rows)
    gold = [norm_label(r["gold_label"]) for r in rows]
    preds = {m: [norm_label(r[m]) for r in rows] for m in METHODS}

    # Point estimates
    point = {m: binary_metrics(gold, preds[m]) for m in METHODS}

    rng = random.Random(SEED)
    boot = {m: {"precision": [], "recall": [], "f1": [], "coverage": []} for m in METHODS}
    diff_b3 = {"precision": [], "recall": [], "f1": []}
    diff_b6 = {"precision": [], "recall": [], "f1": []}

    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]
        g_s = [gold[i] for i in idx]
        m_results = {}
        for m in METHODS:
            p_s = [preds[m][i] for i in idx]
            res = binary_metrics(g_s, p_s)
            m_results[m] = res
            boot[m]["precision"].append(res["precision"])
            boot[m]["recall"].append(res["recall"])
            boot[m]["f1"].append(res["f1"])
            boot[m]["coverage"].append(res["coverage"])
        diff_b3["precision"].append(m_results["Full_LLM_DAG"]["precision"] - m_results["B3_JaroWinkler"]["precision"])
        diff_b3["recall"].append(m_results["Full_LLM_DAG"]["recall"] - m_results["B3_JaroWinkler"]["recall"])
        diff_b3["f1"].append(m_results["Full_LLM_DAG"]["f1"] - m_results["B3_JaroWinkler"]["f1"])
        diff_b6["precision"].append(m_results["Full_LLM_DAG"]["precision"] - m_results["B6_NaiveLLM"]["precision"])
        diff_b6["recall"].append(m_results["Full_LLM_DAG"]["recall"] - m_results["B6_NaiveLLM"]["recall"])
        diff_b6["f1"].append(m_results["Full_LLM_DAG"]["f1"] - m_results["B6_NaiveLLM"]["f1"])

    # Write per-method CI CSV
    out_csv = out_dir / "bootstrap_uncertainty_per_method.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["method", "metric", "point_estimate", "ci_2.5", "ci_97.5", "n_decided",
                    "gold_match_n", "pred_match_n"])
        for m in METHODS:
            for metric in ["precision", "recall", "f1", "coverage"]:
                vals = sorted(boot[m][metric])
                w.writerow([m, metric, round(point[m][metric], 4),
                            round(percentile(vals, 0.025), 4), round(percentile(vals, 0.975), 4),
                            point[m]["n_decided"], point[m]["gold_match_n"], point[m]["pred_match_n"]])
    print(f"Wrote: {out_csv}")

    out_diff = out_dir / "bootstrap_uncertainty_differences.csv"
    with open(out_diff, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["comparison", "metric", "point_diff", "ci_2.5", "ci_97.5", "ci_excludes_zero"])
        for label, diffs, other in [("Full_LLM_DAG_minus_B3", diff_b3, "B3_JaroWinkler"),
                                     ("Full_LLM_DAG_minus_B6", diff_b6, "B6_NaiveLLM")]:
            for metric in ["precision", "recall", "f1"]:
                point_diff = point["Full_LLM_DAG"][metric] - point[other][metric]
                vals = sorted(diffs[metric])
                lo, hi = percentile(vals, 0.025), percentile(vals, 0.975)
                excludes_zero = (lo > 0) or (hi < 0)
                w.writerow([label, metric, round(point_diff, 4), round(lo, 4), round(hi, 4), excludes_zero])
    print(f"Wrote: {out_diff}")

    print(f"\nBootstrap: N={N_BOOT}, seed={SEED}, pair-level resampling with replacement, percentile CI")
    print(f"n test pairs = {n}")
    for m in METHODS:
        print(f"{m}: F1={point[m]['f1']:.4f} P={point[m]['precision']:.4f} R={point[m]['recall']:.4f} Cov={point[m]['coverage']:.4f}")


if __name__ == "__main__":
    main()
