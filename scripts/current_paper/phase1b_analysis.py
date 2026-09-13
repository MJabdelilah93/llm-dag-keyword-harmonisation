"""
phase1b_analysis.py
======================
PHASE 1B / TASKS 7-14 -- downstream analysis of the real OpenAI held-out
test run (N=149) and its cross-model comparison against the real Claude
Haiku 4.5 reruns. Reuses the exact statistical methodology already
established and disclosed in Phase 1A:
  - binary_metrics(): gold-uncertain excluded from the denominator,
    abstained gold-match pairs counted as FN (bootstrap_uncertainty_analysis.py)
  - percentile bootstrap, N=10000, seed=42, pair-level resampling with
    replacement, paired resampling for differences (same methodology)
  - three-way confusion matrix + per-class precision/recall/F1
    (three_way_analysis.py)
  - per-stratum counts-first reporting, metrics left blank (not 0) when a
    denominator is zero, small-sample note for n<10 (per_stratum_analysis.py)

Inputs:
  - results/current_paper/second_model/openai/test_run_real_test_1/raw_outputs.jsonl
    (LOCAL ONLY -- gitignored, contains restricted keyword text in
    justification fields; only decision/confidence/pair_id are read here)
  - results/current_paper/rerun_stability/run_real_run_{1..5}/raw_outputs.jsonl
    (same local-only restriction)
  - data/benchmark/test_set.csv (evidence root, for stratum + gold label)

Outputs (aggregate-only, no keyword strings, safe to commit) under
results/current_paper/phase1b/:
  - openai_test_binary_metrics.json
  - openai_test_bootstrap_ci.csv
  - openai_test_three_way_evaluation.json
  - openai_test_three_way_confusion_matrix.csv
  - openai_test_per_stratum_performance.csv
  - cross_model_agreement.json
  - cross_model_paired_bootstrap_differences.csv
  - cross_model_error_overlap.csv
  - cost_report.json
"""
import argparse
import csv
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

LABELS = ["match", "non_match", "uncertain"]
N_BOOT = 10000
SEED = 42


def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    return "non_match" if lbl in ("non-match", "non_match") else lbl


def load_jsonl(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return {r["pair_id"]: r for r in records}


def binary_metrics(gold, pred):
    n = len(gold)
    n_uncertain_pred = sum(1 for p in pred if p == "uncertain")
    coverage = (n - n_uncertain_pred) / n if n else 0.0
    binary_pairs = [(g, p) for g, p in zip(gold, pred) if g != "uncertain"]
    decided_pairs = [(g, p) for g, p in binary_pairs if p != "uncertain"]
    n_decided = len(decided_pairs)
    if not decided_pairs:
        precision = recall = 0.0
        tp = fp = fn = tn = 0
    else:
        tp = sum(1 for g, p in decided_pairs if g == "match" and p == "match")
        fp = sum(1 for g, p in decided_pairs if g != "match" and p == "match")
        fn_decided = sum(1 for g, p in decided_pairs if g == "match" and p != "match")
        fn_abstain = sum(1 for g, p in binary_pairs if g == "match" and p == "uncertain")
        fn = fn_decided + fn_abstain
        tn = sum(1 for g, p in decided_pairs if g != "match" and p != "match")
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "coverage": coverage,
            "n_decided": n_decided, "TP": tp, "FP": fp, "FN": fn, "TN": tn}


def percentile(sorted_vals, p):
    idx = int(round(p * (len(sorted_vals) - 1)))
    return sorted_vals[idx]


def cohens_kappa(rater1, rater2, labels):
    n = len(rater1)
    po = sum(1 for a, b in zip(rater1, rater2) if a == b) / n
    r1_freq = {lbl: sum(1 for x in rater1 if x == lbl) / n for lbl in labels}
    r2_freq = {lbl: sum(1 for x in rater2 if x == lbl) / n for lbl in labels}
    pe = sum(r1_freq[lbl] * r2_freq[lbl] for lbl in labels)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def majority_vote(decisions_per_run, pair_id):
    """Majority label across raters for one pair. Ties (only possible with
    an even split, not expected given the near-unanimous 5-rater stability
    result -- see real_phase1b_stability_report.json) break deterministically
    toward the first run's decision, then alphabetically, so the function is
    total and reproducible regardless."""
    first_run_id = sorted(decisions_per_run)[0]
    tie_break_label = decisions_per_run[first_run_id][pair_id]
    votes = [decisions_per_run[rid][pair_id] for rid in decisions_per_run]
    counts = defaultdict(int)
    for v in votes:
        counts[v] += 1
    max_count = max(counts.values())
    tied = sorted(lbl for lbl, c in counts.items() if c == max_count)
    if tie_break_label in tied:
        return tie_break_label
    return tied[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"))
    args = ap.parse_args()
    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")
    evidence_root = Path(args.evidence_root)
    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "results" / "current_paper" / "phase1b"
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- gold labels + strata (evidence root, read-only) ---
    gold_by_pair, stratum_by_pair = {}, {}
    with open(evidence_root / "data" / "benchmark" / "test_set.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            gold_by_pair[r["pair_id"]] = norm_label(r["gold_label"])
            stratum_by_pair[r["pair_id"]] = r["stratum"]
    pair_ids = sorted(gold_by_pair.keys())
    if len(pair_ids) != 149:
        sys.exit(f"ERROR: expected 149 pairs, found {len(pair_ids)}")

    # --- OpenAI held-out test run (local-only raw file, aggregate-only output) ---
    openai_dir = repo_root / "results" / "current_paper" / "second_model" / "openai" / "test_run_real_test_1"
    openai_records = load_jsonl(openai_dir / "raw_outputs.jsonl")
    openai_decision = {pid: openai_records[pid]["guard_decision"] for pid in pair_ids}
    openai_confidence = {pid: openai_records[pid]["guard_confidence"] for pid in pair_ids}

    # --- Claude real reruns (local-only raw files) ---
    claude_run_ids = [f"real_run_{i}" for i in range(1, 6)]
    claude_records = {}
    for rid in claude_run_ids:
        rd = repo_root / "results" / "current_paper" / "rerun_stability" / f"run_{rid}"
        claude_records[rid] = load_jsonl(rd / "raw_outputs.jsonl")
    claude_decisions_per_run = {rid: {pid: claude_records[rid][pid]["guard_decision"] for pid in pair_ids}
                                 for rid in claude_run_ids}
    claude_majority = {pid: majority_vote(claude_decisions_per_run, pid) for pid in pair_ids}

    gold = [gold_by_pair[pid] for pid in pair_ids]
    openai_pred = [openai_decision[pid] for pid in pair_ids]
    claude_pred = [claude_majority[pid] for pid in pair_ids]

    # =====================================================================
    # Task 7: OpenAI binary metrics + bootstrap CI
    # =====================================================================
    point = binary_metrics(gold, openai_pred)
    with open(out_dir / "openai_test_binary_metrics.json", "w", encoding="utf-8") as f:
        json.dump({k: (round(v, 4) if isinstance(v, float) else v) for k, v in point.items()}, f, indent=2)

    rng = random.Random(SEED)
    n = len(pair_ids)
    boot = {"precision": [], "recall": [], "f1": [], "coverage": []}
    # paired-difference bootstrap: OpenAI vs Claude, SAME resample indices
    diff = {"precision": [], "recall": [], "f1": []}
    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]
        g_s = [gold[i] for i in idx]
        o_s = [openai_pred[i] for i in idx]
        c_s = [claude_pred[i] for i in idx]
        o_m = binary_metrics(g_s, o_s)
        c_m = binary_metrics(g_s, c_s)
        for k in boot:
            boot[k].append(o_m[k])
        for k in diff:
            diff[k].append(o_m[k] - c_m[k])

    with open(out_dir / "openai_test_bootstrap_ci.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "point_estimate", "ci_2.5", "ci_97.5"])
        for metric in ["precision", "recall", "f1", "coverage"]:
            vals = sorted(boot[metric])
            w.writerow([metric, round(point[metric], 4),
                        round(percentile(vals, 0.025), 4), round(percentile(vals, 0.975), 4)])
    print(f"OpenAI test: P={point['precision']:.4f} R={point['recall']:.4f} F1={point['f1']:.4f} "
          f"Cov={point['coverage']:.4f} (n_decided={point['n_decided']})")

    # =====================================================================
    # Task 9 (part): three-way evaluation, including uncertain-class behaviour
    # =====================================================================
    cm = {g: {p: 0 for p in LABELS} for g in LABELS}
    for g, p in zip(gold, openai_pred):
        cm[g][p] += 1
    accuracy = sum(1 for g, p in zip(gold, openai_pred) if g == p) / n

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

    three_way = {
        "n": n, "confusion_matrix_gold_rows_pred_cols": cm, "accuracy": round(accuracy, 4),
        "per_class": per_class, "macro_f1": round(macro_f1, 4) if macro_f1 is not None else None,
        "uncertain_class_precision": per_class["uncertain"]["precision"],
        "uncertain_class_recall": per_class["uncertain"]["recall"],
        "n_gold_uncertain": per_class["uncertain"]["support_gold"],
        "n_pred_uncertain": sum(cm[g]["uncertain"] for g in LABELS),
    }
    with open(out_dir / "openai_test_three_way_evaluation.json", "w", encoding="utf-8") as f:
        json.dump(three_way, f, indent=2)
    with open(out_dir / "openai_test_three_way_confusion_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gold\\pred"] + LABELS)
        for g in LABELS:
            w.writerow([g] + [cm[g][p] for p in LABELS])
    print(f"OpenAI three-way accuracy={accuracy:.4f}, macro_f1={macro_f1}")

    # =====================================================================
    # Task 9 (part): per-stratum performance, counts-first
    # =====================================================================
    by_stratum = defaultdict(list)
    for pid in pair_ids:
        by_stratum[stratum_by_pair[pid]].append(pid)

    fieldnames = ["stratum", "n_total", "n_gold_match", "n_gold_nonmatch", "n_gold_uncertain",
                  "pred_match", "pred_nonmatch", "pred_uncertain",
                  "TP", "FP", "FN", "TN", "precision", "recall", "f1", "coverage", "note"]
    stratum_rows = []
    for stratum in sorted(by_stratum.keys()):
        ids = by_stratum[stratum]
        g_s = [gold_by_pair[pid] for pid in ids]
        p_s = [openai_decision[pid] for pid in ids]
        n_total = len(ids)
        n_gold_match = sum(1 for g in g_s if g == "match")
        n_gold_nonmatch = sum(1 for g in g_s if g == "non_match")
        n_gold_uncertain = sum(1 for g in g_s if g == "uncertain")
        pred_match = sum(1 for p in p_s if p == "match")
        pred_nonmatch = sum(1 for p in p_s if p == "non_match")
        pred_uncertain = sum(1 for p in p_s if p == "uncertain")
        m = binary_metrics(g_s, p_s)
        notes = []
        precision = round(m["precision"], 4) if (m["TP"] + m["FP"]) > 0 else ""
        if precision == "":
            notes.append("precision undefined: no predicted matches in stratum")
        recall = round(m["recall"], 4) if (m["TP"] + m["FN"]) > 0 else ""
        if recall == "":
            notes.append("recall undefined: no gold matches in stratum")
        f1 = round(m["f1"], 4) if (precision != "" and recall != "") else ""
        if f1 == "":
            notes.append("F1 not computed: precision or recall undefined")
        if n_total < 10:
            notes.append(f"SMALL SAMPLE (n={n_total}) -- point estimates unstable, counts are primary evidence")
        stratum_rows.append({"stratum": stratum, "n_total": n_total, "n_gold_match": n_gold_match,
                              "n_gold_nonmatch": n_gold_nonmatch, "n_gold_uncertain": n_gold_uncertain,
                              "pred_match": pred_match, "pred_nonmatch": pred_nonmatch,
                              "pred_uncertain": pred_uncertain, "TP": m["TP"], "FP": m["FP"],
                              "FN": m["FN"], "TN": m["TN"], "precision": precision, "recall": recall,
                              "f1": f1, "coverage": round(m["coverage"], 4), "note": "; ".join(notes)})
    with open(out_dir / "openai_test_per_stratum_performance.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in stratum_rows:
            w.writerow(r)

    # =====================================================================
    # Task 10-11: cross-model agreement, Cohen's kappa, error overlap
    # =====================================================================
    overall_agreement = sum(1 for pid in pair_ids if claude_majority[pid] == openai_decision[pid]) / n
    kappa = cohens_kappa(claude_pred, openai_pred, LABELS)

    claude_wrong = {pid for pid in pair_ids if claude_majority[pid] != gold_by_pair[pid]
                     and gold_by_pair[pid] != "uncertain"}
    openai_wrong = {pid for pid in pair_ids if openai_decision[pid] != gold_by_pair[pid]
                     and gold_by_pair[pid] != "uncertain"}
    both_wrong = claude_wrong & openai_wrong
    only_claude_wrong = claude_wrong - openai_wrong
    only_openai_wrong = openai_wrong - claude_wrong

    disagreement_rows = []
    for pid in pair_ids:
        if claude_majority[pid] != openai_decision[pid]:
            disagreement_rows.append({
                "pair_id": pid, "gold_label": gold_by_pair[pid], "stratum": stratum_by_pair[pid],
                "claude_majority_decision": claude_majority[pid], "openai_decision": openai_decision[pid],
                "openai_confidence": openai_confidence[pid],
                "claude_matches_gold": claude_majority[pid] == gold_by_pair[pid],
                "openai_matches_gold": openai_decision[pid] == gold_by_pair[pid],
            })

    cross_model = {
        "n_pairs": n,
        "overall_exact_agreement_3way": round(overall_agreement, 4),
        "cohens_kappa_3way": round(kappa, 4),
        "n_disagreements": len(disagreement_rows),
        "n_claude_wrong_vs_gold_decided_only": len(claude_wrong),
        "n_openai_wrong_vs_gold_decided_only": len(openai_wrong),
        "n_both_wrong": len(both_wrong),
        "n_only_claude_wrong": len(only_claude_wrong),
        "n_only_openai_wrong": len(only_openai_wrong),
        "error_overlap_pair_ids": {
            "both_wrong": sorted(both_wrong), "only_claude_wrong": sorted(only_claude_wrong),
            "only_openai_wrong": sorted(only_openai_wrong),
        },
        "disagreements_vs_gold": disagreement_rows,
    }
    with open(out_dir / "cross_model_agreement.json", "w", encoding="utf-8") as f:
        json.dump(cross_model, f, indent=2)

    with open(out_dir / "cross_model_error_overlap.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "n_pairs", "pair_ids"])
        w.writerow(["both_wrong", len(both_wrong), ";".join(sorted(both_wrong))])
        w.writerow(["only_claude_wrong", len(only_claude_wrong), ";".join(sorted(only_claude_wrong))])
        w.writerow(["only_openai_wrong", len(only_openai_wrong), ";".join(sorted(only_openai_wrong))])

    # =====================================================================
    # Task 13: paired bootstrap statistical comparisons (OpenAI - Claude)
    # =====================================================================
    with open(out_dir / "cross_model_paired_bootstrap_differences.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["comparison", "metric", "point_diff", "ci_2.5", "ci_97.5", "ci_excludes_zero"])
        claude_point = binary_metrics(gold, claude_pred)
        for metric in ["precision", "recall", "f1"]:
            point_diff = point[metric] - claude_point[metric]
            vals = sorted(diff[metric])
            lo, hi = percentile(vals, 0.025), percentile(vals, 0.975)
            w.writerow(["OpenAI_minus_Claude", metric, round(point_diff, 4), round(lo, 4), round(hi, 4),
                        (lo > 0) or (hi < 0)])
    print(f"Cross-model: agreement={overall_agreement:.4f}, Cohen's kappa={kappa:.4f}, "
          f"disagreements={len(disagreement_rows)}, both_wrong={len(both_wrong)}, "
          f"only_claude_wrong={len(only_claude_wrong)}, only_openai_wrong={len(only_openai_wrong)}")

    # =====================================================================
    # Task 15: exact cost report by provider/model/run
    # =====================================================================
    cost_report = {"anthropic": {"runs": []}, "openai": {"runs": []}}
    anthropic_total = 0.0
    for rid in claude_run_ids:
        m = json.loads((repo_root / "results" / "current_paper" / "rerun_stability" / f"run_{rid}" / "run_manifest.json").read_text())
        cost_report["anthropic"]["runs"].append({
            "run_id": rid, "n_pairs": m["n_pairs"], "input_tokens": m["total_input_tokens"],
            "output_tokens": m["total_output_tokens"], "cost_usd": m["total_estimated_cost_usd"]})
        anthropic_total += m["total_estimated_cost_usd"]
    cost_report["anthropic"]["total_cost_usd"] = round(anthropic_total, 4)

    OPENAI_IN_PER_1M, OPENAI_OUT_PER_1M = 0.20, 1.25
    openai_total = 0.0
    for run_kind, run_id, manifest_name in [("dev", "real_dev_1", "dev_manifest.json"),
                                             ("test", "real_test_1", "test_manifest.json")]:
        m = json.loads((repo_root / "results" / "current_paper" / "second_model" / "openai" /
                         f"{run_kind}_run_{run_id}" / manifest_name).read_text())
        cost = (m["total_input_tokens"] / 1_000_000 * OPENAI_IN_PER_1M +
                m["total_output_tokens"] / 1_000_000 * OPENAI_OUT_PER_1M)
        cost_report["openai"]["runs"].append({
            "run_id": f"{run_kind}_{run_id}", "n_pairs": m["n_pairs"], "input_tokens": m["total_input_tokens"],
            "output_tokens": m["total_output_tokens"], "reasoning_tokens": m["total_reasoning_tokens"],
            "cost_usd": round(cost, 4)})
        openai_total += cost
    cost_report["openai"]["total_cost_usd"] = round(openai_total, 4)
    cost_report["combined_total_cost_usd"] = round(anthropic_total + openai_total, 4)
    cost_report["authorised_hard_stop_usd"] = 2.00
    cost_report["pct_of_hard_stop_used"] = round(100 * (anthropic_total + openai_total) / 2.00, 2)

    with open(out_dir / "cost_report.json", "w", encoding="utf-8") as f:
        json.dump(cost_report, f, indent=2)
    print(f"\nTotal cost: Anthropic=${anthropic_total:.4f} + OpenAI=${openai_total:.4f} "
          f"= ${anthropic_total + openai_total:.4f} of $2.00 authorised "
          f"({cost_report['pct_of_hard_stop_used']}%)")

    print(f"\nAll outputs written to: {out_dir}")


if __name__ == "__main__":
    main()
