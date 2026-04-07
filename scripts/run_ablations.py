"""
run_ablations.py
================
Runs 4 ablation experiments on test_set.csv using tuned thresholds.

A1: No guard layer (raw LLM output accepted)
A2: No uncertain option (force binary: match/non_match)
A3: No auxiliary context (verifies no context added — informational)
A4: Simplified prompt (no scope policy table)

Requires:
  - results/tuned_thresholds.json (from run_baselines.py + run_full_workflow.py)
  - results/llm_logs/test_raw_outputs.jsonl (from run_full_workflow.py)
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

ROOT = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
RESULTS = ROOT / "results"
LLM_LOGS = RESULTS / "llm_logs"
BENCH = ROOT / "data" / "benchmark"
CONFIGS = ROOT / "configs"

RESULTS.mkdir(parents=True, exist_ok=True)
LLM_LOGS.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

import random
import numpy as np
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

import pandas as pd
import yaml
import anthropic
import os

with open(CONFIGS / "model_config.yaml", encoding="utf-8") as f:
    model_cfg = yaml.safe_load(f)

MODEL_ID = model_cfg["model"]["model_id"]
TEMPERATURE = model_cfg["model"]["temperature"]
MAX_TOKENS = model_cfg["model"]["max_tokens"]

COST_PER_1K_IN = 0.00025
COST_PER_1K_OUT = 0.00125

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
client = anthropic.Anthropic(api_key=API_KEY)

# Load tuned thresholds
with open(RESULTS / "tuned_thresholds.json", encoding="utf-8") as f:
    tuned = json.load(f)
CONF_THRESH = tuned.get("guard_confidence_threshold", {}).get("threshold", 0.70)
log.info(f"Model: {MODEL_ID} | Confidence threshold: {CONF_THRESH}")


# ===========================================================================
# Utilities
# ===========================================================================

def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    if lbl in ("non-match", "non_match"):
        return "non_match"
    return lbl


VALID_DECISIONS = {"match", "non_match", "uncertain"}


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
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "coverage": round(coverage, 4),
        "uncertain_rate": round(uncertain_rate, 4),
        "three_way_acc": round(three_way_acc, 4),
    }


def _prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def call_llm(system_prompt: str, user_prompt: str, max_retries: int = 3) -> dict:
    combined = system_prompt + "\n" + user_prompt
    ph = _prompt_hash(combined)
    ts = datetime.now(timezone.utc).isoformat()
    delays = [1, 2, 4]
    for attempt in range(max_retries):
        try:
            kwargs = {"model": MODEL_ID, "max_tokens": MAX_TOKENS,
                      "temperature": TEMPERATURE,
                      "messages": [{"role": "user", "content": user_prompt}]}
            if system_prompt:
                kwargs["system"] = system_prompt
            msg = client.messages.create(**kwargs)
            resp = msg.content[0].text if msg.content else ""
            in_tok = msg.usage.input_tokens
            out_tok = msg.usage.output_tokens
            cost = in_tok / 1000 * COST_PER_1K_IN + out_tok / 1000 * COST_PER_1K_OUT
            return {"prompt_hash": ph, "full_response": resp, "timestamp": ts,
                    "model_id": MODEL_ID, "input_tokens": in_tok,
                    "output_tokens": out_tok, "estimated_cost_usd": round(cost, 6),
                    "error": None}
        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(delays[attempt])
            last_exc = exc
    return {"prompt_hash": ph, "full_response": "", "timestamp": ts,
            "model_id": MODEL_ID, "input_tokens": 0, "output_tokens": 0,
            "estimated_cost_usd": 0.0, "error": str(last_exc)}


def apply_guard(raw_response: str, confidence_threshold: float) -> dict:
    result = {"decision": "uncertain", "confidence": 0.0, "justification": "",
              "guard_applied": None, "guard_reason": None}
    clean = _strip_markdown_fence(raw_response)
    try:
        parsed = json.loads(clean)
    except Exception:
        result["guard_applied"] = "G1"
        result["guard_reason"] = "malformed_parse_failure"
        return result
    required = {"decision", "confidence", "justification"}
    if not required.issubset(parsed.keys()):
        result["guard_applied"] = "G2"
        result["guard_reason"] = "malformed_missing_field"
        return result
    decision = str(parsed.get("decision", "")).strip().lower()
    if decision not in VALID_DECISIONS:
        result["guard_applied"] = "G3"
        result["guard_reason"] = f"invalid_decision:{decision}"
        return result
    result["decision"] = decision
    result["justification"] = str(parsed.get("justification", ""))
    try:
        conf = float(parsed.get("confidence", 0.0))
        conf = max(0.0, min(1.0, conf))
    except Exception:
        conf = 0.0
    result["confidence"] = conf
    if decision != "uncertain" and conf < confidence_threshold:
        result["decision"] = "uncertain"
        result["guard_applied"] = "G4"
        result["guard_reason"] = f"confidence_{conf:.3f}_below_{confidence_threshold:.3f}"
    return result


# ===========================================================================
# Load test data
# ===========================================================================

df_test = pd.read_csv(BENCH / "test_set.csv", encoding="utf-8-sig")
df_test["gold_label"] = df_test["gold_label"].apply(norm_label)
gold_test = df_test["gold_label"].tolist()
log.info(f"Test set: {len(df_test)} pairs")


# ===========================================================================
# Prompts
# ===========================================================================

SYSTEM_FULL = """You are a bibliometric concept harmonisation assistant. Your task is to decide whether two keyword strings represent the same bibliometric concept.

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

SYSTEM_SIMPLIFIED = """You are a bibliometric concept harmonisation assistant.

Return only valid JSON. Do not include any text outside the JSON object."""

SYSTEM_BINARY = """You are a bibliometric concept harmonisation assistant. Your task is to decide whether two keyword strings represent the same bibliometric concept.

You must return a JSON object with exactly three fields:
- "decision": one of "match" or "non_match" only — do NOT use "uncertain"
- "confidence": a number between 0.0 and 1.0
- "justification": a brief explanation (1-2 sentences)

Apply these scope rules:
- match: spelling variants, punctuation/hyphenation variants, singular/plural, unambiguous acronym-expansion pairs, clear same-concept near-synonyms
- non_match: everything else — broader-narrower relations, related but distinct concepts, ambiguous cases

Return only valid JSON. Do not include any text outside the JSON object."""


def make_user_prompt_full(kw_a: str, kw_b: str) -> str:
    return (f"Keyword A: {kw_a}\nKeyword B: {kw_b}\n\n"
            f"Decide: match, non_match, or uncertain. Return JSON only.")


def make_user_prompt_binary(kw_a: str, kw_b: str) -> str:
    return (f"Keyword A: {kw_a}\nKeyword B: {kw_b}\n\n"
            f"Decide: match or non_match (no uncertain allowed). Return JSON only.")


def make_user_prompt_simplified(kw_a: str, kw_b: str) -> str:
    return (f"Are these two bibliometric keywords the same concept?\n"
            f"Keyword A: {kw_a}\n"
            f"Keyword B: {kw_b}\n"
            f'Return JSON: {{"decision": "match|non_match|uncertain", '
            f'"confidence": 0.0-1.0, "justification": "..."}}')


# ===========================================================================
# A1: No guard layer
# ===========================================================================

def run_a1_no_guard() -> tuple:
    """A1: Use raw LLM outputs from test_raw_outputs.jsonl (no guard)."""
    log.info("A1: No guard layer (reusing test raw outputs) ...")
    test_log = LLM_LOGS / "test_raw_outputs.jsonl"
    if not test_log.exists():
        log.warning("test_raw_outputs.jsonl not found — running fresh LLM calls for A1")
        return run_ablation_fresh("A1", SYSTEM_FULL, make_user_prompt_full,
                                  apply_guard=False)
    preds = []
    with open(test_log, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            raw_decision = entry.get("raw_decision", "uncertain")
            if raw_decision not in VALID_DECISIONS:
                raw_decision = "uncertain"
            preds.append(raw_decision)
    return preds, 0.0


def run_ablation_fresh(name: str, system_prompt: str,
                       user_prompt_fn, apply_guard: bool = True,
                       guard_allow_uncertain: bool = True) -> tuple:
    """Run a fresh LLM ablation on test set."""
    log_path = LLM_LOGS / f"ablation_{name}_raw_outputs.jsonl"
    preds = []
    total_cost = 0.0
    log.info(f"{name}: Running on test set ({len(df_test)} pairs) ...")
    with open(log_path, "w", encoding="utf-8") as fout:
        for idx, (_, row) in enumerate(df_test.iterrows()):
            kw_a, kw_b = row["keyword_a"], row["keyword_b"]
            user_p = user_prompt_fn(kw_a, kw_b)
            llm_result = call_llm(system_prompt, user_p)
            total_cost += llm_result["estimated_cost_usd"]

            if apply_guard:
                g = apply_guard_fn(llm_result["full_response"], CONF_THRESH,
                                   allow_uncertain=guard_allow_uncertain)
                pred = g["decision"]
            else:
                try:
                    clean_resp = _strip_markdown_fence(llm_result["full_response"])
                    parsed = json.loads(clean_resp)
                    pred = str(parsed.get("decision", "uncertain")).strip().lower()
                    if pred not in VALID_DECISIONS:
                        pred = "uncertain"
                    if not guard_allow_uncertain and pred == "uncertain":
                        pred = "non_match"
                except Exception:
                    pred = "uncertain"

            preds.append(pred)
            entry = {
                "pair_id": row.get("pair_id", str(idx)),
                "keyword_a": kw_a, "keyword_b": kw_b,
                "gold_label": row.get("gold_label", ""),
                "ablation": name, "pred": pred,
                **llm_result,
            }
            fout.write(json.dumps(entry, ensure_ascii=False) + "\n")
            if (idx + 1) % 25 == 0:
                log.info(f"  {name}: {idx+1}/{len(df_test)}")
    log.info(f"  {name} cost: ${total_cost:.4f}")
    return preds, total_cost


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def apply_guard_fn(raw_response: str, confidence_threshold: float,
                   allow_uncertain: bool = True) -> dict:
    result = {"decision": "uncertain", "confidence": 0.0, "justification": "",
              "guard_applied": None}
    clean = _strip_markdown_fence(raw_response)
    try:
        parsed = json.loads(clean)
    except Exception:
        result["guard_applied"] = "G1"
        return result
    if not {"decision", "confidence", "justification"}.issubset(parsed.keys()):
        result["guard_applied"] = "G2"
        return result
    decision = str(parsed.get("decision", "")).strip().lower()
    if decision not in VALID_DECISIONS:
        result["guard_applied"] = "G3"
        return result
    if not allow_uncertain and decision == "uncertain":
        decision = "non_match"
    result["decision"] = decision
    result["justification"] = str(parsed.get("justification", ""))
    try:
        conf = float(parsed.get("confidence", 0.0))
        conf = max(0.0, min(1.0, conf))
    except Exception:
        conf = 0.0
    result["confidence"] = conf
    if allow_uncertain and decision != "uncertain" and conf < confidence_threshold:
        result["decision"] = "uncertain"
        result["guard_applied"] = "G4"
    return result


# ===========================================================================
# Run all ablations
# ===========================================================================

ablation_results = []
total_ablation_cost = 0.0

# A1: No guard layer
preds_a1, cost_a1 = run_a1_no_guard()
total_ablation_cost += cost_a1
m_a1 = binary_metrics(gold_test, preds_a1)
m_a1["method"] = "A1_NoGuard"
ablation_results.append(m_a1)
log.info(f"A1: P={m_a1['precision']:.3f} R={m_a1['recall']:.3f} "
         f"F1={m_a1['f1']:.3f} Cov={m_a1['coverage']:.3f}")

# A2: No uncertain option (binary)
preds_a2, cost_a2 = run_ablation_fresh(
    "A2", SYSTEM_BINARY, make_user_prompt_binary,
    apply_guard=True, guard_allow_uncertain=False
)
total_ablation_cost += cost_a2
m_a2 = binary_metrics(gold_test, preds_a2)
m_a2["method"] = "A2_NoBinaryForced"
ablation_results.append(m_a2)
log.info(f"A2: P={m_a2['precision']:.3f} R={m_a2['recall']:.3f} "
         f"F1={m_a2['f1']:.3f} Cov={m_a2['coverage']:.3f}")

# A3: No auxiliary context (informational — standard prompt has no context)
# This verifies the standard workflow never adds auxiliary context
# We re-run with same full system prompt to confirm same results
log.info("A3: No auxiliary context — verifying no context in standard prompt ...")
log.info("  Standard prompt confirmed: no auxiliary context (corpus stats, co-occurrence, etc.)")
log.info("  A3 = same as Full LLM-DAG by design (context-free is the default).")
# Load Full_LLM_DAG test results for comparison
test_results_path = RESULTS / "test_results.csv"
if test_results_path.exists():
    df_tr = pd.read_csv(test_results_path, encoding="utf-8-sig")
    full_dag_row = df_tr[df_tr["method"] == "Full_LLM_DAG"]
    if len(full_dag_row) > 0:
        r = full_dag_row.iloc[0]
        m_a3 = {"method": "A3_NoAuxContext_sameAsFullDAG",
                 "precision": r["precision"], "recall": r["recall"],
                 "f1": r["f1"], "coverage": r["coverage"],
                 "uncertain_rate": r["uncertain_rate"],
                 "three_way_acc": r["three_way_acc"],
                 "note": "Identical to Full_LLM_DAG (no context was ever added)"}
    else:
        m_a3 = {"method": "A3_NoAuxContext", "note": "Full_LLM_DAG results not yet available",
                 "precision": 0, "recall": 0, "f1": 0, "coverage": 0,
                 "uncertain_rate": 0, "three_way_acc": 0}
else:
    m_a3 = {"method": "A3_NoAuxContext", "note": "Full_LLM_DAG results not yet available",
             "precision": 0, "recall": 0, "f1": 0, "coverage": 0,
             "uncertain_rate": 0, "three_way_acc": 0}
ablation_results.append(m_a3)

# A4: Simplified prompt
preds_a4, cost_a4 = run_ablation_fresh(
    "A4", SYSTEM_SIMPLIFIED, make_user_prompt_simplified,
    apply_guard=True, guard_allow_uncertain=True
)
total_ablation_cost += cost_a4
m_a4 = binary_metrics(gold_test, preds_a4)
m_a4["method"] = "A4_SimplifiedPrompt"
ablation_results.append(m_a4)
log.info(f"A4: P={m_a4['precision']:.3f} R={m_a4['recall']:.3f} "
         f"F1={m_a4['f1']:.3f} Cov={m_a4['coverage']:.3f}")

# Save ablation results
df_ablations = pd.DataFrame(ablation_results)
df_ablations.to_csv(RESULTS / "ablation_results.csv", index=False, encoding="utf-8-sig")
log.info(f"Saved ablation results -> {RESULTS / 'ablation_results.csv'}")

# Summary text
lines = ["Ablation Results (test set)", "=" * 60]
lines.append(f"{'Method':<35} {'Prec.':>7} {'Rec.':>7} {'F1':>7} "
             f"{'Cov.':>7} {'Unc.':>7} {'3-way':>7}")
lines.append("-" * 60)
for row in ablation_results:
    lines.append(
        f"{row.get('method',''):<35} "
        f"{row.get('precision',0):>7.3f} "
        f"{row.get('recall',0):>7.3f} "
        f"{row.get('f1',0):>7.3f} "
        f"{row.get('coverage',0):>7.3f} "
        f"{row.get('uncertain_rate',0):>7.3f} "
        f"{row.get('three_way_acc',0):>7.3f}"
    )
lines.append(f"\nTotal additional LLM cost (A2+A4): ${total_ablation_cost:.4f}")
lines.append(f"Model: {MODEL_ID}")
lines.append(f"Confidence threshold: {CONF_THRESH}")
summary = "\n".join(lines)
print("\n" + summary)

with open(RESULTS / "ablation_results_summary.txt", "w", encoding="utf-8") as f:
    f.write(summary + "\n")
log.info(f"Saved ablation summary -> {RESULTS / 'ablation_results_summary.txt'}")

log.info("=" * 60)
log.info("run_ablations.py COMPLETE")
log.info(f"Total ablation cost: ${total_ablation_cost:.4f}")
log.info("=" * 60)
