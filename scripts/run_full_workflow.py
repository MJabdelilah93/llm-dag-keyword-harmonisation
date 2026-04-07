"""
run_full_workflow.py
====================
Implements the full LLM-DAG workflow (Nodes 2+4+5) for M7 benchmark.

Steps per pair:
  1. Normalise (Node 2)
  2. Call LLM with structured prompt + JSON schema (Node 4)
  3. Guard layer — G1-G5 checks (Node 5)

Threshold tuning: confidence threshold searched on dev set [0.50, 0.95]
step 0.05, maximising F1 subject to coverage >= 0.70.

Outputs:
  results/tuned_thresholds.json       (updated with guard_confidence_threshold)
  results/dev_results_full_workflow.csv
  results/llm_logs/dev_workflow_raw_outputs.jsonl
  results/test_results.csv            (all methods combined)
  results/test_predictions.csv
  results/test_results_summary.txt    (Table 6)
  results/llm_logs/test_raw_outputs.jsonl
"""

import io
import json
import logging
import pathlib
import re
import sys
import time
import unicodedata
import hashlib
from datetime import datetime, timezone

# ── UTF-8 stdout ──────────────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
RESULTS = ROOT / "results"
LLM_LOGS = RESULTS / "llm_logs"
BENCH = ROOT / "data" / "benchmark"
CONFIGS = ROOT / "configs"

RESULTS.mkdir(parents=True, exist_ok=True)
LLM_LOGS.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Seed ──────────────────────────────────────────────────────────────────────
import random
import numpy as np
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── Imports ───────────────────────────────────────────────────────────────────
import pandas as pd
import yaml
import anthropic
import os

# ── Config ────────────────────────────────────────────────────────────────────
with open(CONFIGS / "model_config.yaml", encoding="utf-8") as f:
    model_cfg = yaml.safe_load(f)

MODEL_ID = model_cfg["model"]["model_id"]
TEMPERATURE = model_cfg["model"]["temperature"]
MAX_TOKENS = model_cfg["model"]["max_tokens"]
log.info(f"Model: {MODEL_ID}")

# Cost estimates (haiku pricing)
COST_PER_1K_IN = 0.00025
COST_PER_1K_OUT = 0.00125

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
client = anthropic.Anthropic(api_key=API_KEY)

# ===========================================================================
# SECTION 1 — Normalisation (Node 2)
# ===========================================================================

def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


# ===========================================================================
# SECTION 2 — Prompts
# ===========================================================================

SYSTEM_PROMPT = """You are a bibliometric concept harmonisation assistant. Your task is to decide whether two keyword strings represent the same bibliometric concept.

You must return a JSON object with exactly three fields:
- "decision": one of "match", "non_match", or "uncertain"
- "confidence": a number between 0.0 and 1.0
- "justification": a brief explanation stating the primary reason for the decision, using one of these categories where applicable: spelling variant, punctuation/formatting variant, singular-plural, acronym-expansion match, same-concept near-synonym, broader-narrower relation, related but distinct concepts, polysemous acronym, unresolved ambiguity, or malformed string (1-2 sentences)

Apply these scope rules:
- match: spelling variants, punctuation/hyphenation variants, singular/plural, unambiguous acronym-expansion pairs, clear same-concept near-synonyms
- non_match: broader-narrower relations, related but distinct concepts, semantically proximate terms that are not conceptually identical
- uncertain: polysemous acronyms, context-dependent overlap, malformed strings, cases where available evidence does not support a confident decision

Conservative policy: when in doubt, output "uncertain". Do NOT merge concepts that are merely related. The question is: should these two strings be treated as the SAME concept node in a bibliometric thematic map?

Do not infer equivalence from topical similarity, co-occurrence frequency, or membership in the same research area. The question is strictly whether the two strings should be treated as the same concept node in a bibliometric thematic map.

Return only valid JSON. Do not include any text outside the JSON object."""


def make_user_prompt(keyword_a: str, keyword_b: str) -> str:
    return (
        f"Keyword A: {keyword_a}\n"
        f"Keyword B: {keyword_b}\n\n"
        f"Decide: match, non_match, or uncertain. Return JSON only."
    )


# ===========================================================================
# SECTION 3 — LLM call with retry
# ===========================================================================

def _prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def call_llm_structured(keyword_a: str, keyword_b: str,
                         max_retries: int = 3) -> dict:
    """
    Call LLM with structured system + user prompt.
    Returns raw dict with response + metadata.
    """
    user_prompt = make_user_prompt(keyword_a, keyword_b)
    combined = SYSTEM_PROMPT + "\n" + user_prompt
    ph = _prompt_hash(combined)
    ts = datetime.now(timezone.utc).isoformat()
    delays = [1, 2, 4]
    last_exc = None
    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model=MODEL_ID,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            resp_text = msg.content[0].text if msg.content else ""
            in_tok = msg.usage.input_tokens
            out_tok = msg.usage.output_tokens
            cost = (in_tok / 1000 * COST_PER_1K_IN +
                    out_tok / 1000 * COST_PER_1K_OUT)
            return {
                "prompt_hash": ph,
                "full_response": resp_text,
                "timestamp": ts,
                "model_id": MODEL_ID,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "estimated_cost_usd": round(cost, 6),
                "stop_reason": msg.stop_reason,
                "attempt": attempt + 1,
                "error": None,
            }
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(delays[attempt])
    return {
        "prompt_hash": ph,
        "full_response": "",
        "timestamp": ts,
        "model_id": MODEL_ID,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "stop_reason": "error",
        "attempt": max_retries,
        "error": str(last_exc),
    }


# ===========================================================================
# SECTION 4 — Guard layer (G1–G5)
# ===========================================================================

VALID_DECISIONS = {"match", "non_match", "uncertain"}


def _strip_markdown_fence(text: str) -> str:
    """Strip ```json ... ``` or ``` ... ``` markdown fences from LLM response."""
    text = text.strip()
    # Remove opening fence with optional language tag
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    # Remove closing fence
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def apply_guard(raw_response: str, confidence_threshold: float) -> dict:
    """
    Apply guard layer to raw LLM response.

    G1: JSON parse failure -> uncertain
    G2: Missing fields -> uncertain
    G3: Invalid decision value -> uncertain
    G4: confidence < threshold -> override to uncertain
    G5: (contradiction check done at batch level)

    Returns: {decision, confidence, justification, guard_applied, guard_reason}
    """
    result = {
        "decision": "uncertain",
        "confidence": 0.0,
        "justification": "",
        "guard_applied": None,
        "guard_reason": None,
    }

    # G1: JSON parse (strip markdown fences first)
    clean_response = _strip_markdown_fence(raw_response)
    try:
        parsed = json.loads(clean_response)
    except (json.JSONDecodeError, ValueError):
        result["guard_applied"] = "G1"
        result["guard_reason"] = "malformed_parse_failure"
        return result

    # G2: Missing fields
    required = {"decision", "confidence", "justification"}
    if not required.issubset(parsed.keys()):
        missing = required - parsed.keys()
        result["guard_applied"] = "G2"
        result["guard_reason"] = f"malformed_missing_field:{','.join(missing)}"
        return result

    # G3: Invalid decision value
    decision = str(parsed.get("decision", "")).strip().lower()
    if decision not in VALID_DECISIONS:
        result["guard_applied"] = "G3"
        result["guard_reason"] = f"invalid_decision:{decision}"
        return result

    result["decision"] = decision
    result["justification"] = str(parsed.get("justification", ""))

    # Parse confidence
    try:
        conf = float(parsed.get("confidence", 0.0))
        conf = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        conf = 0.0
    result["confidence"] = conf

    # G4: Confidence threshold (only for match/non_match, not uncertain)
    if decision != "uncertain" and conf < confidence_threshold:
        result["decision"] = "uncertain"
        result["guard_applied"] = "G4"
        result["guard_reason"] = f"confidence_{conf:.3f}_below_threshold_{confidence_threshold:.3f}"
        return result

    return result


# ===========================================================================
# SECTION 5 — Run full workflow on a dataframe
# ===========================================================================

def run_workflow(df: pd.DataFrame, confidence_threshold: float,
                 log_path: pathlib.Path, split: str = "dev") -> tuple:
    """
    Run full LLM-DAG workflow on df.
    Returns (preds_with_guard, preds_without_guard) as lists of strings.
    """
    preds_with_guard = []
    preds_without_guard = []
    total_cost = 0.0

    log.info(f"Running Full Workflow on {split} set ({len(df)} pairs, "
             f"confidence_threshold={confidence_threshold}) ...")

    with open(log_path, "w", encoding="utf-8") as fout:
        for idx, (_, row) in enumerate(df.iterrows()):
            kw_a = row["keyword_a"]
            kw_b = row["keyword_b"]
            kw_a_norm = normalise(kw_a)
            kw_b_norm = normalise(kw_b)

            # Node 4: LLM call
            llm_result = call_llm_structured(kw_a, kw_b)

            # Raw prediction (no guard) — strip markdown fences
            try:
                clean_resp = _strip_markdown_fence(llm_result["full_response"])
                raw_parsed = json.loads(clean_resp)
                raw_decision = str(raw_parsed.get("decision", "uncertain")).strip().lower()
                if raw_decision not in VALID_DECISIONS:
                    raw_decision = "uncertain"
            except Exception:
                raw_decision = "uncertain"
            preds_without_guard.append(raw_decision)

            # Node 5: Guard layer
            guard_result = apply_guard(llm_result["full_response"], confidence_threshold)
            preds_with_guard.append(guard_result["decision"])

            total_cost += llm_result["estimated_cost_usd"]

            # Log entry
            entry = {
                "pair_id": row.get("pair_id", str(idx)),
                "keyword_a": kw_a,
                "keyword_b": kw_b,
                "keyword_a_norm": kw_a_norm,
                "keyword_b_norm": kw_b_norm,
                "gold_label": row.get("gold_label", ""),
                **llm_result,
                "raw_decision": raw_decision,
                "guard_decision": guard_result["decision"],
                "guard_confidence": guard_result["confidence"],
                "guard_justification": guard_result["justification"],
                "guard_applied": guard_result["guard_applied"],
                "guard_reason": guard_result["guard_reason"],
                "confidence_threshold": confidence_threshold,
            }
            fout.write(json.dumps(entry, ensure_ascii=False) + "\n")

            if (idx + 1) % 25 == 0:
                log.info(f"  {split}: {idx+1}/{len(df)} done | "
                         f"cost so far: ${total_cost:.4f}")

    log.info(f"  {split} complete. Total cost: ${total_cost:.4f}")
    log.info(f"  Log -> {log_path}")
    return preds_with_guard, preds_without_guard, total_cost


# ===========================================================================
# SECTION 6 — Metric function (same as baselines)
# ===========================================================================

def binary_metrics(gold: list, pred: list) -> dict:
    assert len(gold) == len(pred)
    n = len(gold)
    three_way_correct = sum(1 for g, p in zip(gold, pred) if g == p)
    three_way_acc = three_way_correct / n if n > 0 else 0.0
    n_uncertain_pred = sum(1 for p in pred if p == "uncertain")
    coverage = (n - n_uncertain_pred) / n if n > 0 else 0.0
    uncertain_rate = n_uncertain_pred / n if n > 0 else 0.0
    binary_pairs = [(g, p) for g, p in zip(gold, pred) if g != "uncertain"]
    decided_pairs = [(g, p) for g, p in binary_pairs if p != "uncertain"]
    if len(decided_pairs) == 0:
        precision = 0.0
        recall = 0.0
    else:
        tp = sum(1 for g, p in decided_pairs if g == "match" and p == "match")
        fp = sum(1 for g, p in decided_pairs if g != "match" and p == "match")
        fn_decided = sum(1 for g, p in decided_pairs if g == "match" and p != "match")
        fn_abstain = sum(1 for g, p in binary_pairs if g == "match" and p == "uncertain")
        fn = fn_decided + fn_abstain
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "coverage": round(coverage, 4),
        "uncertain_rate": round(uncertain_rate, 4),
        "three_way_acc": round(three_way_acc, 4),
    }


# ===========================================================================
# SECTION 7 — Load data
# ===========================================================================

log.info("Loading benchmark data ...")
df_dev = pd.read_csv(BENCH / "dev_set.csv", encoding="utf-8-sig")
df_test = pd.read_csv(BENCH / "test_set.csv", encoding="utf-8-sig")

def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    if lbl in ("non-match", "non_match"):
        return "non_match"
    return lbl

df_dev["gold_label"] = df_dev["gold_label"].apply(norm_label)
df_test["gold_label"] = df_test["gold_label"].apply(norm_label)

log.info(f"Dev: {len(df_dev)} | Test: {len(df_test)}")


# ===========================================================================
# SECTION 8 — Tune confidence threshold on dev set
# ===========================================================================

log.info("=" * 60)
log.info("Tuning confidence threshold on dev set ...")
log.info("=" * 60)

# First run dev with threshold=0.0 to get all raw outputs, then sweep thresholds
dev_log_path = LLM_LOGS / "dev_workflow_raw_outputs.jsonl"

# Check if we already have all dev outputs (reuse if complete)
_existing_dev_lines = 0
if dev_log_path.exists():
    with open(dev_log_path, encoding="utf-8") as _f:
        _existing_dev_lines = sum(1 for _ in _f)

if _existing_dev_lines >= len(df_dev):
    log.info(f"Reusing existing dev log ({_existing_dev_lines} entries) ...")
    preds_guard_00 = []
    preds_no_guard = []
    dev_cost = 0.0
    with open(dev_log_path, encoding="utf-8") as _f:
        for _line in _f:
            try:
                _e = json.loads(_line.strip())
            except Exception:
                continue  # skip malformed lines
            preds_guard_00.append(_e.get("guard_decision", "uncertain"))
            preds_no_guard.append(_e.get("raw_decision", "uncertain"))
            dev_cost += _e.get("estimated_cost_usd", 0.0)
else:
    # Run once at threshold 0.0 to collect all raw LLM outputs
    preds_guard_00, preds_no_guard, dev_cost = run_workflow(
        df_dev, confidence_threshold=0.0,
        log_path=dev_log_path, split="dev"
    )

# Load the logged outputs to replay threshold sweep
log.info("Replaying threshold sweep from logged outputs ...")
dev_log_entries = []
with open(dev_log_path, encoding="utf-8") as f:
    for line in f:
        try:
            dev_log_entries.append(json.loads(line.strip()))
        except Exception:
            continue  # skip malformed lines

# Build aligned gold/log lists (handle missing entries via pair_id matching)
log_by_pair = {e["pair_id"]: e for e in dev_log_entries}
aligned_gold = []
aligned_entries = []
for _, row in df_dev.iterrows():
    pid = row["pair_id"]
    aligned_gold.append(row["gold_label"])
    if pid in log_by_pair:
        aligned_entries.append(log_by_pair[pid])
    else:
        # Fallback for missing entry: treat as uncertain
        aligned_entries.append({"full_response": "", "raw_decision": "uncertain",
                                 "guard_decision": "uncertain"})

gold_dev = aligned_gold

best_thresh = 0.50
best_f1 = -1.0
best_cov = 0.0

for thresh in np.arange(0.50, 0.96, 0.05):
    thresh = round(float(thresh), 2)
    # Re-apply guard with this threshold
    preds_sweep = []
    for entry in aligned_entries:
        g = apply_guard(entry["full_response"], thresh)
        preds_sweep.append(g["decision"])
    m = binary_metrics(gold_dev, preds_sweep)
    log.info(f"  thresh={thresh:.2f}: F1={m['f1']:.4f} Cov={m['coverage']:.4f}")
    # Maximise F1 subject to coverage >= 0.70
    if m["coverage"] >= 0.70 and m["f1"] > best_f1:
        best_f1 = m["f1"]
        best_thresh = thresh
        best_cov = m["coverage"]

log.info(f"Best confidence threshold: {best_thresh:.2f} "
         f"(dev F1={best_f1:.4f}, coverage={best_cov:.4f})")

# Save to tuned_thresholds.json
thresh_path = RESULTS / "tuned_thresholds.json"
existing = {}
if thresh_path.exists():
    with open(thresh_path, encoding="utf-8") as f:
        existing = json.load(f)
existing["guard_confidence_threshold"] = {
    "threshold": best_thresh,
    "dev_f1": best_f1,
    "dev_coverage": best_cov,
}
with open(thresh_path, "w", encoding="utf-8") as f:
    json.dump(existing, f, indent=2)
log.info(f"Saved tuned thresholds -> {thresh_path}")


# ===========================================================================
# SECTION 9 — Dev set evaluation
# ===========================================================================

log.info("=" * 60)
log.info("Dev set evaluation (with and without guard) ...")
log.info("=" * 60)

# With guard (best threshold) — use aligned_entries
preds_with_guard_best = []
for entry in aligned_entries:
    g = apply_guard(entry["full_response"], best_thresh)
    preds_with_guard_best.append(g["decision"])

# Without guard
preds_without_guard_dev = [e.get("raw_decision", "uncertain") for e in aligned_entries]

m_with = binary_metrics(gold_dev, preds_with_guard_best)
m_without = binary_metrics(gold_dev, preds_without_guard_dev)

log.info(f"  With guard (thresh={best_thresh}): "
         f"P={m_with['precision']:.3f} R={m_with['recall']:.3f} "
         f"F1={m_with['f1']:.3f} Cov={m_with['coverage']:.3f}")
log.info(f"  Without guard: "
         f"P={m_without['precision']:.3f} R={m_without['recall']:.3f} "
         f"F1={m_without['f1']:.3f} Cov={m_without['coverage']:.3f}")

dev_workflow_rows = [
    {"method": "Full_LLM_DAG_with_guard", "split": "dev", **m_with},
    {"method": "Full_LLM_DAG_no_guard",   "split": "dev", **m_without},
]
pd.DataFrame(dev_workflow_rows).to_csv(
    RESULTS / "dev_results_full_workflow.csv", index=False, encoding="utf-8-sig"
)
log.info(f"Saved dev workflow results -> {RESULTS / 'dev_results_full_workflow.csv'}")


# ===========================================================================
# SECTION 10 — Test set evaluation
# ===========================================================================

log.info("=" * 60)
log.info("Test set evaluation ...")
log.info("=" * 60)

test_log_path = LLM_LOGS / "test_raw_outputs.jsonl"
preds_test_guard, preds_test_no_guard, test_cost = run_workflow(
    df_test, confidence_threshold=best_thresh,
    log_path=test_log_path, split="test"
)

gold_test = df_test["gold_label"].tolist()
m_test = binary_metrics(gold_test, preds_test_guard)
log.info(f"  Full LLM-DAG (test): "
         f"P={m_test['precision']:.3f} R={m_test['recall']:.3f} "
         f"F1={m_test['f1']:.3f} Cov={m_test['coverage']:.3f}")


# ===========================================================================
# SECTION 11 — Combine all test results (load baselines + add workflow)
# ===========================================================================

log.info("Combining all test results ...")

# Load baseline test results
baseline_results_path = RESULTS / "test_results_baselines.csv"
if baseline_results_path.exists():
    df_baseline_test = pd.read_csv(baseline_results_path, encoding="utf-8-sig")
    baseline_rows = df_baseline_test.to_dict("records")
else:
    log.warning("Baseline test results not found — run run_baselines.py first")
    baseline_rows = []

# Add full workflow
workflow_row = {
    "method": "Full_LLM_DAG",
    "split": "test",
    **m_test,
}
all_test_rows = baseline_rows + [workflow_row]
df_all_test = pd.DataFrame(all_test_rows)
df_all_test.to_csv(RESULTS / "test_results.csv", index=False, encoding="utf-8-sig")
log.info(f"Saved combined test results -> {RESULTS / 'test_results.csv'}")

# Test predictions
df_test_preds = df_test[["pair_id", "keyword_a", "keyword_b", "gold_label"]].copy()
df_test_preds["Full_LLM_DAG"] = preds_test_guard

# Merge baseline predictions if available
baseline_preds_path = RESULTS / "test_predictions_baselines.csv"
if baseline_preds_path.exists():
    df_bp = pd.read_csv(baseline_preds_path, encoding="utf-8-sig")
    for col in [c for c in df_bp.columns if c.startswith("B")]:
        df_test_preds[col] = df_bp[col].values
df_test_preds.to_csv(RESULTS / "test_predictions.csv", index=False, encoding="utf-8-sig")
log.info(f"Saved test predictions -> {RESULTS / 'test_predictions.csv'}")


# ===========================================================================
# SECTION 12 — Print Table 6
# ===========================================================================

METHOD_LABELS = {
    "B1_Exact":         "B1 Exact",
    "B2_Normalised":    "B2 Normalised",
    "B3_JaroWinkler":   "B3 Jaro-Winkler",
    "B4_TFIDF":         "B4 TF-IDF n-gram",
    "B5_Embedding":     "B5 Embedding",
    "B6_NaiveLLM":      "B6 Naive LLM",
    "Full_LLM_DAG":     "Full LLM-DAG",
}

header = (
    f"\n{'Method':<20} {'Prec.':>7} {'Rec.':>7} {'F1':>7} "
    f"{'Cov.':>7} {'Unc.':>7} {'3-way Acc.':>11}"
)
sep = "-" * 70
table_lines = ["Table 6: Test Set Results", "=" * 70, header, sep]

for _, row in df_all_test.iterrows():
    label = METHOD_LABELS.get(row["method"], row["method"])
    line = (
        f"{label:<20} {row['precision']:>7.3f} {row['recall']:>7.3f} "
        f"{row['f1']:>7.3f} {row['coverage']:>7.3f} "
        f"{row['uncertain_rate']:>7.3f} {row['three_way_acc']:>11.3f}"
    )
    table_lines.append(line)

table_lines.append(sep)
table_text = "\n".join(table_lines)
print(table_text)

summary_path = RESULTS / "test_results_summary.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write(table_text + "\n")
    f.write(f"\nDev LLM cost:  ${dev_cost:.4f}\n")
    f.write(f"Test LLM cost: ${test_cost:.4f}\n")
    f.write(f"Confidence threshold (tuned on dev): {best_thresh}\n")
    f.write(f"Model: {MODEL_ID}\n")
    f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
log.info(f"Saved Table 6 -> {summary_path}")

log.info("=" * 60)
log.info("run_full_workflow.py COMPLETE")
log.info(f"Total LLM cost (dev+test): ${dev_cost + test_cost:.4f}")
log.info("=" * 60)
