"""
analyze_rerun_stability.py
=============================
PHASE 1A / TASK 6 — stability-outcome analysis, pre-defined in advance of
any real rerun. Accepts N run directories (each produced by
run_single_rerun.py) and the historical original test run, and computes
every stability metric Task 6 specifies. Works identically whether the
runs are real (Phase 1B) or synthetic dry-run validation (Phase 1A) --
the mode is read from each run's own manifest and loudly flagged in the
output if any input run is synthetic.
"""
import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

LABELS = ["match", "non_match", "uncertain"]


def load_run(run_dir: Path):
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    records = []
    with open(run_dir / "raw_outputs.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    by_pair = {r["pair_id"]: r for r in records}
    return manifest, by_pair


def load_historical_reference(evidence_root: Path):
    """The original 2026-04 test run, treated as an additional reference
    run, never overwritten. Loaded from results/test_predictions.csv
    (decision only) -- confidence scores for the historical run would
    require results/llm_logs/test_raw_outputs.jsonl (restricted, real
    keyword strings); this function reads only the decision column, which
    is sufficient for label-agreement metrics."""
    import csv as _csv
    path = evidence_root / "results" / "test_predictions.csv"
    by_pair = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in _csv.DictReader(f):
            lbl = str(r["Full_LLM_DAG"]).strip().lower()
            lbl = "non_match" if lbl in ("non-match", "non_match") else lbl
            by_pair[r["pair_id"]] = {"guard_decision": lbl, "guard_confidence": None}
    return {"run_id": "historical_reference", "is_synthetic": False,
            "note": "original 2026-04 test run, decision-only (no confidence available without restricted logs)"}, by_pair


def fleiss_kappa(pair_ids, run_decisions_list):
    """run_decisions_list: list of {pair_id: decision} dicts, one per rater."""
    n_raters = len(run_decisions_list)
    n_items = len(pair_ids)
    category_counts = defaultdict(lambda: defaultdict(int))
    for rd in run_decisions_list:
        for pid in pair_ids:
            category_counts[pid][rd[pid]] += 1

    p_j = defaultdict(float)
    for pid in pair_ids:
        for cat in LABELS:
            p_j[cat] += category_counts[pid][cat]
    total_assignments = n_items * n_raters
    for cat in LABELS:
        p_j[cat] /= total_assignments

    P_i = {}
    for pid in pair_ids:
        s = sum(category_counts[pid][cat] ** 2 for cat in LABELS)
        P_i[pid] = (s - n_raters) / (n_raters * (n_raters - 1)) if n_raters > 1 else 1.0
    P_bar = sum(P_i.values()) / n_items
    P_bar_e = sum(v ** 2 for v in p_j.values())
    if P_bar_e == 1.0:
        return 1.0 if P_bar == 1.0 else 0.0
    kappa = (P_bar - P_bar_e) / (1 - P_bar_e)
    return kappa


def binary_metrics_from_decisions(gold, pred):
    binary_pairs = [(g, p) for g, p in zip(gold, pred) if g != "uncertain"]
    decided_pairs = [(g, p) for g, p in binary_pairs if p != "uncertain"]
    n = len(gold)
    coverage = sum(1 for p in pred if p != "uncertain") / n if n else 0.0
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
    return {"precision": precision, "recall": recall, "f1": f1, "coverage": coverage}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", required=True)
    ap.add_argument("--run-dirs", nargs="+", required=True,
                     help="Paths to run_<id> directories to analyze (>=2)")
    ap.add_argument("--include-historical", action="store_true",
                     help="Also load and include the historical reference run")
    ap.add_argument("--gold-source", choices=["evidence_root"], default="evidence_root")
    ap.add_argument("--out-prefix", required=True, help="Output filename prefix, e.g. dry_run_synthetic")
    args = ap.parse_args()

    evidence_root = Path(args.evidence_root)
    runs = {}
    for rd in args.run_dirs:
        rd_path = Path(rd)
        manifest, by_pair = load_run(rd_path)
        runs[manifest["run_id"]] = (manifest, by_pair)

    if args.include_historical:
        manifest, by_pair = load_historical_reference(evidence_root)
        runs["historical_reference"] = (manifest, by_pair)

    if len(runs) < 2:
        sys.exit("ERROR: need at least 2 runs to analyze stability")

    any_synthetic = any(m.get("is_synthetic") for m, _ in runs.values())

    # gold labels from the frozen test set
    gold_by_pair = {}
    with open(evidence_root / "data" / "benchmark" / "test_set.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            lbl = str(r["gold_label"]).strip().lower()
            gold_by_pair[r["pair_id"]] = "non_match" if lbl in ("non-match", "non_match") else lbl
    pair_ids = sorted(gold_by_pair.keys())

    run_ids = sorted(runs.keys())
    decisions = {rid: {pid: runs[rid][1][pid]["guard_decision"] for pid in pair_ids} for rid in run_ids}

    # pairwise exact agreement
    pairwise_agreement = {}
    for r1, r2 in combinations(run_ids, 2):
        agree = sum(1 for pid in pair_ids if decisions[r1][pid] == decisions[r2][pid])
        pairwise_agreement[f"{r1}_vs_{r2}"] = round(agree / len(pair_ids), 4)

    # number of pairs whose label ever differs across all runs
    n_ever_changed = sum(1 for pid in pair_ids
                          if len({decisions[rid][pid] for rid in run_ids}) > 1)

    # transition matrix: count, over all pairs of runs, how many times a
    # pair's label crossed each category boundary
    transition_counts = Counter()
    for r1, r2 in combinations(run_ids, 2):
        for pid in pair_ids:
            a, b = decisions[r1][pid], decisions[r2][pid]
            if a != b:
                key = " <-> ".join(sorted([a, b]))
                transition_counts[key] += 1

    kappa = fleiss_kappa(pair_ids, [decisions[rid] for rid in run_ids])

    # confidence-score variation (only for runs that have confidence, i.e. exclude historical)
    conf_runs = [rid for rid in run_ids if runs[rid][1][pair_ids[0]].get("guard_confidence") is not None]
    confidence_std_per_pair = {}
    if len(conf_runs) >= 2:
        for pid in pair_ids:
            vals = [runs[rid][1][pid]["guard_confidence"] for rid in conf_runs]
            if all(v is not None for v in vals):
                confidence_std_per_pair[pid] = statistics.pstdev(vals)
    mean_confidence_std = (statistics.mean(confidence_std_per_pair.values())
                            if confidence_std_per_pair else None)

    gold = [gold_by_pair[pid] for pid in pair_ids]
    per_run_metrics = {rid: binary_metrics_from_decisions(gold, [decisions[rid][pid] for pid in pair_ids])
                        for rid in run_ids}
    f1_values = [m["f1"] for m in per_run_metrics.values()]
    precision_values = [m["precision"] for m in per_run_metrics.values()]
    recall_values = [m["recall"] for m in per_run_metrics.values()]
    coverage_values = [m["coverage"] for m in per_run_metrics.values()]

    report = {
        "ANY_SYNTHETIC_RUNS_INCLUDED": any_synthetic,
        "WARNING": ("At least one input run is a SYNTHETIC DRY-RUN. This report validates the "
                    "analysis code's mechanics only and has NO evidential value about the real "
                    "model's rerun-stability.") if any_synthetic else None,
        "n_runs_analyzed": len(run_ids),
        "run_ids": run_ids,
        "n_pairs": len(pair_ids),
        "pairwise_exact_label_agreement": pairwise_agreement,
        "n_pairs_ever_changing_label": n_ever_changed,
        "pct_pairs_ever_changing_label": round(100 * n_ever_changed / len(pair_ids), 2),
        "transition_matrix_counts": dict(transition_counts),
        "fleiss_kappa_all_runs": round(kappa, 4),
        "mean_pairwise_confidence_stdev": round(mean_confidence_std, 4) if mean_confidence_std is not None else None,
        "per_run_metrics": {rid: {k: round(v, 4) for k, v in m.items()} for rid, m in per_run_metrics.items()},
        "f1_range": {"min": round(min(f1_values), 4), "max": round(max(f1_values), 4)},
        "precision_range": {"min": round(min(precision_values), 4), "max": round(max(precision_values), 4)},
        "recall_range": {"min": round(min(recall_values), 4), "max": round(max(recall_values), 4)},
        "coverage_range": {"min": round(min(coverage_values), 4), "max": round(max(coverage_values), 4)},
    }

    repo_root = Path(__file__).resolve().parents[3]
    out_dir = repo_root / "results" / "current_paper" / "rerun_stability"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.out_prefix}_stability_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
