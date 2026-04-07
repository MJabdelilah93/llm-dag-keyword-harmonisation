"""
run_error_analysis.py
=====================
Error analysis using test-set predictions from full LLM-DAG.

Error categories:
  FP: predicted match, gold = non_match
  FN: predicted non_match, gold = match
  Correct abstention: predicted uncertain, gold = uncertain
  Incorrect abstention: predicted uncertain, gold = match/non_match
  Missed abstention: predicted match/non_match, gold = uncertain

Outputs:
  results/error_analysis.csv
  results/error_analysis_summary.txt
"""

import io
import json
import logging
import pathlib
import sys

# ── UTF-8 stdout ──────────────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
RESULTS = ROOT / "results"
LLM_LOGS = RESULTS / "llm_logs"
BENCH = ROOT / "data" / "benchmark"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

import pandas as pd
import numpy as np
from collections import defaultdict


# ===========================================================================
# Load test predictions
# ===========================================================================

log.info("Loading test predictions ...")
df_preds = pd.read_csv(RESULTS / "test_predictions.csv", encoding="utf-8-sig")

# Normalise labels
def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    if lbl in ("non-match", "non_match"):
        return "non_match"
    return lbl

df_preds["gold_label"] = df_preds["gold_label"].apply(norm_label)
if "Full_LLM_DAG" in df_preds.columns:
    df_preds["Full_LLM_DAG"] = df_preds["Full_LLM_DAG"].apply(norm_label)

# Load justifications from test log
justifications = {}
test_log_path = LLM_LOGS / "test_raw_outputs.jsonl"
if test_log_path.exists():
    with open(test_log_path, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            justifications[entry.get("pair_id", "")] = {
                "justification": entry.get("guard_justification", ""),
                "confidence": entry.get("guard_confidence", 0.0),
                "guard_applied": entry.get("guard_applied", None),
            }

# Load test set for stratum info
df_test = pd.read_csv(BENCH / "test_set.csv", encoding="utf-8-sig")
df_test["gold_label"] = df_test["gold_label"].apply(norm_label)
stratum_map = dict(zip(df_test["pair_id"], df_test["stratum"]))


# ===========================================================================
# Classify errors
# ===========================================================================

def classify_error(gold: str, pred: str) -> str:
    if gold == "match" and pred == "match":
        return "TP"
    if gold == "non_match" and pred == "non_match":
        return "TN"
    if gold == "non_match" and pred == "match":
        return "FP"
    if gold == "match" and pred == "non_match":
        return "FN"
    if gold == "uncertain" and pred == "uncertain":
        return "Correct_Abstention"
    if gold == "uncertain" and pred != "uncertain":
        return "Missed_Abstention"
    if gold != "uncertain" and pred == "uncertain":
        return "Incorrect_Abstention"
    return "Other"


log.info("Classifying errors ...")
error_rows = []

for _, row in df_preds.iterrows():
    pair_id = row.get("pair_id", "")
    gold = row["gold_label"]
    pred_dag = str(row.get("Full_LLM_DAG", "uncertain")).strip().lower()
    pred_b6 = str(row.get("B6_NaiveLLM", "uncertain")).strip().lower()

    if pred_dag in ("non-match",):
        pred_dag = "non_match"
    if pred_b6 in ("non-match",):
        pred_b6 = "non_match"

    error_cat = classify_error(gold, pred_dag)
    b6_cat = classify_error(gold, pred_b6)
    just_info = justifications.get(pair_id, {})

    error_rows.append({
        "pair_id": pair_id,
        "keyword_a": row["keyword_a"],
        "keyword_b": row["keyword_b"],
        "stratum": stratum_map.get(pair_id, ""),
        "gold_label": gold,
        "pred_full_dag": pred_dag,
        "pred_b6": pred_b6,
        "error_category": error_cat,
        "b6_error_category": b6_cat,
        "justification": just_info.get("justification", ""),
        "confidence": just_info.get("confidence", 0.0),
        "guard_applied": just_info.get("guard_applied", None),
    })

df_errors = pd.DataFrame(error_rows)
df_errors.to_csv(RESULTS / "error_analysis.csv", index=False, encoding="utf-8-sig")
log.info(f"Saved error analysis -> {RESULTS / 'error_analysis.csv'}")


# ===========================================================================
# Summary statistics
# ===========================================================================

cat_counts = df_errors["error_category"].value_counts()
b6_cat_counts = df_errors["b6_error_category"].value_counts()

lines = ["Error Analysis — Full LLM-DAG vs B6 Naive LLM", "=" * 70]
lines.append("\nFull LLM-DAG Error Categories:")
for cat in ["TP", "TN", "FP", "FN", "Correct_Abstention",
            "Incorrect_Abstention", "Missed_Abstention", "Other"]:
    n = cat_counts.get(cat, 0)
    lines.append(f"  {cat:<25}: {n:>5}")

lines.append(f"\nB6 Naive LLM Error Categories:")
for cat in ["TP", "TN", "FP", "FN", "Correct_Abstention",
            "Incorrect_Abstention", "Missed_Abstention", "Other"]:
    n = b6_cat_counts.get(cat, 0)
    lines.append(f"  {cat:<25}: {n:>5}")


# Breakdown by stratum
lines.append("\n--- Breakdown by Stratum (Full LLM-DAG) ---")
for stratum in sorted(df_errors["stratum"].unique()):
    sub = df_errors[df_errors["stratum"] == stratum]
    cats = sub["error_category"].value_counts()
    fp = cats.get("FP", 0)
    fn = cats.get("FN", 0)
    ia = cats.get("Incorrect_Abstention", 0)
    ma = cats.get("Missed_Abstention", 0)
    lines.append(f"  {stratum}: n={len(sub)} | FP={fp} FN={fn} "
                 f"IncorrAbst={ia} MissedAbst={ma}")


# 3 examples per error category
lines.append("\n--- Example Pairs by Error Category (Full LLM-DAG) ---")
for cat in ["FP", "FN", "Incorrect_Abstention", "Missed_Abstention",
            "Correct_Abstention"]:
    sub = df_errors[df_errors["error_category"] == cat].head(3)
    if len(sub) == 0:
        continue
    lines.append(f"\n{cat} ({len(df_errors[df_errors['error_category'] == cat])} total):")
    for _, r in sub.iterrows():
        just = r["justification"][:100] if r["justification"] else "(no justification)"
        lines.append(
            f"  [{r['pair_id']}] stratum={r['stratum']} "
            f"gold={r['gold_label']} pred={r['pred_full_dag']}"
        )
        lines.append(f"    A: {r['keyword_a']!r}")
        lines.append(f"    B: {r['keyword_b']!r}")
        lines.append(f"    Justification: {just}")


summary = "\n".join(lines)
print("\n" + summary)

with open(RESULTS / "error_analysis_summary.txt", "w", encoding="utf-8") as f:
    f.write(summary + "\n")
log.info(f"Saved error analysis summary -> {RESULTS / 'error_analysis_summary.txt'}")

log.info("=" * 60)
log.info("run_error_analysis.py COMPLETE")
log.info("=" * 60)
