"""
generate_benchmark_candidates.py
---------------------------------
Generates candidate keyword pairs for gold-standard benchmark annotation.
Applies three retrieval strategies (lexical, acronym, embedding) across
10 difficulty strata (i–x).

Does NOT label pairs — all output is for human annotation only.

Outputs:
  data/benchmark/candidate_pairs.csv
  data/benchmark/candidate_pairs_summary.txt
  data/benchmark/annotation_sheet.csv
"""

import io
import itertools
import logging
import pathlib
import random
import re
import sys
import unicodedata
from collections import defaultdict

import jellyfish
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# UTF-8 stdout (required on Windows terminals)
# ---------------------------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

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
ROOT    = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
DERIVED = ROOT / "data" / "derived"
BENCH   = ROOT / "data" / "benchmark"
BENCH.mkdir(parents=True, exist_ok=True)

AK_FREQ_FILE = DERIVED / "author_keyword_frequencies.csv"

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ---------------------------------------------------------------------------
# Stratum targets
# ---------------------------------------------------------------------------
STRATUM_TARGETS = {
    "i":    40,   # capitalisation / whitespace variants
    "ii":   45,   # spelling variants (Jaro-Winkler)
    "iii":  55,   # acronym expansion
    "iv":   40,   # punctuation / hyphenation variants
    "v":    35,   # singular / plural
    "vi":   75,   # near-synonyms  (embedding cosine [0.75, 0.85))
    "vii":  75,   # broader-narrower proxies (embedding cosine [0.60, 0.75))
    "viii": 60,   # ambiguous short forms
    "ix":   35,   # malformed / encoding-artefact strings
    "x":    40,   # weak semantic links (embedding cosine [0.50, 0.60))
}

STRATUM_DESC = {
    "i":    "Capitalisation / whitespace variants",
    "ii":   "Spelling variants (Jaro-Winkler [0.85,0.95))",
    "iii":  "Acronym expansion",
    "iv":   "Punctuation / hyphenation variants",
    "v":    "Singular / plural",
    "vi":   "Near-synonyms (embedding [0.75,0.85))",
    "vii":  "Broader-narrower proxies (embedding [0.60,0.75))",
    "viii": "Ambiguous short forms + embedding",
    "ix":   "Malformed / encoding-artefact strings",
    "x":    "Weak semantic links (embedding [0.50,0.60))",
}


# ===========================================================================
# SECTION 1  —  Load and normalise
# ===========================================================================

def nfkc_norm(s: str) -> str:
    """Lowercase + Unicode NFKC + strip + collapse whitespace."""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


log.info("Loading author keyword frequencies ...")
df_freq = pd.read_csv(AK_FREQ_FILE, encoding="utf-8-sig")
df_freq.columns = ["keyword", "frequency"]
df_freq = df_freq.dropna(subset=["keyword"]).copy()
df_freq["keyword"]   = df_freq["keyword"].astype(str).str.strip()
df_freq["frequency"] = df_freq["frequency"].astype(int)
df_freq["norm"]      = df_freq["keyword"].apply(nfkc_norm)
df_freq = df_freq.reset_index(drop=True)

kw_list   = df_freq["keyword"].tolist()
norm_list = df_freq["norm"].tolist()
freq_list = df_freq["frequency"].tolist()
kw_to_freq = dict(zip(kw_list, freq_list))

log.info(f"Loaded {len(kw_list):,} unique author keywords")


# ===========================================================================
# SECTION 2  —  Pair registry (deduplication across strata)
# ===========================================================================

seen_pairs: set = set()
all_candidates: list = []
_pair_ctr = 0


def canonical(a: str, b: str) -> tuple:
    return (a, b) if a <= b else (b, a)


def add_pair(kw_a: str, kw_b: str, stratum: str, method: str, score: float) -> bool:
    """Register a pair if not already seen. Returns True if newly added."""
    global _pair_ctr
    key = canonical(kw_a, kw_b)
    if key in seen_pairs:
        return False
    seen_pairs.add(key)
    _pair_ctr += 1
    all_candidates.append({
        "pair_id":          f"RAW{_pair_ctr:06d}",
        "keyword_a":        kw_a,
        "keyword_b":        kw_b,
        "freq_a":           kw_to_freq.get(kw_a, 0),
        "freq_b":           kw_to_freq.get(kw_b, 0),
        "stratum":          stratum,
        "retrieval_method": method,
        "similarity_score": round(float(score), 4),
    })
    return True


def count_stratum(s: str) -> int:
    return sum(1 for c in all_candidates if c["stratum"] == s)


# ===========================================================================
# SECTION 3A  —  Lexical blocking
# ===========================================================================

# ── Stratum i: capitalisation / whitespace variants ─────────────────────────
log.info("Stratum i: capitalisation / whitespace variants ...")

norm_to_kws: dict = defaultdict(list)
for kw, norm in zip(kw_list, norm_list):
    norm_to_kws[norm].append(kw)

for norm, group in norm_to_kws.items():
    if len(group) < 2:
        continue
    for a, b in itertools.combinations(group, 2):
        add_pair(a, b, "i", "capitalisation_whitespace", 1.0)

log.info(f"  -> {count_stratum('i'):,} candidates")


# ── Stratum ii: spelling variants (Jaro-Winkler [0.85, 0.95)) ───────────────
log.info("Stratum ii: spelling variants via Jaro-Winkler ...")

# Only keywords with freq >= 2; block by first 3 chars of normalised form
# to keep comparisons tractable (full pairwise over 12k would be ~75M calls)
freq2 = [(kw, norm) for kw, norm, freq in zip(kw_list, norm_list, freq_list)
          if freq >= 2 and len(norm) >= 4]

log.info(f"  Freq>=2 keyword pool: {len(freq2):,}")

prefix3_blocks: dict = defaultdict(list)
for kw, norm in freq2:
    prefix3_blocks[norm[:3]].append((kw, norm))

for prefix, block in prefix3_blocks.items():
    if len(block) < 2:
        continue
    for (a_kw, a_norm), (b_kw, b_norm) in itertools.combinations(block, 2):
        if canonical(a_kw, b_kw) in seen_pairs:
            continue
        la, lb = len(a_norm), len(b_norm)
        # JW >= 0.85 requires roughly similar lengths
        if la == 0 or lb == 0 or min(la, lb) / max(la, lb) < 0.60:
            continue
        jw = jellyfish.jaro_winkler_similarity(a_norm, b_norm)
        if 0.85 <= jw < 0.95:
            add_pair(a_kw, b_kw, "ii", "jaro_winkler", jw)

log.info(f"  -> {count_stratum('ii'):,} candidates")


# ── Stratum iv: punctuation / hyphenation variants ──────────────────────────
log.info("Stratum iv: punctuation / hyphenation variants ...")

_PUNCT_RE = re.compile(r"[-/(). ]")


def strip_punct(s: str) -> str:
    return _PUNCT_RE.sub("", s)


punct_norm_to_kws: dict = defaultdict(list)
for kw, norm in zip(kw_list, norm_list):
    pn = strip_punct(norm)
    if len(pn) >= 3:
        punct_norm_to_kws[pn].append(kw)

for pn, group in punct_norm_to_kws.items():
    if len(group) < 2:
        continue
    for a, b in itertools.combinations(group, 2):
        add_pair(a, b, "iv", "punctuation_hyphenation", 0.95)

log.info(f"  -> {count_stratum('iv'):,} candidates")


# ── Stratum v: singular / plural ────────────────────────────────────────────
log.info("Stratum v: singular / plural ...")

# Build a norm -> first keyword map (one representative per normalised form)
norm_to_first: dict = {}
for kw, norm in zip(kw_list, norm_list):
    if norm not in norm_to_first:
        norm_to_first[norm] = kw

for norm_a, kw_a in norm_to_first.items():
    # +s
    nb = norm_a + "s"
    if nb in norm_to_first and nb != norm_a:
        add_pair(kw_a, norm_to_first[nb], "v", "singular_plural_s", 0.90)
    # +es
    nb = norm_a + "es"
    if nb in norm_to_first and nb != norm_a:
        add_pair(kw_a, norm_to_first[nb], "v", "singular_plural_es", 0.90)
    # ies <-> y
    if norm_a.endswith("ies") and len(norm_a) > 4:
        nb = norm_a[:-3] + "y"
        if nb in norm_to_first:
            add_pair(kw_a, norm_to_first[nb], "v", "singular_plural_ies_y", 0.90)

log.info(f"  -> {count_stratum('v'):,} candidates")


# ── Stratum ix: malformed / encoding-artefact strings ───────────────────────
log.info("Stratum ix: malformed / encoding-artefact strings ...")

_ARTEFACT_RE = re.compile(
    r"â€|Ã[^A-Z]|Ã©|â€™|â€œ|Â©|â„¢|\\u[0-9a-fA-F]{4}|&#[0-9]+;",
    re.IGNORECASE
)
_EXCESS_PUNCT_RE = re.compile(r"[^\w\s]{3,}")


def is_malformed(kw: str) -> bool:
    if len(kw.strip()) < 3:
        return True
    if _ARTEFACT_RE.search(kw):
        return True
    if _EXCESS_PUNCT_RE.search(kw):
        return True
    return False


malformed_kws = [(kw, nfkc_norm(kw)) for kw in kw_list if is_malformed(kw)]
log.info(f"  Malformed keywords identified: {len(malformed_kws)}")

# For each malformed keyword find its closest non-malformed, freq>=2 JW neighbour
good_pool = [(kw, norm) for kw, norm, freq in zip(kw_list, norm_list, freq_list)
              if freq >= 2 and not is_malformed(kw)]

for mal_kw, mal_norm in malformed_kws[:600]:   # cap to keep runtime reasonable
    if len(mal_norm) < 2:
        continue
    best_score, best_kw = 0.0, None
    # Block by first two chars to limit comparisons
    prefix2 = mal_norm[:2]
    candidates_pool = [(kw, norm) for kw, norm in good_pool
                        if norm[:2] == prefix2]
    if not candidates_pool:
        candidates_pool = good_pool[:300]       # fallback: head of sorted list
    for cand_kw, cand_norm in candidates_pool[:300]:
        jw = jellyfish.jaro_winkler_similarity(mal_norm, cand_norm)
        if jw > best_score:
            best_score, best_kw = jw, cand_kw
    if best_kw and best_score > 0.70:
        add_pair(mal_kw, best_kw, "ix", "malformed_jw_nearest", best_score)

log.info(f"  -> {count_stratum('ix'):,} candidates")


# ===========================================================================
# SECTION 3B  —  Acronym detection (stratum iii)
# ===========================================================================

log.info("Stratum iii: acronym expansion ...")

ACRONYM_RE = re.compile(r"^[A-Z]{2,6}$")
PAREN_ACRO_RE = re.compile(r"\(([A-Za-z]{2,6})\)")

# Identify acronym keywords
acronym_kws = [(kw, kw.strip().upper()) for kw in kw_list
               if ACRONYM_RE.match(kw.strip())]
log.info(f"  Candidate acronym keywords: {len(acronym_kws)}")

# Pre-build two indices over all long keywords:
# 1. parenthetical index:  acronym_string -> [long_kw, ...]
# 2. initials index:       initials_string -> [long_kw, ...]

paren_index: dict = defaultdict(list)
initials_index: dict = defaultdict(list)

_SPLIT_RE = re.compile(r"[\s\-/]+")

for kw in kw_list:
    # parenthetical
    for m in PAREN_ACRO_RE.finditer(kw):
        paren_index[m.group(1).upper()].append(kw)
    # initials (only for multi-word keywords)
    words = [w for w in _SPLIT_RE.split(kw.strip()) if w]
    if len(words) >= 2:
        initials = "".join(w[0].upper() for w in words if w)
        if 2 <= len(initials) <= 6:
            initials_index[initials].append(kw)

for acro_kw, acro_upper in acronym_kws:
    matched_expansions = set()
    # parenthetical matches
    for long_kw in paren_index.get(acro_upper, []):
        if long_kw != acro_kw and len(long_kw) > len(acro_kw):
            matched_expansions.add(long_kw)
    # initial-letter matches
    for long_kw in initials_index.get(acro_upper, []):
        if long_kw != acro_kw and len(long_kw) > len(acro_kw):
            matched_expansions.add(long_kw)
    for long_kw in matched_expansions:
        add_pair(acro_kw, long_kw, "iii", "acronym_expansion", 0.95)

log.info(f"  -> {count_stratum('iii'):,} candidates")


# ===========================================================================
# SECTION 3C  —  Embedding-based retrieval (strata vi, vii, viii, x)
# ===========================================================================

log.info("Loading sentence-transformers (all-MiniLM-L6-v2) ...")

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.neighbors import NearestNeighbors

    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Encode only keywords with freq >= 2
    emb_rows = [(kw, norm) for kw, norm, freq in zip(kw_list, norm_list, freq_list)
                 if freq >= 2]
    emb_kws   = [r[0] for r in emb_rows]
    emb_norms = [r[1] for r in emb_rows]

    # Identify ambiguous short forms (stratum viii): 2-4 chars, lowercase, not acronym
    short_ambig = {kw for kw, norm in emb_rows
                   if 2 <= len(norm) <= 4 and norm.islower()
                   and not ACRONYM_RE.match(kw.strip())}
    log.info(f"  Ambiguous short-form keywords: {len(short_ambig)}")

    log.info(f"  Encoding {len(emb_kws):,} keywords (freq >= 2) ...")
    embeddings = model.encode(
        emb_norms,
        batch_size=256,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,   # L2-normalise -> cosine via dot product
    )
    log.info("  Encoding complete.")

    # NearestNeighbors — cosine distance = 1 - cosine_similarity for L2-norm vecs
    # Request 8 neighbours (first is self, discarded)
    N_NEIGHBORS = 8
    log.info("  Fitting NearestNeighbors index ...")
    nn = NearestNeighbors(
        n_neighbors=N_NEIGHBORS,
        metric="cosine",
        algorithm="brute",
        n_jobs=-1,
    )
    nn.fit(embeddings)
    log.info("  Running kneighbors query ...")
    distances, indices = nn.kneighbors(embeddings)
    log.info("  kneighbors complete.")

    # Assign stratum by similarity range and whether keyword is a short form
    def embedding_stratum(kw_a: str, sim: float) -> tuple[str, str]:
        if kw_a in short_ambig:
            return "viii", "embedding_short_ambig"
        if sim >= 0.75:
            return "vi",  "embedding_near_synonym"
        if sim >= 0.60:
            return "vii", "embedding_broader_narrower"
        return "x", "embedding_weak_semantic"

    TOP_K_STANDARD  = 5   # neighbours to consider per standard keyword
    TOP_K_SHORT     = 3   # neighbours to consider per short-form keyword

    for i, kw_a in enumerate(emb_kws):
        top_k = TOP_K_SHORT if kw_a in short_ambig else TOP_K_STANDARD
        for rank in range(1, min(top_k + 1, N_NEIGHBORS)):
            j    = indices[i][rank]
            dist = distances[i][rank]
            sim  = max(0.0, 1.0 - float(dist))   # guard against tiny negatives

            if sim < 0.50 or sim >= 0.85:
                continue

            kw_b = emb_kws[j]
            if canonical(kw_a, kw_b) in seen_pairs:
                continue

            stratum, method = embedding_stratum(kw_a, sim)
            add_pair(kw_a, kw_b, stratum, method, sim)

    log.info(f"  Stratum vi   -> {count_stratum('vi'):,} candidates")
    log.info(f"  Stratum vii  -> {count_stratum('vii'):,} candidates")
    log.info(f"  Stratum viii -> {count_stratum('viii'):,} candidates")
    log.info(f"  Stratum x    -> {count_stratum('x'):,} candidates")

except ImportError as exc:
    log.error(f"sentence-transformers unavailable: {exc}")
    log.error("Install: pip install sentence-transformers scikit-learn")
    log.error("Embedding strata (vi, vii, viii, x) will be empty.")


# ===========================================================================
# SECTION 4  —  Stratified sampling (seed=42)
# ===========================================================================

log.info("Stratified sampling ...")

df_all = pd.DataFrame(all_candidates)
log.info(f"Total candidate pairs (all strata): {len(df_all):,}")

sampled_rows = []
shortfalls   = {}

for stratum, target in STRATUM_TARGETS.items():
    pool = df_all[df_all["stratum"] == stratum].copy()
    n_avail = len(pool)

    if n_avail == 0:
        log.warning(f"  Stratum {stratum}: 0 candidates — SHORTFALL of {target}")
        shortfalls[stratum] = {"target": target, "available": 0, "shortfall": target}
        continue

    if n_avail < target:
        shortfall = target - n_avail
        log.warning(f"  Stratum {stratum}: {n_avail} available < {target} target "
                    f"— SHORTFALL of {shortfall}")
        shortfalls[stratum] = {"target": target, "available": n_avail, "shortfall": shortfall}
        sampled_rows.append(pool)
    else:
        sampled = pool.sample(n=target, random_state=SEED)
        log.info(f"  Stratum {stratum}: sampled {target:,} / {n_avail:,}")
        sampled_rows.append(sampled)

df_sample = (
    pd.concat(sampled_rows, ignore_index=True)
    .sort_values(["stratum", "keyword_a"])
    .reset_index(drop=True)
)
# Assign clean sequential pair IDs
df_sample["pair_id"] = [f"BP{i+1:04d}" for i in range(len(df_sample))]
df_sample = df_sample[["pair_id", "keyword_a", "keyword_b",
                         "freq_a", "freq_b", "stratum",
                         "retrieval_method", "similarity_score"]]

log.info(f"Total sampled pairs: {len(df_sample):,}")


# ===========================================================================
# SECTION 5  —  Save candidate_pairs.csv and summary
# ===========================================================================

pairs_path = BENCH / "candidate_pairs.csv"
df_sample.to_csv(pairs_path, index=False, encoding="utf-8-sig")
log.info(f"Saved candidate pairs -> {pairs_path}")

# Build summary text
summary_lines = [
    "=" * 72,
    "BENCHMARK CANDIDATE PAIRS — GENERATION SUMMARY",
    "=" * 72,
    f"Total candidate pairs generated (before sampling): {len(df_all):,}",
    f"Total pairs in final benchmark file:               {len(df_sample):,}",
    "",
    f"{'Stratum':<9} {'Description':<40} {'Target':>7} {'Avail':>7} {'Sampled':>8}",
    "-" * 72,
]

for stratum, target in STRATUM_TARGETS.items():
    n_avail   = len(df_all[df_all["stratum"] == stratum])
    n_sampled = len(df_sample[df_sample["stratum"] == stratum])
    flag = "  *** SHORTFALL ***" if stratum in shortfalls else ""
    summary_lines.append(
        f"{stratum:<9} {STRATUM_DESC[stratum]:<40} {target:>7} {n_avail:>7} {n_sampled:>8}{flag}"
    )

summary_lines += [
    "-" * 72,
    f"{'TOTAL':<9} {'':<40} {sum(STRATUM_TARGETS.values()):>7} {len(df_all):>7} {len(df_sample):>8}",
    "",
]

if shortfalls:
    summary_lines.append("SHORTFALL STRATA:")
    for s, info in shortfalls.items():
        summary_lines.append(
            f"  Stratum {s}: target={info['target']}, available={info['available']}, "
            f"shortfall={info['shortfall']}"
        )
    summary_lines.append("")
else:
    summary_lines.append("All stratum targets met — no shortfalls.")
    summary_lines.append("")

summary_lines += [
    "NOTES:",
    "  - Stratum vii (broader-narrower) uses embedding neighbours as proxies.",
    "    Annotators should flag pairs as 'uncertain' where the relationship is",
    "    hierarchical rather than synonymous.",
    "  - Random seed 42 used throughout for reproducibility.",
    "  - No labels have been assigned — all pairs require human annotation.",
    "  - Label schema: match | non-match | uncertain",
    "    See scope policy in annotation guide (docs/annotation_guide/).",
    "",
    "STRATUM RETRIEVAL METHODS:",
]
for s, desc in STRATUM_DESC.items():
    summary_lines.append(f"  {s}: {desc}")

summary_text = "\n".join(summary_lines)
print("\n" + summary_text + "\n")

summary_path = BENCH / "candidate_pairs_summary.txt"
summary_path.write_text(summary_text, encoding="utf-8")
log.info(f"Saved summary -> {summary_path}")


# ===========================================================================
# SECTION 6  —  Annotation spreadsheet
# ===========================================================================

log.info("Generating annotation spreadsheet ...")

instruction_row = pd.DataFrame([{
    "pair_id":           "INSTRUCTIONS",
    "keyword_a":         "Keyword A",
    "keyword_b":         "Keyword B",
    "freq_a":            "Corpus freq A",
    "freq_b":            "Corpus freq B",
    "stratum":           "Stratum",
    "label_annotator_1": (
        "Label each pair as: match / non-match / uncertain. "
        "Refer to the scope policy in Table 1."
    ),
    "label_annotator_2": "",
    "label_adjudicator": "",
    "notes":             "",
}])

df_annot = df_sample[["pair_id", "keyword_a", "keyword_b",
                        "freq_a", "freq_b", "stratum"]].copy()
df_annot["label_annotator_1"] = ""
df_annot["label_annotator_2"] = ""
df_annot["label_adjudicator"] = ""
df_annot["notes"]             = ""

df_annot_out = pd.concat([instruction_row, df_annot], ignore_index=True)
annot_path = BENCH / "annotation_sheet.csv"
df_annot_out.to_csv(annot_path, index=False, encoding="utf-8-sig")
log.info(f"Saved annotation sheet -> {annot_path}")

log.info("Done.")
