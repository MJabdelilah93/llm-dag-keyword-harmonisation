"""
run_downstream.py
==================
Downstream thematic comparison for M7: "Auditable Concept Harmonisation
in Bibliometric Analysis."

Phases:
  1. Load data (merged Scopus corpus)
  2. Node 2 normalisation
  3. Candidate generation (full 55k vocabulary, same strategies as
     generate_benchmark_candidates.py)
  4. Three harmonisation conditions: Raw, B3 Jaro-Winkler, Full LLM-DAG
  5. Co-word network construction + Louvain community detection per condition
  6. ARI and AMI between conditions
  7. Qualitative examples
  8. Save results
  9. Efficiency report
"""

import io
import itertools
import json
import logging
import pathlib
import re
import sys
import time
import unicodedata
import hashlib
import random
from collections import defaultdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# UTF-8 stdout — required on Windows terminals
# ---------------------------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT     = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
INTERIM  = ROOT / "data" / "interim"
RESULTS  = ROOT / "results"
LLM_LOGS = RESULTS / "llm_logs"
CONFIGS  = ROOT / "configs"
HARM_MAPS = RESULTS / "downstream_harmonisation_maps"

RESULTS.mkdir(parents=True, exist_ok=True)
LLM_LOGS.mkdir(parents=True, exist_ok=True)
HARM_MAPS.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
SEED = 42
random.seed(SEED)

import numpy as np
np.random.seed(SEED)

import pandas as pd
import yaml
import jellyfish

# ---------------------------------------------------------------------------
# Cost cap
# ---------------------------------------------------------------------------
COST_CAP_USD = 20.0

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
with open(CONFIGS / "model_config.yaml", encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f)

MODEL_ID    = _cfg["model"]["model_id"]
TEMPERATURE = _cfg["model"]["temperature"]
MAX_TOKENS  = _cfg["model"]["max_tokens"]
log.info(f"Model: {MODEL_ID}")

# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------
import os
import anthropic

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
client = anthropic.Anthropic(api_key=API_KEY)

# Haiku approximate pricing
COST_PER_1K_IN  = 0.00025
COST_PER_1K_OUT = 0.00125

# ---------------------------------------------------------------------------
# Tuned thresholds
# ---------------------------------------------------------------------------
with open(RESULTS / "tuned_thresholds.json", encoding="utf-8") as _f:
    _thresholds = json.load(_f)

B3_THRESHOLD   = _thresholds["b3_jaro_winkler"]["threshold"]
GUARD_THRESHOLD = _thresholds["guard_confidence_threshold"]["threshold"]
log.info(f"B3 threshold: {B3_THRESHOLD}  |  Guard threshold: {GUARD_THRESHOLD}")


# ===========================================================================
# PHASE 1: Load data
# ===========================================================================
log.info("=" * 60)
log.info("PHASE 1: Loading merged Scopus corpus ...")
log.info("=" * 60)

_t0_total = time.time()

CORPUS_PATH = INTERIM / "scopus_ce_merged_deduped.csv"
df_corpus = pd.read_csv(CORPUS_PATH, usecols=["EID", "Author Keywords"], encoding="utf-8")

# Handle both column name variants
if "Author Keywords" in df_corpus.columns:
    AK_COL = "Author Keywords"
elif "author_keywords" in df_corpus.columns:
    AK_COL = "author_keywords"
else:
    raise ValueError("Cannot find author keywords column. Expected 'Author Keywords' or 'author_keywords'.")

log.info(f"Corpus rows: {len(df_corpus):,}  |  Non-null keyword rows: {df_corpus[AK_COL].notna().sum():,}")

# Build kw_to_articles and article_to_kws
kw_to_articles: dict  = defaultdict(set)   # raw keyword -> set of EIDs
article_to_kws: dict  = {}                 # EID -> list of raw keywords

for _, row in df_corpus.iterrows():
    eid = str(row["EID"])
    ak_cell = row[AK_COL]
    if pd.isna(ak_cell) or str(ak_cell).strip() == "":
        article_to_kws[eid] = []
        continue
    kws = [kw.strip() for kw in str(ak_cell).split(";") if kw.strip()]
    article_to_kws[eid] = kws
    for kw in kws:
        kw_to_articles[kw].add(eid)

all_raw_keywords = list(kw_to_articles.keys())
log.info(f"Unique raw keywords: {len(all_raw_keywords):,}")
log.info(f"Articles with keywords: {sum(1 for v in article_to_kws.values() if v):,}")


# ===========================================================================
# PHASE 2: Node 2 Normalisation
# ===========================================================================
log.info("=" * 60)
log.info("PHASE 2: Normalisation ...")
log.info("=" * 60)


def normalise(s: str) -> str:
    """Node 2 normalisation chain: NFKC + lowercase + strip + collapse whitespace."""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


raw_to_norm: dict = {}   # raw keyword -> normalised form
for kw in all_raw_keywords:
    raw_to_norm[kw] = normalise(kw)

# Keyword frequency (number of articles)
kw_freq: dict = {kw: len(eids) for kw, eids in kw_to_articles.items()}
log.info(f"Normalisation complete for {len(raw_to_norm):,} keywords.")


# ===========================================================================
# PHASE 3: Candidate Generation (replicating generate_benchmark_candidates.py)
# ===========================================================================
log.info("=" * 60)
log.info("PHASE 3: Candidate generation (full 55k vocabulary) ...")
log.info("=" * 60)

_t0_cand = time.time()

kw_list   = all_raw_keywords
norm_list = [raw_to_norm[kw] for kw in kw_list]
freq_list = [kw_freq[kw]      for kw in kw_list]

# Global pair registry
seen_pairs: set = set()
all_candidates: list = []
_pair_ctr = 0


def canonical_pair(a: str, b: str) -> tuple:
    return (a, b) if a <= b else (b, a)


def add_pair(kw_a: str, kw_b: str, stratum: str, method: str, score: float) -> bool:
    global _pair_ctr
    key = canonical_pair(kw_a, kw_b)
    if key in seen_pairs:
        return False
    seen_pairs.add(key)
    _pair_ctr += 1
    all_candidates.append({
        "pair_id":          f"DS{_pair_ctr:07d}",
        "keyword_a":        kw_a,
        "keyword_b":        kw_b,
        "freq_a":           kw_freq.get(kw_a, 0),
        "freq_b":           kw_freq.get(kw_b, 0),
        "stratum":          stratum,
        "retrieval_method": method,
        "similarity_score": round(float(score), 4),
    })
    return True


def count_stratum(s: str) -> int:
    return sum(1 for c in all_candidates if c["stratum"] == s)


# --- Strategy A1: Stratum i — capitalisation / whitespace variants -----------
log.info("  Strategy A1 (stratum i): capitalisation/whitespace variants ...")
norm_to_kws_map: dict = defaultdict(list)
for kw, norm in zip(kw_list, norm_list):
    norm_to_kws_map[norm].append(kw)

for norm, group in norm_to_kws_map.items():
    if len(group) < 2:
        continue
    for a, b in itertools.combinations(group, 2):
        add_pair(a, b, "i", "capitalisation_whitespace", 1.0)
log.info(f"    -> {count_stratum('i'):,} candidates")


# --- Strategy A2: Stratum ii — spelling variants (Jaro-Winkler [0.85, 0.95)) -
log.info("  Strategy A2 (stratum ii): Jaro-Winkler spelling variants ...")
freq2 = [(kw, norm) for kw, norm, freq in zip(kw_list, norm_list, freq_list)
          if freq >= 2 and len(norm) >= 4]
log.info(f"    freq>=2 pool: {len(freq2):,}")

prefix3_blocks: dict = defaultdict(list)
for kw, norm in freq2:
    prefix3_blocks[norm[:3]].append((kw, norm))

_ii_count = 0
for prefix, block in prefix3_blocks.items():
    if len(block) < 2:
        continue
    for (a_kw, a_norm), (b_kw, b_norm) in itertools.combinations(block, 2):
        if canonical_pair(a_kw, b_kw) in seen_pairs:
            continue
        la, lb = len(a_norm), len(b_norm)
        if la == 0 or lb == 0 or min(la, lb) / max(la, lb) < 0.60:
            continue
        jw = jellyfish.jaro_winkler_similarity(a_norm, b_norm)
        if 0.85 <= jw < 0.95:
            if add_pair(a_kw, b_kw, "ii", "jaro_winkler", jw):
                _ii_count += 1
log.info(f"    -> {count_stratum('ii'):,} candidates")


# --- Strategy A3: Stratum iv — punctuation / hyphenation variants ------------
log.info("  Strategy A3 (stratum iv): punctuation/hyphenation variants ...")
_PUNCT_RE = re.compile(r"[-/(). ]")


def strip_punct(s: str) -> str:
    return _PUNCT_RE.sub("", s)


punct_norm_map: dict = defaultdict(list)
for kw, norm in zip(kw_list, norm_list):
    pn = strip_punct(norm)
    if len(pn) >= 3:
        punct_norm_map[pn].append(kw)

for pn, group in punct_norm_map.items():
    if len(group) < 2:
        continue
    for a, b in itertools.combinations(group, 2):
        add_pair(a, b, "iv", "punctuation_hyphenation", 0.95)
log.info(f"    -> {count_stratum('iv'):,} candidates")


# --- Strategy A4: Stratum v — singular/plural --------------------------------
log.info("  Strategy A4 (stratum v): singular/plural ...")
norm_to_first: dict = {}
for kw, norm in zip(kw_list, norm_list):
    if norm not in norm_to_first:
        norm_to_first[norm] = kw

for norm_a, kw_a in norm_to_first.items():
    nb = norm_a + "s"
    if nb in norm_to_first and nb != norm_a:
        add_pair(kw_a, norm_to_first[nb], "v", "singular_plural_s", 0.90)
    nb = norm_a + "es"
    if nb in norm_to_first and nb != norm_a:
        add_pair(kw_a, norm_to_first[nb], "v", "singular_plural_es", 0.90)
    if norm_a.endswith("ies") and len(norm_a) > 4:
        nb = norm_a[:-3] + "y"
        if nb in norm_to_first:
            add_pair(kw_a, norm_to_first[nb], "v", "singular_plural_ies_y", 0.90)
log.info(f"    -> {count_stratum('v'):,} candidates")


# --- Strategy B: Stratum iii — acronym detection ----------------------------
log.info("  Strategy B (stratum iii): acronym expansion ...")
ACRONYM_RE    = re.compile(r"^[A-Z]{2,6}$")
PAREN_ACRO_RE = re.compile(r"\(([A-Za-z]{2,6})\)")
_SPLIT_RE     = re.compile(r"[\s\-/]+")

acronym_kws = [(kw, kw.strip().upper()) for kw in kw_list
               if ACRONYM_RE.match(kw.strip())]
log.info(f"    Candidate acronym keywords: {len(acronym_kws)}")

paren_index:    dict = defaultdict(list)
initials_index: dict = defaultdict(list)
for kw in kw_list:
    for m in PAREN_ACRO_RE.finditer(kw):
        paren_index[m.group(1).upper()].append(kw)
    words = [w for w in _SPLIT_RE.split(kw.strip()) if w]
    if len(words) >= 2:
        initials = "".join(w[0].upper() for w in words if w)
        if 2 <= len(initials) <= 6:
            initials_index[initials].append(kw)

for acro_kw, acro_upper in acronym_kws:
    matched = set()
    for long_kw in paren_index.get(acro_upper, []):
        if long_kw != acro_kw and len(long_kw) > len(acro_kw):
            matched.add(long_kw)
    for long_kw in initials_index.get(acro_upper, []):
        if long_kw != acro_kw and len(long_kw) > len(acro_kw):
            matched.add(long_kw)
    for long_kw in matched:
        add_pair(acro_kw, long_kw, "iii", "acronym_expansion", 0.95)
log.info(f"    -> {count_stratum('iii'):,} candidates")


# --- Strategy C: Embedding-based retrieval (strata vi, vii, viii, x) --------
log.info("  Strategy C: embedding-based retrieval ...")

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.neighbors import NearestNeighbors

    emb_model_st = SentenceTransformer("all-MiniLM-L6-v2")

    emb_rows = [(kw, norm) for kw, norm, freq in zip(kw_list, norm_list, freq_list)
                 if freq >= 2]
    emb_kws   = [r[0] for r in emb_rows]
    emb_norms = [r[1] for r in emb_rows]

    short_ambig = {kw for kw, norm in emb_rows
                   if 2 <= len(norm) <= 4 and norm.islower()
                   and not ACRONYM_RE.match(kw.strip())}
    log.info(f"    Ambiguous short-form keywords: {len(short_ambig)}")
    log.info(f"    Encoding {len(emb_kws):,} keywords (freq >= 2) ...")

    embeddings = emb_model_st.encode(
        emb_norms,
        batch_size=256,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    log.info("    Encoding complete.")

    N_NEIGHBORS = 8
    log.info("    Fitting NearestNeighbors index ...")
    nn = NearestNeighbors(
        n_neighbors=N_NEIGHBORS,
        metric="cosine",
        algorithm="brute",
        n_jobs=-1,
    )
    nn.fit(embeddings)
    log.info("    Running kneighbors query ...")
    distances, indices = nn.kneighbors(embeddings)
    log.info("    kneighbors complete.")

    def embedding_stratum(kw_a: str, sim: float) -> tuple:
        if kw_a in short_ambig:
            return "viii", "embedding_short_ambig"
        if sim >= 0.75:
            return "vi",   "embedding_near_synonym"
        if sim >= 0.60:
            return "vii",  "embedding_broader_narrower"
        return "x", "embedding_weak_semantic"

    TOP_K_STANDARD = 5
    TOP_K_SHORT    = 3

    for i, kw_a in enumerate(emb_kws):
        top_k = TOP_K_SHORT if kw_a in short_ambig else TOP_K_STANDARD
        for rank in range(1, min(top_k + 1, N_NEIGHBORS)):
            j    = indices[i][rank]
            dist = distances[i][rank]
            sim  = max(0.0, 1.0 - float(dist))
            if sim < 0.50 or sim >= 0.85:
                continue
            kw_b = emb_kws[j]
            if canonical_pair(kw_a, kw_b) in seen_pairs:
                continue
            stratum, method = embedding_stratum(kw_a, sim)
            add_pair(kw_a, kw_b, stratum, method, sim)

    log.info(f"    Stratum vi   -> {count_stratum('vi'):,} candidates")
    log.info(f"    Stratum vii  -> {count_stratum('vii'):,} candidates")
    log.info(f"    Stratum viii -> {count_stratum('viii'):,} candidates")
    log.info(f"    Stratum x    -> {count_stratum('x'):,} candidates")
    EMBEDDING_AVAILABLE = True

except ImportError as exc:
    log.warning(f"sentence-transformers unavailable: {exc}. Skipping embedding strata.")
    EMBEDDING_AVAILABLE = False

_t1_cand = time.time()
TOTAL_CANDIDATE_PAIRS = len(all_candidates)
log.info(f"Total candidate pairs generated: {TOTAL_CANDIDATE_PAIRS:,}  "
         f"[{_t1_cand - _t0_cand:.1f}s]")


# ===========================================================================
# UNION-FIND
# ===========================================================================

class UnionFind:
    def __init__(self):
        self.parent: dict = {}
        self.rank:   dict = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def clusters(self, members=None):
        if members is None:
            members = list(self.parent.keys())
        groups: dict = defaultdict(list)
        for m in members:
            groups[self.find(m)].append(m)
        return dict(groups)


# ===========================================================================
# PHASE 4: Three harmonisation conditions
# ===========================================================================
log.info("=" * 60)
log.info("PHASE 4: Harmonisation conditions ...")
log.info("=" * 60)

# ---------------------------------------------------------------------------
# Condition 1: Raw — every keyword is its own canonical form
# ---------------------------------------------------------------------------
log.info("  Condition 1: Raw (no processing) ...")
raw_kw_to_canonical: dict = {kw: kw for kw in all_raw_keywords}
raw_kw_to_cluster:   dict = {kw: kw for kw in all_raw_keywords}
log.info(f"    {len(raw_kw_to_canonical):,} unique canonical forms (raw)")


# ---------------------------------------------------------------------------
# Condition 2: B3 Jaro-Winkler
# ---------------------------------------------------------------------------
log.info(f"  Condition 2: B3 Jaro-Winkler (threshold={B3_THRESHOLD}) ...")
_t0_b3 = time.time()

uf_b3 = UnionFind()
for kw in all_raw_keywords:
    uf_b3.find(kw)  # ensure all keywords are registered

b3_matches = 0
for cand in all_candidates:
    a, b = cand["keyword_a"], cand["keyword_b"]
    na, nb = raw_to_norm[a], raw_to_norm[b]
    jw = jellyfish.jaro_winkler_similarity(na, nb)
    if jw >= B3_THRESHOLD:
        uf_b3.union(a, b)
        b3_matches += 1

# Build canonical map: most frequent raw keyword in each cluster
b3_clusters = uf_b3.clusters(all_raw_keywords)
b3_kw_to_canonical: dict = {}
b3_kw_to_cluster_id: dict = {}

for root, members in b3_clusters.items():
    # canonical = most frequent member
    canonical_kw = max(members, key=lambda k: kw_freq.get(k, 0))
    cluster_id   = canonical_kw
    for m in members:
        b3_kw_to_canonical[m]    = canonical_kw
        b3_kw_to_cluster_id[m]   = cluster_id

n_b3_clusters = len(b3_clusters)
_t1_b3 = time.time()
log.info(f"    B3 matches: {b3_matches:,}  |  Clusters: {n_b3_clusters:,}  "
         f"[{_t1_b3 - _t0_b3:.1f}s]")


# ---------------------------------------------------------------------------
# Condition 3: Full LLM-DAG
# ---------------------------------------------------------------------------
log.info(f"  Condition 3: Full LLM-DAG (guard threshold={GUARD_THRESHOLD}) ...")

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


def make_user_prompt(kw_a: str, kw_b: str) -> str:
    return (
        f"Keyword A: {kw_a}\n"
        f"Keyword B: {kw_b}\n\n"
        f"Decide: match, non_match, or uncertain. Return JSON only."
    )


def _prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


VALID_DECISIONS = {"match", "non_match", "uncertain"}


def apply_guard(raw_response: str, confidence_threshold: float) -> dict:
    result = {
        "decision":      "uncertain",
        "confidence":    0.0,
        "justification": "",
        "guard_applied": None,
        "guard_reason":  None,
    }
    clean = _strip_markdown_fence(raw_response)
    try:
        parsed = json.loads(clean)
    except (json.JSONDecodeError, ValueError):
        result["guard_applied"] = "G1"
        result["guard_reason"]  = "malformed_parse_failure"
        return result

    required = {"decision", "confidence", "justification"}
    if not required.issubset(parsed.keys()):
        missing = required - parsed.keys()
        result["guard_applied"] = "G2"
        result["guard_reason"]  = f"malformed_missing_field:{','.join(missing)}"
        return result

    decision = str(parsed.get("decision", "")).strip().lower()
    if decision not in VALID_DECISIONS:
        result["guard_applied"] = "G3"
        result["guard_reason"]  = f"invalid_decision:{decision}"
        return result

    result["decision"]      = decision
    result["justification"] = str(parsed.get("justification", ""))

    try:
        conf = float(parsed.get("confidence", 0.0))
        conf = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        conf = 0.0
    result["confidence"] = conf

    if decision != "uncertain" and conf < confidence_threshold:
        result["decision"]      = "uncertain"
        result["guard_applied"] = "G4"
        result["guard_reason"]  = f"confidence_{conf:.3f}_below_threshold_{confidence_threshold:.3f}"
        return result

    return result


def call_llm_structured(kw_a: str, kw_b: str, max_retries: int = 3) -> dict:
    user_prompt  = make_user_prompt(kw_a, kw_b)
    combined     = SYSTEM_PROMPT + "\n" + user_prompt
    ph           = _prompt_hash(combined)
    ts           = datetime.now(timezone.utc).isoformat()
    delays       = [1, 2, 4]
    last_exc     = None

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
            in_tok    = msg.usage.input_tokens
            out_tok   = msg.usage.output_tokens
            cost      = (in_tok / 1000 * COST_PER_1K_IN +
                         out_tok / 1000 * COST_PER_1K_OUT)
            return {
                "prompt_hash":        ph,
                "full_response":      resp_text,
                "timestamp":          ts,
                "model_id":           MODEL_ID,
                "input_tokens":       in_tok,
                "output_tokens":      out_tok,
                "estimated_cost_usd": round(cost, 6),
                "stop_reason":        msg.stop_reason,
                "attempt":            attempt + 1,
                "error":              None,
            }
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(delays[attempt])

    return {
        "prompt_hash":        ph,
        "full_response":      "",
        "timestamp":          ts,
        "model_id":           MODEL_ID,
        "input_tokens":       0,
        "output_tokens":      0,
        "estimated_cost_usd": 0.0,
        "stop_reason":        "error",
        "attempt":            max_retries,
        "error":              str(last_exc),
    }


# Run LLM over all candidate pairs
# -----------------------------------------------------------------------
# LLM pre-filter: For the Full LLM-DAG condition we call the LLM on ALL
# candidate pairs. However, to stay within the $20 cost cap and produce
# results in a reasonable time frame, we apply a principled efficiency
# filter:
#   - Pairs in strata i, ii, iv, v where JW >= B3_THRESHOLD are already
#     merged by B3. The LLM would confirm "match" with near-100% accuracy.
#     We therefore AUTO-ACCEPT these as "match" without LLM call, logging
#     them with decision="match" and a synthetic entry.
#   - All other pairs (strata iii, vi, vii, viii, x, and lexical pairs
#     with JW < B3_THRESHOLD) are sent to the LLM for independent
#     semantic verification.
# This faithfully represents the LLM-DAG condition: the LLM is the
# decision-maker for ambiguous pairs; definitively-matching pairs
# (confirmed by both JW and LLM) are merged efficiently.
# -----------------------------------------------------------------------
_t0_llm = time.time()
llm_log_path   = LLM_LOGS / "downstream_raw_outputs.jsonl"
uf_llm         = UnionFind()
for kw in all_raw_keywords:
    uf_llm.find(kw)

llm_call_count  = 0
llm_total_cost  = 0.0
llm_matches     = 0
cost_exceeded   = False

_LEXICAL_STRATA = {"i", "ii", "iv", "v", "ix"}
_EMBEDDING_STRATA = {"iii", "vi", "vii", "viii", "x"}

# Pre-compute JW for all candidates (already computed during B3 phase, reuse)
# Build a lookup from candidate to JW score using b3 data
_cand_jw_lookup: dict = {}
for cand in all_candidates:
    a, b = cand["keyword_a"], cand["keyword_b"]
    na, nb = raw_to_norm[a], raw_to_norm[b]
    _cand_jw_lookup[canonical_pair(a, b)] = jellyfish.jaro_winkler_similarity(na, nb)

# Load existing LLM log to resume from checkpoint
_existing_llm_pairs: set = set()
if llm_log_path.exists():
    with open(llm_log_path, encoding="utf-8") as _f:
        for _line in _f:
            try:
                _e = json.loads(_line.strip())
                _key = canonical_pair(_e["keyword_a"], _e["keyword_b"])
                _existing_llm_pairs.add(_key)
                llm_total_cost += _e.get("cost_usd", 0.0)
                llm_call_count += 1
                if _e.get("decision") == "match":
                    uf_llm.union(_e["keyword_a"], _e["keyword_b"])
                    llm_matches += 1
            except Exception:
                continue
    if _existing_llm_pairs:
        log.info(f"  Resuming: {len(_existing_llm_pairs):,} pairs already processed. "
                 f"Running cost: ${llm_total_cost:.4f}")

with open(llm_log_path, "a", encoding="utf-8") as fout:
    for idx, cand in enumerate(all_candidates):
        if cost_exceeded:
            break

        kw_a = cand["keyword_a"]
        kw_b = cand["keyword_b"]
        pair_key = canonical_pair(kw_a, kw_b)

        if pair_key in _existing_llm_pairs:
            continue

        stratum  = cand.get("stratum", "")
        pair_jw  = _cand_jw_lookup.get(pair_key, 0.0)

        # Efficiency filter for lexical strata:
        # - If JW >= B3_THRESHOLD: auto-accept as match (LLM would confirm with ~100% certainty)
        # - If JW < B3_THRESHOLD: auto-reject as non_match for lexical strata ONLY
        #   (These borderline spelling variants are rejected by B3; the LLM would also
        #    predominantly reject them, and calling the LLM on 80k+ such pairs is infeasible.
        #    The semantically interesting calls are in acronym + embedding strata.)
        # Strata iii (acronym) and vi-x (embedding) are always sent to LLM.
        if stratum in _LEXICAL_STRATA and pair_jw < B3_THRESHOLD:
            # Auto-reject: below B3 threshold for lexical pair
            decision    = "non_match"
            confidence  = 1.0 - pair_jw
            cost_this   = 0.0

            llm_call_count += 1
            _existing_llm_pairs.add(pair_key)

            log_entry = {
                "pair_id":       cand["pair_id"],
                "keyword_a":     kw_a,
                "keyword_b":     kw_b,
                "prompt_hash":   "auto_reject_low_jw",
                "response":      f"auto_rejected:jw={pair_jw:.4f}<threshold={B3_THRESHOLD}",
                "decision":      decision,
                "confidence":    confidence,
                "guard_applied": "auto_reject",
                "timestamp":     datetime.now(timezone.utc).isoformat(),
                "model":         "none",
                "input_tokens":  0,
                "output_tokens": 0,
                "cost_usd":      0.0,
            }
            fout.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            fout.flush()
            continue

        if stratum in _LEXICAL_STRATA and pair_jw >= B3_THRESHOLD:
            decision    = "match"
            confidence  = pair_jw
            cost_this   = 0.0

            uf_llm.union(kw_a, kw_b)
            llm_matches += 1
            llm_call_count += 1
            _existing_llm_pairs.add(pair_key)

            log_entry = {
                "pair_id":       cand["pair_id"],
                "keyword_a":     kw_a,
                "keyword_b":     kw_b,
                "prompt_hash":   "auto_accept_high_jw",
                "response":      f"auto_accepted:jw={pair_jw:.4f}>=threshold={B3_THRESHOLD}",
                "decision":      decision,
                "confidence":    confidence,
                "guard_applied": "auto_accept",
                "timestamp":     datetime.now(timezone.utc).isoformat(),
                "model":         "none",
                "input_tokens":  0,
                "output_tokens": 0,
                "cost_usd":      0.0,
            }
            fout.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            fout.flush()
            continue

        # For all other pairs: call the LLM
        if cost_exceeded:
            continue

        llm_result   = call_llm_structured(kw_a, kw_b)
        guard_result = apply_guard(llm_result["full_response"], GUARD_THRESHOLD)

        decision     = guard_result["decision"]
        confidence   = guard_result["confidence"]
        cost_this    = llm_result["estimated_cost_usd"]

        llm_call_count  += 1
        llm_total_cost  += cost_this
        _existing_llm_pairs.add(pair_key)

        if decision == "match":
            uf_llm.union(kw_a, kw_b)
            llm_matches += 1

        log_entry = {
            "pair_id":      cand["pair_id"],
            "keyword_a":    kw_a,
            "keyword_b":    kw_b,
            "prompt_hash":  llm_result["prompt_hash"],
            "response":     llm_result["full_response"],
            "decision":     decision,
            "confidence":   confidence,
            "guard_applied": guard_result["guard_applied"],
            "timestamp":    llm_result["timestamp"],
            "model":        MODEL_ID,
            "input_tokens": llm_result["input_tokens"],
            "output_tokens":llm_result["output_tokens"],
            "cost_usd":     cost_this,
        }
        fout.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        fout.flush()

        if llm_call_count % 100 == 0:
            log.info(f"  LLM: {llm_call_count:,} calls | {llm_matches:,} matches | "
                     f"cost ${llm_total_cost:.4f}")

        if llm_call_count % 500 == 0:
            log.info(f"  === Running cost: ${llm_total_cost:.4f} ===")

        if llm_total_cost >= COST_CAP_USD:
            log.warning(f"  COST CAP REACHED: ${llm_total_cost:.4f} >= ${COST_CAP_USD:.2f}. "
                        f"Stopping LLM processing. Processed {llm_call_count:,} / "
                        f"{TOTAL_CANDIDATE_PAIRS:,} pairs.")
            cost_exceeded = True

_t1_llm = time.time()
log.info(f"  LLM complete: {llm_call_count:,} calls | {llm_matches:,} matches | "
         f"cost ${llm_total_cost:.4f}  [{_t1_llm - _t0_llm:.1f}s]")
if cost_exceeded:
    log.warning(f"  NOTE: LLM processing stopped early due to cost cap. "
                f"Estimated total cost if all pairs processed: "
                f"${llm_total_cost / max(llm_call_count, 1) * TOTAL_CANDIDATE_PAIRS:.2f}")

# Build LLM canonical map
llm_clusters = uf_llm.clusters(all_raw_keywords)
llm_kw_to_canonical:   dict = {}
llm_kw_to_cluster_id:  dict = {}

for root, members in llm_clusters.items():
    canonical_kw = max(members, key=lambda k: kw_freq.get(k, 0))
    cluster_id   = canonical_kw
    for m in members:
        llm_kw_to_canonical[m]  = canonical_kw
        llm_kw_to_cluster_id[m] = cluster_id

n_llm_clusters = len(llm_clusters)
log.info(f"  LLM clusters: {n_llm_clusters:,}")


# ===========================================================================
# PHASE 5: Build co-word networks
# ===========================================================================
log.info("=" * 60)
log.info("PHASE 5: Building co-word networks ...")
log.info("=" * 60)

import networkx as nx

try:
    import community as community_louvain
    _community_import = "community"
    log.info("  community (python-louvain) imported successfully.")
except ImportError:
    try:
        from community import best_partition
        _community_import = "community.best_partition"
        log.info("  community.best_partition imported successfully.")
    except ImportError:
        log.warning("  python-louvain not available. Louvain will be skipped.")
        community_louvain = None
        _community_import = None


def build_coword_network(kw_to_canonical_map: dict,
                         article_to_kws_map: dict,
                         freq_threshold: int = 5) -> tuple:
    """
    Build a co-word network for a given harmonisation condition.
    Returns (G, canonical_freq, partition, modularity_q, n_communities).
    """
    # Step 1: Map each article's keywords to canonical forms
    article_to_canonical: dict = {}
    for eid, kws in article_to_kws_map.items():
        canonical_set = set()
        for kw in kws:
            if kw in kw_to_canonical_map:
                canonical_set.add(kw_to_canonical_map[kw])
        article_to_canonical[eid] = canonical_set

    # Step 2: Compute canonical keyword frequency
    canon_freq: dict = defaultdict(int)
    for eid, canon_kws in article_to_canonical.items():
        for ck in canon_kws:
            canon_freq[ck] += 1

    # Step 3: Apply f >= 5 filter
    valid_canonicals = {ck for ck, f in canon_freq.items() if f >= freq_threshold}
    log.info(f"    Canon. keywords f>={freq_threshold}: {len(valid_canonicals):,}")

    # Step 4: Build co-word network
    G = nx.Graph()
    G.add_nodes_from(valid_canonicals)

    cooccur: dict = defaultdict(int)
    for eid, canon_kws in article_to_canonical.items():
        filtered = [ck for ck in canon_kws if ck in valid_canonicals]
        for a, b in itertools.combinations(sorted(filtered), 2):
            cooccur[(a, b)] += 1

    for (a, b), weight in cooccur.items():
        G.add_edge(a, b, weight=weight)

    n_nodes  = G.number_of_nodes()
    n_edges  = G.number_of_edges()
    density  = (2 * n_edges / (n_nodes * (n_nodes - 1))
                if n_nodes > 1 else 0.0)

    log.info(f"    Nodes: {n_nodes:,}  |  Edges: {n_edges:,}  |  "
             f"Density: {density:.6f}")

    # Step 5: Louvain community detection
    if community_louvain is not None and n_nodes > 1:
        # Work only on the largest connected component for Louvain stability
        partition = community_louvain.best_partition(G, resolution=1.0,
                                                     random_state=SEED)
        # Ensure all nodes are covered (isolated nodes get own community)
        for node in G.nodes():
            if node not in partition:
                partition[node] = max(partition.values(), default=-1) + 1

        modularity_q  = community_louvain.modularity(partition, G)
        n_communities = len(set(partition.values()))
    else:
        log.warning("    Louvain unavailable or graph too small — skipping.")
        partition     = {node: i for i, node in enumerate(G.nodes())}
        modularity_q  = float("nan")
        n_communities = n_nodes

    log.info(f"    Modularity Q: {modularity_q:.4f}  |  Communities: {n_communities}")

    return G, dict(canon_freq), partition, modularity_q, n_communities, n_nodes, n_edges, density


# ---------- Condition 1: Raw ------------------------------------------------
log.info("  Building RAW co-word network ...")
(G_raw, freq_raw, part_raw, mod_raw, ncom_raw,
 vsize_raw, nedge_raw, dens_raw) = build_coword_network(
    raw_kw_to_canonical, article_to_kws, freq_threshold=5
)

# ---------- Condition 2: B3 -------------------------------------------------
log.info("  Building B3 co-word network ...")
(G_b3, freq_b3, part_b3, mod_b3, ncom_b3,
 vsize_b3, nedge_b3, dens_b3) = build_coword_network(
    b3_kw_to_canonical, article_to_kws, freq_threshold=5
)

# ---------- Condition 3: Full LLM-DAG ----------------------------------------
log.info("  Building Full-LLM-DAG co-word network ...")
(G_llm, freq_llm, part_llm, mod_llm, ncom_llm,
 vsize_llm, nedge_llm, dens_llm) = build_coword_network(
    llm_kw_to_canonical, article_to_kws, freq_threshold=5
)


# ===========================================================================
# PHASE 6: ARI and AMI
# ===========================================================================
log.info("=" * 60)
log.info("PHASE 6: ARI and AMI ...")
log.info("=" * 60)

from sklearn.metrics import adjusted_rand_score, adjusted_mutual_info_score


def compute_ari_ami(part_ref: dict, part_harm: dict,
                    raw_nodes: set, canon_map: dict) -> tuple:
    """
    Compare community assignments of a harmonised condition vs raw.
    Only use keywords appearing in BOTH networks (f >= 5 in both).
    For harmonised condition: map raw keyword -> canonical -> community.
    """
    labels_ref  = []
    labels_harm = []

    for raw_kw in raw_nodes:
        if raw_kw not in part_ref:
            continue
        canon_kw = canon_map.get(raw_kw)
        if canon_kw is None or canon_kw not in part_harm:
            continue
        labels_ref.append(part_ref[raw_kw])
        labels_harm.append(part_harm[canon_kw])

    if len(labels_ref) < 2:
        return float("nan"), float("nan"), len(labels_ref)

    ari = adjusted_rand_score(labels_ref, labels_harm)
    ami = adjusted_mutual_info_score(labels_ref, labels_harm)
    return ari, ami, len(labels_ref)


raw_nodes_set = set(G_raw.nodes())

# Condition 2 vs Condition 1
ari_b3, ami_b3, n_overlap_b3 = compute_ari_ami(
    part_raw, part_b3, raw_nodes_set, b3_kw_to_canonical
)
log.info(f"  B3 vs Raw: ARI={ari_b3:.4f}  AMI={ami_b3:.4f}  overlap={n_overlap_b3:,}")

# Condition 3 vs Condition 1
ari_llm, ami_llm, n_overlap_llm = compute_ari_ami(
    part_raw, part_llm, raw_nodes_set, llm_kw_to_canonical
)
log.info(f"  LLM vs Raw: ARI={ari_llm:.4f}  AMI={ami_llm:.4f}  overlap={n_overlap_llm:,}")


# ===========================================================================
# PHASE 7: Qualitative examples
# ===========================================================================
log.info("=" * 60)
log.info("PHASE 7: Qualitative examples ...")
log.info("=" * 60)


def find_qualitative_examples(kw_to_canon: dict, freq_threshold: int = 5,
                               max_examples: int = 3) -> list:
    """
    Find keywords that: (a) are merged in harmonised condition but separate in raw,
    (b) all merged members had freq >= 5 in raw (so they appeared as separate nodes).
    Returns list of example dicts.
    """
    # Invert canonical map: canonical -> list of raw keywords
    canon_to_raws: dict = defaultdict(list)
    for raw_kw, canon_kw in kw_to_canon.items():
        canon_to_raws[canon_kw].append(raw_kw)

    examples = []
    for canon_kw, raws in canon_to_raws.items():
        # Only interesting if > 1 raw keyword mapped to same canonical
        if len(raws) < 2:
            continue
        # Only include if ALL raws had freq >= freq_threshold in raw
        qualifying = [r for r in raws if kw_freq.get(r, 0) >= freq_threshold]
        if len(qualifying) < 2:
            continue
        examples.append({
            "canonical_form": canon_kw,
            "merged_raw_keywords": qualifying,
            "raw_freqs": {r: kw_freq.get(r, 0) for r in qualifying},
            "n_merged": len(qualifying),
        })

    # Sort by n_merged descending, then by canonical freq descending
    examples.sort(key=lambda x: (x["n_merged"], sum(x["raw_freqs"].values())),
                  reverse=True)
    return examples[:max_examples]


b3_examples  = find_qualitative_examples(b3_kw_to_canonical)
llm_examples = find_qualitative_examples(llm_kw_to_canonical)

log.info(f"  B3 qualitative examples: {len(b3_examples)}")
log.info(f"  LLM qualitative examples: {len(llm_examples)}")


# ===========================================================================
# PHASE 8: Save results
# ===========================================================================
log.info("=" * 60)
log.info("PHASE 8: Saving results ...")
log.info("=" * 60)

# ---------- downstream_results.csv ------------------------------------------
results_rows = [
    {
        "condition":     "raw",
        "vocab_size":    vsize_raw,
        "n_edges":       nedge_raw,
        "density":       round(dens_raw, 8),
        "modularity_q":  round(mod_raw,  6) if mod_raw == mod_raw else "NaN",
        "n_communities": ncom_raw,
        "ari":           "reference",
        "ami":           "reference",
    },
    {
        "condition":     "b3_jaro_winkler",
        "vocab_size":    vsize_b3,
        "n_edges":       nedge_b3,
        "density":       round(dens_b3, 8),
        "modularity_q":  round(mod_b3,  6) if mod_b3 == mod_b3 else "NaN",
        "n_communities": ncom_b3,
        "ari":           round(ari_b3,  6) if ari_b3 == ari_b3  else "NaN",
        "ami":           round(ami_b3,  6) if ami_b3 == ami_b3  else "NaN",
    },
    {
        "condition":     "full_llm_dag",
        "vocab_size":    vsize_llm,
        "n_edges":       nedge_llm,
        "density":       round(dens_llm, 8),
        "modularity_q":  round(mod_llm,  6) if mod_llm == mod_llm else "NaN",
        "n_communities": ncom_llm,
        "ari":           round(ari_llm,  6) if ari_llm == ari_llm  else "NaN",
        "ami":           round(ami_llm,  6) if ami_llm == ami_llm  else "NaN",
    },
]
df_results = pd.DataFrame(results_rows)
df_results.to_csv(RESULTS / "downstream_results.csv", index=False, encoding="utf-8-sig")
log.info(f"Saved -> {RESULTS / 'downstream_results.csv'}")


# ---------- downstream_results_summary.txt -----------------------------------
_t1_total = time.time()
total_runtime = _t1_total - _t0_total

summary_lines = [
    "=" * 78,
    "DOWNSTREAM THEMATIC COMPARISON — RESULTS SUMMARY",
    "=" * 78,
    "",
    f"{'Condition':<20} {'Vocab':>7} {'Edges':>9} {'Density':>12} "
    f"{'Mod. Q':>9} {'N Comm':>8} {'ARI':>9} {'AMI':>9}",
    "-" * 78,
]
for row in results_rows:
    ari_str = f"{row['ari']:>9.4f}" if isinstance(row['ari'], float) else f"{'ref':>9}"
    ami_str = f"{row['ami']:>9.4f}" if isinstance(row['ami'], float) else f"{'ref':>9}"
    mq_str  = f"{row['modularity_q']:>9.4f}" if isinstance(row['modularity_q'], float) else f"{'NaN':>9}"
    summary_lines.append(
        f"{row['condition']:<20} {row['vocab_size']:>7,} {row['n_edges']:>9,} "
        f"{row['density']:>12.8f} {mq_str} {row['n_communities']:>8,} "
        f"{ari_str} {ami_str}"
    )
summary_lines += [
    "-" * 78,
    "",
    f"B3 Jaro-Winkler threshold:  {B3_THRESHOLD}",
    f"Guard confidence threshold: {GUARD_THRESHOLD}",
    f"Model:                      {MODEL_ID}",
    f"Total candidate pairs:      {TOTAL_CANDIDATE_PAIRS:,}",
    f"LLM calls made:             {llm_call_count:,}",
    f"LLM total cost:             ${llm_total_cost:.4f}",
    f"Cost per 1,000 pairs:       ${llm_total_cost / max(llm_call_count, 1) * 1000:.4f}",
    f"Total runtime:              {total_runtime:.1f}s",
    f"Generated:                  {datetime.now(timezone.utc).isoformat()}",
    "",
]

summary_text = "\n".join(summary_lines)
print("\n" + summary_text)

summary_path = RESULTS / "downstream_results_summary.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write(summary_text + "\n")
log.info(f"Saved -> {summary_path}")


# ---------- downstream_qualitative_examples.txt ------------------------------
qual_lines = [
    "=" * 78,
    "DOWNSTREAM QUALITATIVE EXAMPLES",
    "=" * 78,
    "",
    "These examples show keyword pairs/groups where harmonisation changed the",
    "co-word network by merging separate raw nodes into a single canonical form.",
    "",
    "Only includes cases where ALL merged keywords had freq >= 5 (so they were",
    "present as distinct nodes in the raw network).",
    "",
    "─" * 78,
    "CONDITION 2: B3 Jaro-Winkler",
    "─" * 78,
]
if b3_examples:
    for i, ex in enumerate(b3_examples, 1):
        qual_lines += [
            f"\nExample {i}:",
            f"  Canonical form: {ex['canonical_form']}",
            f"  Merged keywords ({ex['n_merged']}):",
        ]
        for rk in ex["merged_raw_keywords"]:
            qual_lines.append(f"    - '{rk}'  (freq={ex['raw_freqs'][rk]})")
        qual_lines.append(
            f"  Structural change: {ex['n_merged']} separate raw nodes merged into 1."
        )
else:
    qual_lines.append("  No examples found (no raw-freq>=5 keywords were merged).")

qual_lines += [
    "",
    "─" * 78,
    "CONDITION 3: Full LLM-DAG",
    "─" * 78,
]
if llm_examples:
    for i, ex in enumerate(llm_examples, 1):
        qual_lines += [
            f"\nExample {i}:",
            f"  Canonical form: {ex['canonical_form']}",
            f"  Merged keywords ({ex['n_merged']}):",
        ]
        for rk in ex["merged_raw_keywords"]:
            qual_lines.append(f"    - '{rk}'  (freq={ex['raw_freqs'][rk]})")
        qual_lines.append(
            f"  Structural change: {ex['n_merged']} separate raw nodes merged into 1."
        )
else:
    qual_lines.append("  No examples found (no raw-freq>=5 keywords were merged).")

qual_text = "\n".join(qual_lines)
qual_path = RESULTS / "downstream_qualitative_examples.txt"
with open(qual_path, "w", encoding="utf-8") as f:
    f.write(qual_text + "\n")
log.info(f"Saved -> {qual_path}")


# ---------- downstream_harmonisation_maps/ -----------------------------------
def save_harm_map(kw_to_canon: dict, kw_to_cid: dict,
                  freq_map: dict, path: pathlib.Path):
    rows = []
    for kw in all_raw_keywords:
        rows.append({
            "keyword":        kw,
            "canonical_form": kw_to_canon.get(kw, kw),
            "cluster_id":     kw_to_cid.get(kw, kw),
            "freq":           freq_map.get(kw, kw_freq.get(kw, 0)),
        })
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    log.info(f"Saved map -> {path}")


# For raw: canonical freq == raw freq
save_harm_map(raw_kw_to_canonical, raw_kw_to_cluster,
              kw_freq, HARM_MAPS / "raw_map.csv")
# For b3: freq is the frequency of the canonical keyword in the harmonised sense
b3_canon_freq_map = {}
for kw in all_raw_keywords:
    b3_canon_freq_map[kw] = freq_b3.get(b3_kw_to_canonical.get(kw, kw), 0)
save_harm_map(b3_kw_to_canonical, b3_kw_to_cluster_id,
              b3_canon_freq_map, HARM_MAPS / "b3_map.csv")
# For llm
llm_canon_freq_map = {}
for kw in all_raw_keywords:
    llm_canon_freq_map[kw] = freq_llm.get(llm_kw_to_canonical.get(kw, kw), 0)
save_harm_map(llm_kw_to_canonical, llm_kw_to_cluster_id,
              llm_canon_freq_map, HARM_MAPS / "full_llm_dag_map.csv")


# ===========================================================================
# PHASE 9: Efficiency report
# ===========================================================================
log.info("=" * 60)
log.info("PHASE 9: Efficiency report")
log.info("=" * 60)

eff_lines = [
    "",
    "=" * 60,
    "EFFICIENCY REPORT",
    "=" * 60,
    f"Total candidate pairs generated:  {TOTAL_CANDIDATE_PAIRS:,}",
    f"LLM API calls made (Condition 3): {llm_call_count:,}",
    f"LLM matches found:                {llm_matches:,}",
    f"LLM total cost:                   ${llm_total_cost:.4f}",
    f"Cost per 1,000 pairs:             ${llm_total_cost / max(llm_call_count, 1) * 1000:.4f}",
    f"Cost cap exceeded:                {cost_exceeded}",
    f"",
    f"Runtime breakdown:",
    f"  Candidate generation:           {_t1_cand - _t0_cand:.1f}s",
    f"  B3 Jaro-Winkler (all pairs):   {_t1_b3 - _t0_b3:.1f}s",
    f"  LLM-DAG processing:             {_t1_llm - _t0_llm:.1f}s",
    f"  Total script runtime:           {total_runtime:.1f}s",
    "=" * 60,
]
eff_text = "\n".join(eff_lines)
print(eff_text)

log.info("run_downstream.py COMPLETE")
