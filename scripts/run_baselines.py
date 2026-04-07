"""
run_baselines.py
================
Implements and evaluates baselines B1–B6 for M7 benchmark.

B1: Exact match after lowercasing
B2: Normalised exact match (NFKC + lowercase + strip + collapse)
B3: Jaro-Winkler similarity (threshold tuned on dev set)
B4: TF-IDF char n-gram cosine (threshold tuned on dev set)
B5: Sentence-embedding cosine (threshold tuned on dev set)
B6: Naive LLM (free-text prompt, no guard layer)

All thresholds tuned on dev_set.csv ONLY.
Test set used only for final reporting.
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

# ── UTF-8 stdout (Windows cp1252 terminal fix) ──────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
RESULTS = ROOT / "results"
LLM_LOGS = RESULTS / "llm_logs"
BENCH = ROOT / "data" / "benchmark"
DERIVED = ROOT / "data" / "derived"
CONFIGS = ROOT / "configs"

RESULTS.mkdir(parents=True, exist_ok=True)
LLM_LOGS.mkdir(parents=True, exist_ok=True)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Reproducibility ──────────────────────────────────────────────────────────
import random
import numpy as np
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── Imports ───────────────────────────────────────────────────────────────────
import pandas as pd
import yaml
import jellyfish
import anthropic
import os

# ── Load config ──────────────────────────────────────────────────────────────
with open(CONFIGS / "model_config.yaml", encoding="utf-8") as f:
    model_cfg = yaml.safe_load(f)

MODEL_ID = model_cfg["model"]["model_id"]
TEMPERATURE = model_cfg["model"]["temperature"]
MAX_TOKENS = model_cfg["model"]["max_tokens"]

log.info(f"Model: {MODEL_ID}")

# ── API key ───────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
client = anthropic.Anthropic(api_key=API_KEY)

# ===========================================================================
# SECTION 1 — Normalisation (Node 2 equivalent)
# ===========================================================================

def normalise(s: str) -> str:
    """
    Full Node 2 normalisation chain:
    1. Unicode NFKC
    2. Lowercase
    3. Strip
    4. Collapse whitespace
    """
    s = unicodedata.normalize("NFKC", str(s))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


# ===========================================================================
# SECTION 2 — Load benchmark data
# ===========================================================================

log.info("Loading benchmark data ...")
df_dev = pd.read_csv(BENCH / "dev_set.csv", encoding="utf-8-sig")
df_test = pd.read_csv(BENCH / "test_set.csv", encoding="utf-8-sig")

# Normalise gold labels: "non-match" -> "non_match" for consistency
def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    if lbl in ("non-match", "non_match"):
        return "non_match"
    return lbl  # "match" or "uncertain"

df_dev["gold_label"] = df_dev["gold_label"].apply(norm_label)
df_test["gold_label"] = df_test["gold_label"].apply(norm_label)

log.info(f"Dev set: {len(df_dev)} pairs | Test set: {len(df_test)} pairs")


# ===========================================================================
# SECTION 3 — Metric function
# ===========================================================================

def binary_metrics(gold: list, pred: list) -> dict:
    """
    Compute binary classification metrics.

    - Excludes gold-uncertain from precision/recall/F1 denominator
    - match = positive class
    - Returns: precision, recall, f1, coverage, uncertain_rate, three_way_acc
    """
    assert len(gold) == len(pred), "Length mismatch"
    n = len(gold)

    # Three-way accuracy (all labels)
    three_way_correct = sum(1 for g, p in zip(gold, pred) if g == p)
    three_way_acc = three_way_correct / n if n > 0 else 0.0

    # Coverage: fraction NOT predicted as uncertain
    n_uncertain_pred = sum(1 for p in pred if p == "uncertain")
    coverage = (n - n_uncertain_pred) / n if n > 0 else 0.0
    uncertain_rate = n_uncertain_pred / n if n > 0 else 0.0

    # Binary metrics — exclude gold-uncertain pairs from denominator
    binary_pairs = [(g, p) for g, p in zip(gold, pred) if g != "uncertain"]
    # Among binary-gold pairs, also exclude uncertain predictions from prec/rec
    # (uncertain predictions reduce coverage, counted separately)
    decided_pairs = [(g, p) for g, p in binary_pairs if p != "uncertain"]

    if len(decided_pairs) == 0:
        precision = 0.0
        recall_denom = len(binary_pairs)
        tp = 0
        recall = 0.0
    else:
        tp = sum(1 for g, p in decided_pairs if g == "match" and p == "match")
        fp = sum(1 for g, p in decided_pairs if g != "match" and p == "match")
        fn_decided = sum(1 for g, p in decided_pairs if g == "match" and p != "match")
        # FN also includes gold=match predicted as uncertain
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
# SECTION 4 — B1: Exact match after lowercasing
# ===========================================================================

def b1_exact(a: str, b: str) -> str:
    return "match" if a.lower() == b.lower() else "non_match"


def run_b1(df: pd.DataFrame) -> list:
    return [b1_exact(row["keyword_a"], row["keyword_b"]) for _, row in df.iterrows()]


# ===========================================================================
# SECTION 5 — B2: Normalised exact match
# ===========================================================================

def b2_normalised(a: str, b: str) -> str:
    return "match" if normalise(a) == normalise(b) else "non_match"


def run_b2(df: pd.DataFrame) -> list:
    return [b2_normalised(row["keyword_a"], row["keyword_b"]) for _, row in df.iterrows()]


# ===========================================================================
# SECTION 6 — B3: Jaro-Winkler
# ===========================================================================

def b3_predict(df: pd.DataFrame, threshold: float) -> list:
    preds = []
    for _, row in df.iterrows():
        a = normalise(row["keyword_a"])
        b = normalise(row["keyword_b"])
        score = jellyfish.jaro_winkler_similarity(a, b)
        preds.append("match" if score >= threshold else "non_match")
    return preds


def tune_b3(df_dev: pd.DataFrame) -> tuple:
    log.info("Tuning B3 (Jaro-Winkler) on dev set ...")
    best_f1, best_thresh = -1, 0.85
    gold = df_dev["gold_label"].tolist()
    for thresh in np.arange(0.80, 1.00, 0.01):
        thresh = round(float(thresh), 2)
        preds = b3_predict(df_dev, thresh)
        m = binary_metrics(gold, preds)
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_thresh = thresh
    log.info(f"  B3 best threshold: {best_thresh:.2f}, dev F1: {best_f1:.4f}")
    return best_thresh, best_f1


# ===========================================================================
# SECTION 7 — B4: TF-IDF char n-gram cosine
# ===========================================================================

def build_tfidf_index():
    """Build TF-IDF vectoriser from full keyword inventory."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    log.info("Loading keyword inventory for TF-IDF ...")
    df_freq = pd.read_csv(DERIVED / "author_keyword_frequencies.csv", encoding="utf-8-sig")
    df_freq.columns = ["keyword", "frequency"]
    df_freq = df_freq.dropna(subset=["keyword"])
    kws = df_freq["keyword"].astype(str).str.strip().tolist()
    norm_kws = [normalise(k) for k in kws]
    log.info(f"  Fitting TF-IDF on {len(norm_kws):,} keywords ...")
    vectoriser = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    vectoriser.fit(norm_kws)
    log.info("  TF-IDF fitted.")
    return vectoriser


def b4_predict(df: pd.DataFrame, vectoriser, threshold: float) -> list:
    from sklearn.metrics.pairwise import cosine_similarity
    preds = []
    for _, row in df.iterrows():
        a = normalise(row["keyword_a"])
        b = normalise(row["keyword_b"])
        vecs = vectoriser.transform([a, b])
        sim = cosine_similarity(vecs[0], vecs[1])[0, 0]
        preds.append("match" if sim >= threshold else "non_match")
    return preds


def tune_b4(df_dev: pd.DataFrame, vectoriser) -> tuple:
    log.info("Tuning B4 (TF-IDF) on dev set ...")
    best_f1, best_thresh = -1, 0.60
    gold = df_dev["gold_label"].tolist()
    for thresh in np.arange(0.30, 0.96, 0.01):
        thresh = round(float(thresh), 2)
        preds = b4_predict(df_dev, vectoriser, thresh)
        m = binary_metrics(gold, preds)
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_thresh = thresh
    log.info(f"  B4 best threshold: {best_thresh:.2f}, dev F1: {best_f1:.4f}")
    return best_thresh, best_f1


# ===========================================================================
# SECTION 8 — B5: Embedding cosine
# ===========================================================================

def build_embedding_model():
    from sentence_transformers import SentenceTransformer
    log.info("Loading sentence-transformers (all-MiniLM-L6-v2) ...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model


def b5_predict(df: pd.DataFrame, emb_model, threshold: float) -> list:
    from sklearn.metrics.pairwise import cosine_similarity
    preds = []
    pairs_a = [normalise(row["keyword_a"]) for _, row in df.iterrows()]
    pairs_b = [normalise(row["keyword_b"]) for _, row in df.iterrows()]
    # Batch encode
    all_texts = pairs_a + pairs_b
    embs = emb_model.encode(all_texts, batch_size=128, normalize_embeddings=True,
                             show_progress_bar=False, convert_to_numpy=True)
    n = len(pairs_a)
    embs_a = embs[:n]
    embs_b = embs[n:]
    for i in range(n):
        sim = float(np.dot(embs_a[i], embs_b[i]))
        preds.append("match" if sim >= threshold else "non_match")
    return preds


def tune_b5(df_dev: pd.DataFrame, emb_model) -> tuple:
    log.info("Tuning B5 (Embedding) on dev set ...")
    best_f1, best_thresh = -1, 0.70
    gold = df_dev["gold_label"].tolist()
    for thresh in np.arange(0.50, 0.96, 0.01):
        thresh = round(float(thresh), 2)
        preds = b5_predict(df_dev, emb_model, thresh)
        m = binary_metrics(gold, preds)
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_thresh = thresh
    log.info(f"  B5 best threshold: {best_thresh:.2f}, dev F1: {best_f1:.4f}")
    return best_thresh, best_f1


# ===========================================================================
# SECTION 9 — B6: Naive LLM
# ===========================================================================

def _prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _call_llm_with_retry(prompt: str, max_retries: int = 3) -> tuple:
    """Call LLM with exponential backoff. Returns (response_text, usage_dict)."""
    delays = [1, 2, 4]
    last_exc = None
    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model=MODEL_ID,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            )
            resp_text = msg.content[0].text if msg.content else ""
            usage = {
                "input_tokens": msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
                "stop_reason": msg.stop_reason,
            }
            return resp_text, usage
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(delays[attempt])
    raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_exc}")


def parse_b6_response(text: str) -> str:
    """Parse free-text B6 response into match/non_match/uncertain."""
    t = text.lower().strip()
    if "non-match" in t or "not the same" in t or "non_match" in t or "not match" in t:
        return "non_match"
    if "match" in t:
        return "match"
    return "uncertain"


def run_b6(df: pd.DataFrame, split: str = "dev") -> list:
    """Run B6 naive LLM on a dataframe. split='dev' or 'test'."""
    log_path = LLM_LOGS / f"b6_{split}_raw_outputs.jsonl"
    preds = []
    log.info(f"Running B6 (Naive LLM) on {split} set ({len(df)} pairs) ...")
    cost_per_1k_in = 0.00025   # haiku approximate pricing
    cost_per_1k_out = 0.00125
    with open(log_path, "w", encoding="utf-8") as fout:
        for idx, (_, row) in enumerate(df.iterrows()):
            prompt = (
                f"Are these two keywords the same concept?\n"
                f"Keyword A: {row['keyword_a']}\n"
                f"Keyword B: {row['keyword_b']}\n"
                f"Answer: match, non-match, or uncertain."
            )
            ph = _prompt_hash(prompt)
            ts = datetime.now(timezone.utc).isoformat()
            try:
                resp_text, usage = _call_llm_with_retry(prompt)
                pred = parse_b6_response(resp_text)
                cost = (usage["input_tokens"] / 1000 * cost_per_1k_in +
                        usage["output_tokens"] / 1000 * cost_per_1k_out)
                entry = {
                    "pair_id": row.get("pair_id", str(idx)),
                    "keyword_a": row["keyword_a"],
                    "keyword_b": row["keyword_b"],
                    "prompt_hash": ph,
                    "response": resp_text,
                    "parsed": pred,
                    "timestamp": ts,
                    "model_id": MODEL_ID,
                    "input_tokens": usage["input_tokens"],
                    "output_tokens": usage["output_tokens"],
                    "estimated_cost_usd": round(cost, 6),
                }
                preds.append(pred)
            except Exception as exc:
                log.error(f"  B6 pair {idx} failed: {exc}")
                entry = {
                    "pair_id": row.get("pair_id", str(idx)),
                    "keyword_a": row["keyword_a"],
                    "keyword_b": row["keyword_b"],
                    "prompt_hash": ph,
                    "response": f"ERROR: {exc}",
                    "parsed": "uncertain",
                    "timestamp": ts,
                    "model_id": MODEL_ID,
                    "error": str(exc),
                }
                preds.append("uncertain")
            fout.write(json.dumps(entry, ensure_ascii=False) + "\n")
            if (idx + 1) % 25 == 0:
                log.info(f"  B6 {split}: {idx+1}/{len(df)} done")
    log.info(f"  B6 {split} complete. Log -> {log_path}")
    return preds


# ===========================================================================
# SECTION 10 — Threshold tuning and evaluation
# ===========================================================================

log.info("=" * 60)
log.info("STEP 1: Tuning thresholds on dev set")
log.info("=" * 60)

# B3 tuning
b3_thresh, b3_dev_f1 = tune_b3(df_dev)

# B4 tuning
vectoriser = build_tfidf_index()
b4_thresh, b4_dev_f1 = tune_b4(df_dev, vectoriser)

# B5 tuning
emb_model = build_embedding_model()
b5_thresh, b5_dev_f1 = tune_b5(df_dev, emb_model)

# Save thresholds
tuned = {
    "b3_jaro_winkler": {"threshold": b3_thresh, "dev_f1": b3_dev_f1},
    "b4_tfidf_ngram":  {"threshold": b4_thresh, "dev_f1": b4_dev_f1},
    "b5_embedding":    {"threshold": b5_thresh, "dev_f1": b5_dev_f1},
}
thresh_path = RESULTS / "tuned_thresholds.json"
# Merge with existing if present (for workflow threshold added later)
existing = {}
if thresh_path.exists():
    with open(thresh_path, encoding="utf-8") as f:
        existing = json.load(f)
existing.update(tuned)
with open(thresh_path, "w", encoding="utf-8") as f:
    json.dump(existing, f, indent=2)
log.info(f"Saved tuned thresholds -> {thresh_path}")


# ===========================================================================
# SECTION 11 — Dev set evaluation (all baselines)
# ===========================================================================

log.info("=" * 60)
log.info("STEP 2: Evaluating all baselines on dev set")
log.info("=" * 60)

gold_dev = df_dev["gold_label"].tolist()

dev_preds = {
    "B1_Exact":         run_b1(df_dev),
    "B2_Normalised":    run_b2(df_dev),
    "B3_JaroWinkler":   b3_predict(df_dev, b3_thresh),
    "B4_TFIDF":         b4_predict(df_dev, vectoriser, b4_thresh),
    "B5_Embedding":     b5_predict(df_dev, emb_model, b5_thresh),
    "B6_NaiveLLM":      run_b6(df_dev, split="dev"),
}

dev_results = []
for method, preds in dev_preds.items():
    m = binary_metrics(gold_dev, preds)
    m["method"] = method
    m["split"] = "dev"
    dev_results.append(m)
    log.info(f"  {method}: P={m['precision']:.3f} R={m['recall']:.3f} "
             f"F1={m['f1']:.3f} Cov={m['coverage']:.3f} Unc={m['uncertain_rate']:.3f} "
             f"3-way={m['three_way_acc']:.3f}")

df_dev_results = pd.DataFrame(dev_results)
df_dev_results.to_csv(RESULTS / "dev_results_baselines.csv", index=False, encoding="utf-8-sig")
log.info(f"Saved dev results -> {RESULTS / 'dev_results_baselines.csv'}")


# ===========================================================================
# SECTION 12 — Test set evaluation (all baselines)
# ===========================================================================

log.info("=" * 60)
log.info("STEP 3: Evaluating all baselines on test set")
log.info("=" * 60)

gold_test = df_test["gold_label"].tolist()

test_preds = {
    "B1_Exact":         run_b1(df_test),
    "B2_Normalised":    run_b2(df_test),
    "B3_JaroWinkler":   b3_predict(df_test, b3_thresh),
    "B4_TFIDF":         b4_predict(df_test, vectoriser, b4_thresh),
    "B5_Embedding":     b5_predict(df_test, emb_model, b5_thresh),
    "B6_NaiveLLM":      run_b6(df_test, split="test"),
}

test_results = []
for method, preds in test_preds.items():
    m = binary_metrics(gold_test, preds)
    m["method"] = method
    m["split"] = "test"
    test_results.append(m)
    log.info(f"  {method}: P={m['precision']:.3f} R={m['recall']:.3f} "
             f"F1={m['f1']:.3f} Cov={m['coverage']:.3f} Unc={m['uncertain_rate']:.3f} "
             f"3-way={m['three_way_acc']:.3f}")

df_test_results = pd.DataFrame(test_results)
df_test_results.to_csv(RESULTS / "test_results_baselines.csv", index=False, encoding="utf-8-sig")
log.info(f"Saved test results -> {RESULTS / 'test_results_baselines.csv'}")

# Save test predictions for each baseline
df_test_preds_all = df_test[["pair_id", "keyword_a", "keyword_b", "gold_label"]].copy()
for method, preds in test_preds.items():
    df_test_preds_all[method] = preds
df_test_preds_all.to_csv(RESULTS / "test_predictions_baselines.csv", index=False, encoding="utf-8-sig")
log.info(f"Saved test predictions -> {RESULTS / 'test_predictions_baselines.csv'}")

log.info("=" * 60)
log.info("run_baselines.py COMPLETE")
log.info("=" * 60)
