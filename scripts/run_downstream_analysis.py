"""
run_downstream_analysis.py
===========================
Produces downstream thematic comparison results from the current checkpoint
of results/llm_logs/downstream_raw_outputs.jsonl

This script is designed to be run after run_downstream.py has produced at
least partial LLM results. It reads the checkpoint and produces all
Phase 5-9 outputs (co-word networks, ARI/AMI, qualitative examples, reports).

Can be rerun as run_downstream.py accumulates more LLM results.
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
from collections import defaultdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# UTF-8 stdout
# ---------------------------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

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
import jellyfish

ROOT      = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
INTERIM   = ROOT / "data" / "interim"
RESULTS   = ROOT / "results"
LLM_LOGS  = RESULTS / "llm_logs"
CONFIGS   = ROOT / "configs"
HARM_MAPS = RESULTS / "downstream_harmonisation_maps"

RESULTS.mkdir(parents=True, exist_ok=True)
HARM_MAPS.mkdir(parents=True, exist_ok=True)

with open(CONFIGS / "model_config.yaml", encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f)
MODEL_ID = _cfg["model"]["model_id"]

with open(RESULTS / "tuned_thresholds.json", encoding="utf-8") as _f:
    _thresholds = json.load(_f)
B3_THRESHOLD    = _thresholds["b3_jaro_winkler"]["threshold"]
GUARD_THRESHOLD = _thresholds["guard_confidence_threshold"]["threshold"]

_t0 = time.time()

# ===========================================================================
# PHASE 1: Load corpus
# ===========================================================================
log.info("PHASE 1: Loading corpus ...")
df_corpus = pd.read_csv(INTERIM / "scopus_ce_merged_deduped.csv",
                         usecols=["EID", "Author Keywords"], encoding="utf-8")
AK_COL = "Author Keywords"

kw_to_articles: dict = defaultdict(set)
article_to_kws: dict = {}

for _, row in df_corpus.iterrows():
    eid     = str(row["EID"])
    ak_cell = row[AK_COL]
    if pd.isna(ak_cell) or str(ak_cell).strip() == "":
        article_to_kws[eid] = []
        continue
    kws = [kw.strip() for kw in str(ak_cell).split(";") if kw.strip()]
    article_to_kws[eid] = kws
    for kw in kws:
        kw_to_articles[kw].add(eid)

all_raw_keywords = list(kw_to_articles.keys())
kw_freq: dict = {kw: len(eids) for kw, eids in kw_to_articles.items()}
log.info(f"Corpus: {len(df_corpus):,} articles | {len(all_raw_keywords):,} unique keywords")


# ===========================================================================
# PHASE 2: Normalisation
# ===========================================================================
def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

raw_to_norm: dict = {kw: normalise(kw) for kw in all_raw_keywords}
log.info(f"Normalisation complete: {len(raw_to_norm):,} keywords")


# ===========================================================================
# PHASE 3: Candidate Generation (replicated from run_downstream.py)
# ===========================================================================
log.info("PHASE 3: Candidate generation ...")
_t0_cand = time.time()

kw_list   = all_raw_keywords
norm_list = [raw_to_norm[kw] for kw in kw_list]
freq_list = [kw_freq[kw]      for kw in kw_list]

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
        "stratum":          stratum,
        "retrieval_method": method,
        "similarity_score": round(float(score), 4),
    })
    return True


# A1: Stratum i
norm_to_kws_map: dict = defaultdict(list)
for kw, norm in zip(kw_list, norm_list):
    norm_to_kws_map[norm].append(kw)
for norm, group in norm_to_kws_map.items():
    if len(group) < 2:
        continue
    for a, b in itertools.combinations(group, 2):
        add_pair(a, b, "i", "capitalisation_whitespace", 1.0)
log.info(f"  Stratum i: {sum(1 for c in all_candidates if c['stratum']=='i'):,}")

# A2: Stratum ii
freq2 = [(kw, norm) for kw, norm, freq in zip(kw_list, norm_list, freq_list)
          if freq >= 2 and len(norm) >= 4]
prefix3_blocks: dict = defaultdict(list)
for kw, norm in freq2:
    prefix3_blocks[norm[:3]].append((kw, norm))
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
            add_pair(a_kw, b_kw, "ii", "jaro_winkler", jw)
log.info(f"  Stratum ii: {sum(1 for c in all_candidates if c['stratum']=='ii'):,}")

# A3: Stratum iv
_PUNCT_RE = re.compile(r"[-/(). ]")
punct_norm_map: dict = defaultdict(list)
for kw, norm in zip(kw_list, norm_list):
    pn = _PUNCT_RE.sub("", norm)
    if len(pn) >= 3:
        punct_norm_map[pn].append(kw)
for pn, group in punct_norm_map.items():
    if len(group) < 2:
        continue
    for a, b in itertools.combinations(group, 2):
        add_pair(a, b, "iv", "punctuation_hyphenation", 0.95)
log.info(f"  Stratum iv: {sum(1 for c in all_candidates if c['stratum']=='iv'):,}")

# A4: Stratum v
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
log.info(f"  Stratum v: {sum(1 for c in all_candidates if c['stratum']=='v'):,}")

# B: Stratum iii
ACRONYM_RE    = re.compile(r"^[A-Z]{2,6}$")
PAREN_ACRO_RE = re.compile(r"\(([A-Za-z]{2,6})\)")
_SPLIT_RE     = re.compile(r"[\s\-/]+")
acronym_kws = [(kw, kw.strip().upper()) for kw in kw_list if ACRONYM_RE.match(kw.strip())]
paren_index: dict = defaultdict(list)
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
log.info(f"  Stratum iii: {sum(1 for c in all_candidates if c['stratum']=='iii'):,}")

# C: Embedding strata
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.neighbors import NearestNeighbors

    emb_model_st = SentenceTransformer("all-MiniLM-L6-v2")
    emb_rows = [(kw, norm) for kw, norm, freq in zip(kw_list, norm_list, freq_list) if freq >= 2]
    emb_kws   = [r[0] for r in emb_rows]
    emb_norms = [r[1] for r in emb_rows]
    short_ambig = {kw for kw, norm in emb_rows if 2 <= len(norm) <= 4 and norm.islower()
                   and not ACRONYM_RE.match(kw.strip())}
    log.info(f"  Encoding {len(emb_kws):,} keywords ...")
    embeddings = emb_model_st.encode(emb_norms, batch_size=256, show_progress_bar=True,
                                      convert_to_numpy=True, normalize_embeddings=True)
    nn = NearestNeighbors(n_neighbors=8, metric="cosine", algorithm="brute", n_jobs=-1)
    nn.fit(embeddings)
    distances, indices = nn.kneighbors(embeddings)
    log.info("  kneighbors complete.")

    def embedding_stratum(kw_a: str, sim: float) -> tuple:
        if kw_a in short_ambig:
            return "viii", "embedding_short_ambig"
        if sim >= 0.75:
            return "vi", "embedding_near_synonym"
        if sim >= 0.60:
            return "vii", "embedding_broader_narrower"
        return "x", "embedding_weak_semantic"

    for i, kw_a in enumerate(emb_kws):
        top_k = 3 if kw_a in short_ambig else 5
        for rank in range(1, min(top_k + 1, 8)):
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

    for s in ["vi", "vii", "viii", "x"]:
        log.info(f"  Stratum {s}: {sum(1 for c in all_candidates if c['stratum']==s):,}")
except ImportError as exc:
    log.warning(f"sentence-transformers unavailable: {exc}")

TOTAL_CANDIDATE_PAIRS = len(all_candidates)
_t1_cand = time.time()
log.info(f"Total candidate pairs: {TOTAL_CANDIDATE_PAIRS:,}  [{_t1_cand - _t0_cand:.1f}s]")


# ===========================================================================
# Union-Find
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
# PHASE 4: Harmonisation conditions
# ===========================================================================
log.info("PHASE 4: Harmonisation conditions ...")

# Condition 1: Raw
raw_kw_to_canonical: dict = {kw: kw for kw in all_raw_keywords}
raw_kw_to_cluster:   dict = {kw: kw for kw in all_raw_keywords}
log.info(f"  Raw: {len(raw_kw_to_canonical):,} unique canonical forms")

# Condition 2: B3 Jaro-Winkler
uf_b3 = UnionFind()
for kw in all_raw_keywords:
    uf_b3.find(kw)
b3_matches = 0
for cand in all_candidates:
    a, b = cand["keyword_a"], cand["keyword_b"]
    na, nb = raw_to_norm[a], raw_to_norm[b]
    jw = jellyfish.jaro_winkler_similarity(na, nb)
    if jw >= B3_THRESHOLD:
        uf_b3.union(a, b)
        b3_matches += 1

b3_clusters = uf_b3.clusters(all_raw_keywords)
b3_kw_to_canonical: dict = {}
b3_kw_to_cluster_id: dict = {}
for root, members in b3_clusters.items():
    canonical_kw = max(members, key=lambda k: kw_freq.get(k, 0))
    for m in members:
        b3_kw_to_canonical[m]   = canonical_kw
        b3_kw_to_cluster_id[m] = canonical_kw
log.info(f"  B3: {b3_matches:,} matches | {len(b3_clusters):,} clusters")

# Condition 3: Full LLM-DAG (from checkpoint)
log.info("  Full LLM-DAG: loading checkpoint ...")
llm_log_path = LLM_LOGS / "downstream_raw_outputs.jsonl"

uf_llm = UnionFind()
for kw in all_raw_keywords:
    uf_llm.find(kw)

llm_call_count   = 0
llm_real_count   = 0
llm_total_cost   = 0.0
llm_matches      = 0
processed_pairs: set = set()

if llm_log_path.exists():
    with open(llm_log_path, encoding="utf-8") as _f:
        for _line in _f:
            try:
                _e  = json.loads(_line.strip())
                _kw_a = _e.get("keyword_a", "")
                _kw_b = _e.get("keyword_b", "")
                _key = canonical_pair(_kw_a, _kw_b)
                processed_pairs.add(_key)
                llm_call_count += 1
                _cost = _e.get("cost_usd", 0.0)
                llm_total_cost += _cost
                if _cost > 0:
                    llm_real_count += 1
                if _e.get("decision") == "match":
                    uf_llm.union(_kw_a, _kw_b)
                    llm_matches += 1
            except Exception:
                continue
else:
    log.warning("No LLM log found — LLM-DAG condition will equal raw condition!")

llm_coverage = len(processed_pairs) / max(TOTAL_CANDIDATE_PAIRS, 1)
log.info(f"  LLM-DAG checkpoint: {llm_call_count:,} pairs ({llm_coverage*100:.1f}%) | "
         f"real LLM calls: {llm_real_count:,} | "
         f"matches: {llm_matches:,} | cost: ${llm_total_cost:.4f}")

# For unprocessed pairs, use B3 JW decision as fallback
# (these are embedding/acronym pairs not yet evaluated by LLM)
n_fallback = 0
for cand in all_candidates:
    a, b = cand["keyword_a"], cand["keyword_b"]
    pair_key = canonical_pair(a, b)
    if pair_key not in processed_pairs:
        # Unprocessed: use B3 fallback (if JW >= threshold, merge; else skip)
        na, nb = raw_to_norm[a], raw_to_norm[b]
        jw = jellyfish.jaro_winkler_similarity(na, nb)
        if jw >= B3_THRESHOLD:
            uf_llm.union(a, b)
        n_fallback += 1

log.info(f"  LLM-DAG: {n_fallback:,} unprocessed pairs used B3 fallback")

llm_clusters = uf_llm.clusters(all_raw_keywords)
llm_kw_to_canonical:  dict = {}
llm_kw_to_cluster_id: dict = {}
for root, members in llm_clusters.items():
    canonical_kw = max(members, key=lambda k: kw_freq.get(k, 0))
    for m in members:
        llm_kw_to_canonical[m]  = canonical_kw
        llm_kw_to_cluster_id[m] = canonical_kw
log.info(f"  LLM-DAG clusters: {len(llm_clusters):,}")


# ===========================================================================
# PHASE 5: Co-word networks
# ===========================================================================
log.info("PHASE 5: Building co-word networks ...")

import networkx as nx
try:
    import community as community_louvain
    log.info("  python-louvain imported.")
except ImportError:
    try:
        from community import best_partition as _bp
        import community as community_louvain
        log.info("  python-louvain imported via best_partition.")
    except ImportError:
        log.warning("  python-louvain not available.")
        community_louvain = None


def build_coword_network(kw_to_canonical_map: dict, freq_threshold: int = 5) -> tuple:
    # Map articles to canonical keywords
    article_to_canonical: dict = {}
    for eid, kws in article_to_kws.items():
        canon_set = set()
        for kw in kws:
            if kw in kw_to_canonical_map:
                canon_set.add(kw_to_canonical_map[kw])
        article_to_canonical[eid] = canon_set

    # Canonical frequency
    canon_freq: dict = defaultdict(int)
    for eid, canon_kws in article_to_canonical.items():
        for ck in canon_kws:
            canon_freq[ck] += 1

    valid_canonicals = {ck for ck, f in canon_freq.items() if f >= freq_threshold}
    log.info(f"    Canon. keywords f>={freq_threshold}: {len(valid_canonicals):,}")

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
    density  = 2 * n_edges / (n_nodes * (n_nodes - 1)) if n_nodes > 1 else 0.0

    log.info(f"    Nodes: {n_nodes:,} | Edges: {n_edges:,} | Density: {density:.6f}")

    if community_louvain is not None and n_nodes > 1:
        partition     = community_louvain.best_partition(G, resolution=1.0, random_state=SEED)
        for node in G.nodes():
            if node not in partition:
                partition[node] = max(partition.values(), default=-1) + 1
        modularity_q  = community_louvain.modularity(partition, G)
        n_communities = len(set(partition.values()))
    else:
        partition     = {node: i for i, node in enumerate(G.nodes())}
        modularity_q  = float("nan")
        n_communities = n_nodes

    log.info(f"    Q={modularity_q:.4f} | Communities: {n_communities}")
    return G, dict(canon_freq), partition, modularity_q, n_communities, n_nodes, n_edges, density


log.info("  RAW network ...")
(G_raw, freq_raw, part_raw, mod_raw, ncom_raw,
 vsize_raw, nedge_raw, dens_raw) = build_coword_network(raw_kw_to_canonical)

log.info("  B3 network ...")
(G_b3, freq_b3, part_b3, mod_b3, ncom_b3,
 vsize_b3, nedge_b3, dens_b3) = build_coword_network(b3_kw_to_canonical)

log.info("  LLM-DAG network ...")
(G_llm, freq_llm, part_llm, mod_llm, ncom_llm,
 vsize_llm, nedge_llm, dens_llm) = build_coword_network(llm_kw_to_canonical)


# ===========================================================================
# PHASE 6: ARI and AMI
# ===========================================================================
log.info("PHASE 6: ARI and AMI ...")

from sklearn.metrics import adjusted_rand_score, adjusted_mutual_info_score


def compute_ari_ami(part_ref: dict, part_harm: dict,
                    raw_nodes: set, canon_map: dict) -> tuple:
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

ari_b3,  ami_b3,  n_ov_b3  = compute_ari_ami(part_raw, part_b3,  raw_nodes_set, b3_kw_to_canonical)
ari_llm, ami_llm, n_ov_llm = compute_ari_ami(part_raw, part_llm, raw_nodes_set, llm_kw_to_canonical)

log.info(f"  B3 vs Raw:  ARI={ari_b3:.4f}  AMI={ami_b3:.4f}  overlap={n_ov_b3:,}")
log.info(f"  LLM vs Raw: ARI={ari_llm:.4f}  AMI={ami_llm:.4f}  overlap={n_ov_llm:,}")


# ===========================================================================
# PHASE 7: Qualitative examples
# ===========================================================================
log.info("PHASE 7: Qualitative examples ...")


def find_qualitative_examples(kw_to_canon: dict, freq_threshold: int = 5,
                               max_examples: int = 3) -> list:
    canon_to_raws: dict = defaultdict(list)
    for raw_kw, canon_kw in kw_to_canon.items():
        canon_to_raws[canon_kw].append(raw_kw)
    examples = []
    for canon_kw, raws in canon_to_raws.items():
        if len(raws) < 2:
            continue
        qualifying = [r for r in raws if kw_freq.get(r, 0) >= freq_threshold]
        if len(qualifying) < 2:
            continue
        examples.append({
            "canonical_form":       canon_kw,
            "merged_raw_keywords":  qualifying,
            "raw_freqs":            {r: kw_freq.get(r, 0) for r in qualifying},
            "n_merged":             len(qualifying),
        })
    examples.sort(key=lambda x: (x["n_merged"], sum(x["raw_freqs"].values())), reverse=True)
    return examples[:max_examples]


b3_examples  = find_qualitative_examples(b3_kw_to_canonical)
llm_examples = find_qualitative_examples(llm_kw_to_canonical)
log.info(f"  B3: {len(b3_examples)} examples | LLM: {len(llm_examples)} examples")


# ===========================================================================
# PHASE 8: Save results
# ===========================================================================
log.info("PHASE 8: Saving results ...")
_t1 = time.time()
total_runtime = _t1 - _t0

results_rows = [
    {
        "condition":     "raw",
        "vocab_size":    vsize_raw,
        "n_edges":       nedge_raw,
        "density":       round(dens_raw,  8),
        "modularity_q":  round(mod_raw,   6) if mod_raw == mod_raw else "NaN",
        "n_communities": ncom_raw,
        "ari":           "reference",
        "ami":           "reference",
    },
    {
        "condition":     "b3_jaro_winkler",
        "vocab_size":    vsize_b3,
        "n_edges":       nedge_b3,
        "density":       round(dens_b3,   8),
        "modularity_q":  round(mod_b3,    6) if mod_b3 == mod_b3   else "NaN",
        "n_communities": ncom_b3,
        "ari":           round(ari_b3,    6) if ari_b3 == ari_b3   else "NaN",
        "ami":           round(ami_b3,    6) if ami_b3 == ami_b3   else "NaN",
    },
    {
        "condition":     "full_llm_dag",
        "vocab_size":    vsize_llm,
        "n_edges":       nedge_llm,
        "density":       round(dens_llm,  8),
        "modularity_q":  round(mod_llm,   6) if mod_llm == mod_llm else "NaN",
        "n_communities": ncom_llm,
        "ari":           round(ari_llm,   6) if ari_llm == ari_llm else "NaN",
        "ami":           round(ami_llm,   6) if ami_llm == ami_llm else "NaN",
    },
]
pd.DataFrame(results_rows).to_csv(RESULTS / "downstream_results.csv",
                                   index=False, encoding="utf-8-sig")
log.info(f"Saved -> {RESULTS / 'downstream_results.csv'}")

# Summary text
summary_lines = [
    "=" * 78,
    "DOWNSTREAM THEMATIC COMPARISON — RESULTS SUMMARY",
    "=" * 78,
    "",
    f"NOTE: Full LLM-DAG condition based on {llm_coverage*100:.1f}% of candidate pairs",
    f"      ({llm_call_count:,} processed, {TOTAL_CANDIDATE_PAIRS - llm_call_count:,} pending).",
    f"      Real LLM API calls: {llm_real_count:,}  |  Cost: ${llm_total_cost:.4f}",
    f"      Unprocessed pairs use B3-JW fallback.",
    f"      Re-run run_downstream.py or run_downstream_analysis.py after full LLM run.",
    "",
    f"{'Condition':<20} {'Vocab':>7} {'Edges':>9} {'Density':>12} "
    f"{'Mod. Q':>9} {'N Comm':>8} {'ARI':>9} {'AMI':>9}",
    "-" * 78,
]
for row in results_rows:
    ari_s = f"{row['ari']:>9.4f}" if isinstance(row['ari'], float) else f"{'ref':>9}"
    ami_s = f"{row['ami']:>9.4f}" if isinstance(row['ami'], float) else f"{'ref':>9}"
    mq_s  = f"{row['modularity_q']:>9.4f}" if isinstance(row['modularity_q'], float) else f"{'NaN':>9}"
    summary_lines.append(
        f"{row['condition']:<20} {row['vocab_size']:>7,} {row['n_edges']:>9,} "
        f"{row['density']:>12.8f} {mq_s} {row['n_communities']:>8,} {ari_s} {ami_s}"
    )
summary_lines += [
    "-" * 78,
    "",
    f"B3 Jaro-Winkler threshold:  {B3_THRESHOLD}",
    f"Guard confidence threshold: {GUARD_THRESHOLD}",
    f"Model:                      {MODEL_ID}",
    f"Total candidate pairs:      {TOTAL_CANDIDATE_PAIRS:,}",
    f"LLM pairs processed:        {llm_call_count:,} ({llm_coverage*100:.1f}%)",
    f"Real LLM API calls:         {llm_real_count:,}",
    f"LLM total cost:             ${llm_total_cost:.4f}",
    f"Cost per 1,000 real calls:  ${llm_total_cost / max(llm_real_count, 1) * 1000:.4f}",
    f"Total runtime:              {total_runtime:.1f}s",
    f"Generated:                  {datetime.now(timezone.utc).isoformat()}",
    "",
]
summary_text = "\n".join(summary_lines)
print("\n" + summary_text)

with open(RESULTS / "downstream_results_summary.txt", "w", encoding="utf-8") as f:
    f.write(summary_text + "\n")
log.info(f"Saved -> {RESULTS / 'downstream_results_summary.txt'}")

# Qualitative examples
qual_lines = [
    "=" * 78,
    "DOWNSTREAM QUALITATIVE EXAMPLES",
    "=" * 78,
    "",
    "These show keyword groups where harmonisation merged separate raw-network nodes",
    "(all merged keywords had freq >= 5 in raw).",
    "",
    "─" * 78,
    "CONDITION 2: B3 Jaro-Winkler",
    "─" * 78,
]
if b3_examples:
    for i, ex in enumerate(b3_examples, 1):
        qual_lines += [f"\nExample {i}:",
                       f"  Canonical form: {ex['canonical_form']}",
                       f"  Merged keywords ({ex['n_merged']}):"]
        for rk in ex["merged_raw_keywords"]:
            qual_lines.append(f"    - '{rk}'  (freq={ex['raw_freqs'][rk]})")
        qual_lines.append(f"  Change: {ex['n_merged']} raw nodes -> 1 canonical node.")
else:
    qual_lines.append("  None found.")

qual_lines += ["", "─" * 78, "CONDITION 3: Full LLM-DAG", "─" * 78]
if llm_examples:
    for i, ex in enumerate(llm_examples, 1):
        qual_lines += [f"\nExample {i}:",
                       f"  Canonical form: {ex['canonical_form']}",
                       f"  Merged keywords ({ex['n_merged']}):"]
        for rk in ex["merged_raw_keywords"]:
            qual_lines.append(f"    - '{rk}'  (freq={ex['raw_freqs'][rk]})")
        qual_lines.append(f"  Change: {ex['n_merged']} raw nodes -> 1 canonical node.")
else:
    qual_lines.append("  None found.")

with open(RESULTS / "downstream_qualitative_examples.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(qual_lines) + "\n")
log.info(f"Saved -> {RESULTS / 'downstream_qualitative_examples.txt'}")

# Harmonisation maps
def save_harm_map(kw_to_canon: dict, kw_to_cid: dict, freq_map: dict, path: pathlib.Path):
    rows = [{"keyword": kw, "canonical_form": kw_to_canon.get(kw, kw),
             "cluster_id": kw_to_cid.get(kw, kw), "freq": freq_map.get(kw, kw_freq.get(kw, 0))}
            for kw in all_raw_keywords]
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    log.info(f"Saved map -> {path}")

b3_cfreq  = {kw: freq_b3.get(b3_kw_to_canonical.get(kw, kw), 0)  for kw in all_raw_keywords}
llm_cfreq = {kw: freq_llm.get(llm_kw_to_canonical.get(kw, kw), 0) for kw in all_raw_keywords}

save_harm_map(raw_kw_to_canonical, raw_kw_to_cluster, kw_freq, HARM_MAPS / "raw_map.csv")
save_harm_map(b3_kw_to_canonical,  b3_kw_to_cluster_id,  b3_cfreq,  HARM_MAPS / "b3_map.csv")
save_harm_map(llm_kw_to_canonical, llm_kw_to_cluster_id, llm_cfreq, HARM_MAPS / "full_llm_dag_map.csv")


# ===========================================================================
# PHASE 9: Efficiency report
# ===========================================================================
eff_lines = [
    "", "=" * 60, "EFFICIENCY REPORT", "=" * 60,
    f"Total candidate pairs generated:  {TOTAL_CANDIDATE_PAIRS:,}",
    f"LLM log entries (checkpoint):     {llm_call_count:,} ({llm_coverage*100:.1f}%)",
    f"Real LLM API calls made:          {llm_real_count:,}",
    f"LLM matches found:                {llm_matches:,}",
    f"LLM total cost:                   ${llm_total_cost:.4f}",
    f"Cost per 1,000 real calls:        ${llm_total_cost / max(llm_real_count, 1) * 1000:.4f}",
    f"",
    f"Runtime breakdown:",
    f"  Candidate generation:           {_t1_cand - _t0_cand:.1f}s",
    f"  Total analysis runtime:         {total_runtime:.1f}s",
    "=" * 60,
]
print("\n".join(eff_lines))

log.info("run_downstream_analysis.py COMPLETE")
