"""
phase1b_reconciliation.py
============================
Phase 1B FINAL RECONCILIATION AUDIT -- zero-cost, no-network. Recomputes
every count independently from already-generated local artefacts (no
model is called, no file from the original real runs is modified). This
script exists to let the reconciliation audit's numbers be independently
re-derived by a reader, rather than trusted from prose alone.

Reads (local-only, restricted, gitignored -- decision/confidence/pair_id
fields only are used, never keyword text):
  - results/current_paper/second_model/openai/test_run_real_test_1/raw_outputs.jsonl
  - results/current_paper/rerun_stability/run_real_run_{1..5}/raw_outputs.jsonl
  - data/benchmark/test_set.csv (evidence root)

Writes (aggregate-only, safe to commit) under results/current_paper/phase1b/:
  - reconciliation_coverage_breakdown.json
  - reconciliation_binary_contingency.json
  - reconciliation_threeway_contingency.json
  - reconciliation_claude_threeway_confusion_matrix.csv
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

LABELS = ["match", "non_match", "uncertain"]


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


def majority_vote(decisions_per_run, pair_id):
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


def cohens_kappa(rater1, rater2, labels):
    n = len(rater1)
    po = sum(1 for a, b in zip(rater1, rater2) if a == b) / n
    r1_freq = {lbl: sum(1 for x in rater1 if x == lbl) / n for lbl in labels}
    r2_freq = {lbl: sum(1 for x in rater2 if x == lbl) / n for lbl in labels}
    pe = sum(r1_freq[lbl] * r2_freq[lbl] for lbl in labels)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


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

    gold_by_pair, stratum_by_pair = {}, {}
    with open(evidence_root / "data" / "benchmark" / "test_set.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            gold_by_pair[r["pair_id"]] = norm_label(r["gold_label"])
            stratum_by_pair[r["pair_id"]] = r["stratum"]
    pair_ids = sorted(gold_by_pair.keys())
    assert len(pair_ids) == 149

    openai_dir = repo_root / "results" / "current_paper" / "second_model" / "openai" / "test_run_real_test_1"
    openai_records = load_jsonl(openai_dir / "raw_outputs.jsonl")
    openai_pred_by_pair = {pid: openai_records[pid]["guard_decision"] for pid in pair_ids}

    claude_run_ids = [f"real_run_{i}" for i in range(1, 6)]
    claude_records = {}
    for rid in claude_run_ids:
        rd = repo_root / "results" / "current_paper" / "rerun_stability" / f"run_{rid}"
        claude_records[rid] = load_jsonl(rd / "raw_outputs.jsonl")
    claude_decisions_per_run = {rid: {pid: claude_records[rid][pid]["guard_decision"] for pid in pair_ids}
                                 for rid in claude_run_ids}
    claude_pred_by_pair = {pid: majority_vote(claude_decisions_per_run, pid) for pid in pair_ids}

    gold_binary_ids = [pid for pid in pair_ids if gold_by_pair[pid] != "uncertain"]
    assert len(gold_binary_ids) == 124, len(gold_binary_ids)

    # =====================================================================
    # SECTION 1: coverage / n_decided reconciliation
    # =====================================================================
    n_all = len(pair_ids)
    openai_abstain_all = sum(1 for pid in pair_ids if openai_pred_by_pair[pid] == "uncertain")
    openai_definitive_all = n_all - openai_abstain_all

    openai_abstain_binary = sum(1 for pid in gold_binary_ids if openai_pred_by_pair[pid] == "uncertain")
    openai_definitive_binary = len(gold_binary_ids) - openai_abstain_binary

    claude_abstain_all = sum(1 for pid in pair_ids if claude_pred_by_pair[pid] == "uncertain")
    claude_definitive_all = n_all - claude_abstain_all
    claude_abstain_binary = sum(1 for pid in gold_binary_ids if claude_pred_by_pair[pid] == "uncertain")
    claude_definitive_binary = len(gold_binary_ids) - claude_abstain_binary

    coverage_breakdown = {
        "denominator_definitions": {
            "ALL_149": "every test pair, regardless of gold label",
            "GOLD_BINARY_124": "test pairs whose gold label is match or non_match only (excludes the 25 gold-uncertain pairs)",
        },
        "openai": {
            "definitive_predictions_among_all_149": openai_definitive_all,
            "abstentions_among_all_149": openai_abstain_all,
            "coverage_over_all_149": round(openai_definitive_all / n_all, 4),
            "definitive_predictions_among_gold_binary_124": openai_definitive_binary,
            "abstentions_among_gold_binary_124": openai_abstain_binary,
            "coverage_over_gold_binary_124": round(openai_definitive_binary / len(gold_binary_ids), 4),
        },
        "claude_majority": {
            "definitive_predictions_among_all_149": claude_definitive_all,
            "abstentions_among_all_149": claude_abstain_all,
            "coverage_over_all_149": round(claude_definitive_all / n_all, 4),
            "definitive_predictions_among_gold_binary_124": claude_definitive_binary,
            "abstentions_among_gold_binary_124": claude_abstain_binary,
            "coverage_over_gold_binary_124": round(claude_definitive_binary / len(gold_binary_ids), 4),
        },
        "clarification": (
            "The previously reported 'coverage=0.7584' for OpenAI uses denominator ALL_149 "
            "(113/149 definitive = 0.7584). The previously reported 'n_decided=111' is the "
            "count of definitive predictions among the GOLD_BINARY_124 subset only (111/124), "
            "NOT 111/149 as the prior report's prose incorrectly stated -- 111/149 would be "
            "0.7450, which is not the reported coverage figure. This script fixes the label; "
            "the underlying binary_metrics() computation in phase1b_analysis.py was already "
            "numerically correct (precision/recall/F1 were computed over the right subset), "
            "only the report's PROSE mislabelled the denominator of the printed 'n_decided' number."
        ),
    }
    with open(out_dir / "reconciliation_coverage_breakdown.json", "w", encoding="utf-8") as f:
        json.dump(coverage_breakdown, f, indent=2)
    print("SECTION 1 (coverage/n_decided):")
    print(json.dumps(coverage_breakdown, indent=2))

    # =====================================================================
    # SECTION 2A: primary binary evaluation (gold restricted to match/non_match)
    # =====================================================================
    def binary_outcome(pred, gold):
        if pred == "uncertain":
            return "ABSTAINED"
        return "CORRECT" if pred == gold else "WRONG_DECIDED"

    binary_outcomes = {}
    for pid in gold_binary_ids:
        g = gold_by_pair[pid]
        binary_outcomes[pid] = {
            "gold": g,
            "claude_pred": claude_pred_by_pair[pid],
            "openai_pred": openai_pred_by_pair[pid],
            "claude_outcome": binary_outcome(claude_pred_by_pair[pid], g),
            "openai_outcome": binary_outcome(openai_pred_by_pair[pid], g),
        }

    def is_correct(outcome):
        return outcome == "CORRECT"

    contingency_2x2 = {"both_correct": 0, "claude_only_correct": 0, "openai_only_correct": 0, "both_not_correct": 0}
    detail_4x4 = defaultdict(int)  # (claude_outcome, openai_outcome) -> count
    for pid, o in binary_outcomes.items():
        c_ok, o_ok = is_correct(o["claude_outcome"]), is_correct(o["openai_outcome"])
        if c_ok and o_ok:
            contingency_2x2["both_correct"] += 1
        elif c_ok and not o_ok:
            contingency_2x2["claude_only_correct"] += 1
        elif not c_ok and o_ok:
            contingency_2x2["openai_only_correct"] += 1
        else:
            contingency_2x2["both_not_correct"] += 1
        detail_4x4[(o["claude_outcome"], o["openai_outcome"])] += 1

    claude_outcome_counts = defaultdict(int)
    openai_outcome_counts = defaultdict(int)
    for o in binary_outcomes.values():
        claude_outcome_counts[o["claude_outcome"]] += 1
        openai_outcome_counts[o["openai_outcome"]] += 1

    binary_report = {
        "gold_set": "restricted to match/non_match, N=124 (excludes 25 gold-uncertain pairs)",
        "abstention_scoring_policy": (
            "An abstention (predicted 'uncertain') on a gold match/non_match pair is scored as "
            "NOT CORRECT -- it is a missed decision, distinct from a WRONG_DECIDED active "
            "misclassification. This matches the existing binary_metrics() convention where an "
            "abstained gold-match pair counts as FN (not a true positive), extended here "
            "symmetrically to gold-non_match pairs for the purpose of this contingency table only "
            "(binary_metrics() itself does not need a symmetric treatment for TN, since precision/"
            "recall are defined over the match class specifically -- this contingency table is a "
            "different, more general correctness view)."
        ),
        "claude_outcome_counts_of_124": dict(claude_outcome_counts),
        "openai_outcome_counts_of_124": dict(openai_outcome_counts),
        "contingency_2x2_by_correctness": contingency_2x2,
        "contingency_4x4_by_exact_outcome": {f"claude={k[0]},openai={k[1]}": v for k, v in sorted(detail_4x4.items())},
    }
    with open(out_dir / "reconciliation_binary_contingency.json", "w", encoding="utf-8") as f:
        json.dump(binary_report, f, indent=2)
    print("\nSECTION 2A (primary binary evaluation, N=124):")
    print(json.dumps(binary_report, indent=2))

    # =====================================================================
    # SECTION 2B: full three-way evaluation (all 149, all 3 labels)
    # =====================================================================
    def build_cm(pred_by_pair):
        cm = {g: {p: 0 for p in LABELS} for g in LABELS}
        for pid in pair_ids:
            cm[gold_by_pair[pid]][pred_by_pair[pid]] += 1
        return cm

    claude_cm = build_cm(claude_pred_by_pair)
    openai_cm = build_cm(openai_pred_by_pair)

    claude_correct = {pid: claude_pred_by_pair[pid] == gold_by_pair[pid] for pid in pair_ids}
    openai_correct = {pid: openai_pred_by_pair[pid] == gold_by_pair[pid] for pid in pair_ids}

    tw_contingency = {"both_correct": 0, "claude_only_correct": 0, "openai_only_correct": 0, "both_incorrect": 0}
    claude_only_wrong_pairs, openai_only_wrong_pairs, both_wrong_pairs = [], [], []
    for pid in pair_ids:
        c, o = claude_correct[pid], openai_correct[pid]
        if c and o:
            tw_contingency["both_correct"] += 1
        elif c and not o:
            tw_contingency["claude_only_correct"] += 1
            openai_only_wrong_pairs.append(pid)
        elif not c and o:
            tw_contingency["openai_only_correct"] += 1
            claude_only_wrong_pairs.append(pid)
        else:
            tw_contingency["both_incorrect"] += 1
            both_wrong_pairs.append(pid)

    claude_pred_list = [claude_pred_by_pair[pid] for pid in pair_ids]
    openai_pred_list = [openai_pred_by_pair[pid] for pid in pair_ids]
    exact_agreement = sum(1 for a, b in zip(claude_pred_list, openai_pred_list) if a == b) / len(pair_ids)
    kappa = cohens_kappa(claude_pred_list, openai_pred_list, LABELS)

    threeway_report = {
        "scope": "ALL 149 pairs, all 3 labels (match/non_match/uncertain), correctness = pred == gold exactly",
        "claude_majority_confusion_matrix_gold_rows_pred_cols": claude_cm,
        "openai_confusion_matrix_gold_rows_pred_cols": openai_cm,
        "correctness_contingency_vs_gold": tw_contingency,
        "pairs_where_claude_correct_openai_wrong": sorted(set(openai_only_wrong_pairs)),
        "pairs_where_openai_correct_claude_wrong": sorted(set(claude_only_wrong_pairs)),
        "both_incorrect_pair_ids": sorted(set(both_wrong_pairs)),
        "claude_vs_openai_exact_agreement": round(exact_agreement, 4),
        "claude_vs_openai_cohens_kappa": round(kappa, 4),
    }

    with open(out_dir / "reconciliation_threeway_contingency.json", "w", encoding="utf-8") as f:
        json.dump(threeway_report, f, indent=2)

    with open(out_dir / "reconciliation_claude_threeway_confusion_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gold\\pred"] + LABELS)
        for g in LABELS:
            w.writerow([g] + [claude_cm[g][p] for p in LABELS])

    print("\nSECTION 2B (full three-way evaluation, all 149 pairs):")
    print(json.dumps(threeway_report, indent=2))

    # =====================================================================
    # SECTION 3: Claim 13 reassessment -- is OpenAI's error set a superset of Claude's?
    # =====================================================================
    print("\nSECTION 3 (Claim 13 -- superset check):")
    print(f"  Primary binary (decided-only, N=124, gold!=uncertain, both p!=uncertain): "
          f"pairs where ONLY Claude wrong = {contingency_2x2['claude_only_correct'] == 0}"
          f" (openai_only_correct={contingency_2x2['openai_only_correct']}, "
          f"claude_only_correct={contingency_2x2['claude_only_correct']})")
    print(f"  Full three-way (all 149, all 3 labels): "
          f"pairs where OpenAI correct AND Claude wrong = {len(set(claude_only_wrong_pairs))} "
          f"-- superset claim is {'TRUE' if len(set(claude_only_wrong_pairs))==0 else 'FALSE'} under this framing")

    print(f"\nAll outputs written to: {out_dir}")


if __name__ == "__main__":
    main()
