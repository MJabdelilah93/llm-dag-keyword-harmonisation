"""
error_sensitivity_analysis.py
================================
PHASE 1A / TASK 3 — exact best-case/worst-case error-sensitivity analysis
for Full LLM-DAG, addressing the Scientometrics editor's "three errors
should not decide the result" comment directly and quantitatively.

Model: the 124 gold-decided test pairs sit in one of four confusion cells
(TP=41, FP=1, FN=2, TN=80). Changing the model's PREDICTED label for one
pair moves it between cells that share the same GOLD label:
  gold=match:     TP <-> FN   (a = TP->FN flips, b = FN->TP flips)
  gold=non_match: FP <-> TN   (c = FP->TN flips, d = TN->FP flips)
For k total changed decisions, every valid (a,b,c,d) with a+b+c+d=k and
0<=a<=TP, 0<=b<=FN, 0<=c<=FP, 0<=d<=TN is enumerated EXACTLY (brute force
over a small integer space -- no sampling, no approximation), and the
resulting precision/recall/F1 computed for every combination. This gives
the true best-case and worst-case bound achievable with exactly k changed
decisions, not an approximation.

"Best case" and "worst case" are reported separately per the task's
explicit instruction not to manufacture a favourable scenario -- both
directions are computed from the same exhaustive search, not chosen ahead
of time.

No historical prediction file is modified. This is a pure combinatorial
calculation over the frozen, already-verified confusion-matrix counts.
"""
import csv
import json
import pathlib

TP, FP, FN, TN = 41, 1, 2, 80
N_DECIDED = TP + FP + FN + TN
assert N_DECIDED == 124

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "results" / "current_paper"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def metrics(tp, fp, fn, tn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn)
    return precision, recall, f1, accuracy


def enumerate_k(k):
    """All (a,b,c,d) with a+b+c+d=k, respecting cell capacities."""
    results = []
    for a in range(min(TP, k) + 1):
        for b in range(min(FN, k - a) + 1):
            for c in range(min(FP, k - a - b) + 1):
                d = k - a - b - c
                if d < 0 or d > TN:
                    continue
                tp2, fp2, fn2, tn2 = TP - a + b, FP - c + d, FN + a - b, TN + c - d
                p, r, f1, acc = metrics(tp2, fp2, fn2, tn2)
                results.append({"a_TPtoFN": a, "b_FNtoTP": b, "c_FPtoTN": c, "d_TNtoFP": d,
                                 "TP": tp2, "FP": fp2, "FN": fn2, "TN": tn2,
                                 "precision": p, "recall": r, "f1": f1, "accuracy": acc})
    return results


baseline_p, baseline_r, baseline_f1, baseline_acc = metrics(TP, FP, FN, TN)

report = {"baseline": {"TP": TP, "FP": FP, "FN": FN, "TN": TN, "n_decided": N_DECIDED,
                        "precision": round(baseline_p, 4), "recall": round(baseline_r, 4),
                        "f1": round(baseline_f1, 4), "accuracy": round(baseline_acc, 4)},
          "scenarios": {}}

csv_rows = []
for k in (1, 2, 3):
    combos = enumerate_k(k)
    best_f1 = max(combos, key=lambda c: c["f1"])
    worst_f1 = min(combos, key=lambda c: c["f1"])
    best_p = max(combos, key=lambda c: c["precision"])
    worst_p = min(combos, key=lambda c: c["precision"])
    best_r = max(combos, key=lambda c: c["recall"])
    worst_r = min(combos, key=lambda c: c["recall"])
    best_acc = max(combos, key=lambda c: c["accuracy"])
    worst_acc = min(combos, key=lambda c: c["accuracy"])

    report["scenarios"][f"k={k}"] = {
        "n_valid_combinations_enumerated": len(combos),
        "f1": {"best_case": round(best_f1["f1"], 4), "worst_case": round(worst_f1["f1"], 4),
               "baseline": round(baseline_f1, 4),
               "best_case_delta": round(best_f1["f1"] - baseline_f1, 4),
               "worst_case_delta": round(worst_f1["f1"] - baseline_f1, 4)},
        "precision": {"best_case": round(best_p["precision"], 4), "worst_case": round(worst_p["precision"], 4)},
        "recall": {"best_case": round(best_r["recall"], 4), "worst_case": round(worst_r["recall"], 4)},
        "accuracy": {"best_case": round(best_acc["accuracy"], 4), "worst_case": round(worst_acc["accuracy"], 4)},
        "best_f1_scenario_flips": {k2: v for k2, v in best_f1.items() if k2.startswith(("a_", "b_", "c_", "d_"))},
        "worst_f1_scenario_flips": {k2: v for k2, v in worst_f1.items() if k2.startswith(("a_", "b_", "c_", "d_"))},
    }
    for c in combos:
        csv_rows.append({"k": k, **c})

out_json = OUT_DIR / "error_sensitivity_analysis.json"
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

out_csv = OUT_DIR / "error_sensitivity_all_combinations.csv"
with open(out_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
    w.writeheader()
    for r in csv_rows:
        w.writerow(r)

print(json.dumps(report, indent=2))
print(f"\nWrote: {out_json}")
print(f"Wrote: {out_csv}")
