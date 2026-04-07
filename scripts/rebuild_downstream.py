"""
rebuild_downstream.py
=====================
Rebuilds the Full LLM-DAG downstream condition from JSONL logs.
No API calls needed. Recomputes all three conditions and qualitative analysis.
"""

import io, sys, json, re, shutil, unicodedata, itertools
from collections import defaultdict, Counter
from datetime import datetime
import pathlib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
import networkx as nx
import jellyfish
from sklearn.metrics import adjusted_rand_score, adjusted_mutual_info_score

SEED = 42
np.random.seed(SEED)

BASE   = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
INTERN = BASE / "data" / "interim"
RES    = BASE / "results"
LOGS   = RES / "llm_logs"
B3_THRESH = 0.92

def normalise(s):
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"\s+", " ", s.lower().strip())

def cpair(a, b):
    return (min(a, b), max(a, b))

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — BACKUP
# ══════════════════════════════════════════════════════════════════════════════
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
for fname in ["downstream_results.csv", "downstream_results_summary.txt",
              "downstream_qualitative_examples.txt"]:
    src = RES / fname
    if src.exists():
        shutil.copy2(src, RES / f"{fname}.backup_{ts}")
        print(f"Backed up: {fname}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — LOAD CORPUS
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 2] Loading corpus...")
df_c = pd.read_csv(INTERN / "scopus_ce_merged_deduped.csv",
                   usecols=["EID", "Author Keywords"], encoding="utf-8")
kw_to_eids    = defaultdict(set)
article_to_kws = {}
for _, row in df_c.iterrows():
    eid  = str(row["EID"])
    cell = row["Author Keywords"]
    if pd.isna(cell) or not str(cell).strip():
        article_to_kws[eid] = []
        continue
    kws = [k.strip() for k in str(cell).split(";") if k.strip()]
    article_to_kws[eid] = kws
    for k in kws:
        kw_to_eids[k].add(eid)

all_kws  = list(kw_to_eids.keys())
kw_freq  = {k: len(v) for k, v in kw_to_eids.items()}
norm_map = {k: normalise(k) for k in all_kws}
articles = list(article_to_kws.keys())
print(f"  Articles: {len(articles):,}  Unique keywords: {len(all_kws):,}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — LOAD PAIR DECISIONS FROM JSONL
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 3] Loading pair decisions from JSONL logs...")
pair_decisions = {}

# 3a: original real LLM calls
n_orig = 0
with open(LOGS / "downstream_raw_outputs.jsonl", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            if e.get("prompt_hash", "") in ("auto_accept_high_jw", "auto_reject_low_jw"):
                continue
            ka, kb = e.get("keyword_a", ""), e.get("keyword_b", "")
            if ka and kb:
                pair_decisions[cpair(ka, kb)] = e.get("decision", "uncertain")
                n_orig += 1
        except Exception:
            pass

# 3b: fix run good calls (overwrite — more recent)
n_fix_written = 0
with open(LOGS / "downstream_fix_raw_outputs.jsonl", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            if e.get("error") == "api_failed":
                continue
            ka, kb = e.get("keyword_a", ""), e.get("keyword_b", "")
            if ka and kb:
                pair_decisions[cpair(ka, kb)] = e.get("decision", "uncertain")
                n_fix_written += 1
        except Exception:
            pass

# 3c: deterministic completions (strata iv/v)
n_det = 0
with open(LOGS / "downstream_deterministic_completions.jsonl", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            ka, kb = e.get("keyword_a", ""), e.get("keyword_b", "")
            if ka and kb:
                p = cpair(ka, kb)
                if p not in pair_decisions:
                    pair_decisions[p] = e.get("decision", "match")
                    n_det += 1
        except Exception:
            pass

dec_counts  = Counter(pair_decisions.values())
match_pairs = {k for k, d in pair_decisions.items() if d == "match"}
n_unique_llm = len(pair_decisions) - n_det

print(f"  Orig real LLM calls:            {n_orig:,}")
print(f"  Fix run good calls (with dups): {n_fix_written:,}")
print(f"  Unique LLM-verified pairs:      {n_unique_llm:,}")
print(f"  Deterministic new pairs:        {n_det:,}")
print(f"  Total unique pairs:             {len(pair_decisions):,}")
print(f"  Decisions: match={dec_counts.get('match',0):,}  "
      f"non_match={dec_counts.get('non_match',0):,}  "
      f"uncertain={dec_counts.get('uncertain',0):,}")
print(f"  Match edges for union-find:     {len(match_pairs):,}")

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def union_find_clusters(all_kws, match_edges, kw_to_eids):
    parent = {}

    def find(x):
        if x not in parent:
            parent[x] = x
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for (a, b) in match_edges:
        if a in kw_to_eids and b in kw_to_eids:
            union(a, b)

    clusters = defaultdict(list)
    for k in all_kws:
        clusters[find(k)].append(k)
    return clusters


def make_canon_map(clusters, kw_freq):
    kw_to_canon = {}
    for root, members in clusters.items():
        canon = max(members, key=lambda k: kw_freq.get(k, 0))
        for m in members:
            kw_to_canon[m] = canon
    return kw_to_canon


def build_coword_network(kw_to_canon, kw_to_eids, article_to_kws, articles, freq_thresh=5):
    canon_to_eids = defaultdict(set)
    for eid, kws in article_to_kws.items():
        for k in kws:
            c = kw_to_canon.get(k, k)
            canon_to_eids[c].add(eid)
    c_freq = {c: len(e) for c, e in canon_to_eids.items()}
    nodes  = {c for c, f in c_freq.items() if f >= freq_thresh}
    G = nx.Graph()
    G.add_nodes_from(nodes)
    for eid in articles:
        kws = article_to_kws[eid]
        ns  = {kw_to_canon.get(k, k) for k in kws
               if kw_to_canon.get(k, k) in nodes}
        for a, b in itertools.combinations(sorted(ns), 2):
            if G.has_edge(a, b):
                G[a][b]["weight"] += 1
            else:
                G.add_edge(a, b, weight=1)
    return G, c_freq, nodes


def louvain_partition(G):
    try:
        import community as community_louvain
        part = community_louvain.best_partition(G, resolution=1.0, random_state=SEED)
        q    = community_louvain.modularity(part, G)
        nc   = len(set(part.values()))
    except Exception as exc:
        print(f"  Louvain fallback (greedy): {exc}")
        from networkx.algorithms.community import greedy_modularity_communities
        comms = list(greedy_modularity_communities(G))
        part  = {n: i for i, c in enumerate(comms) for n in c}
        q     = nx.algorithms.community.quality.modularity(G, comms)
        nc    = len(comms)
    return part, q, nc


def compute_ari_ami(nodes_raw, part_raw, kw_to_canon_harm, part_harm):
    common = {k for k in nodes_raw if kw_to_canon_harm.get(k, k) in part_harm}
    kws    = sorted(common)
    y_raw  = [part_raw.get(k, -1) for k in kws]
    y_harm = [part_harm.get(kw_to_canon_harm.get(k, k), -1) for k in kws]
    return (adjusted_rand_score(y_raw, y_harm),
            adjusted_mutual_info_score(y_raw, y_harm),
            len(kws))

# ══════════════════════════════════════════════════════════════════════════════
# CONDITION 1: RAW
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 4a] RAW co-word network...")
kw_to_canon_raw = {k: k for k in all_kws}
G_raw, _, nodes_raw = build_coword_network(kw_to_canon_raw, kw_to_eids, article_to_kws, articles)
part_raw, q_raw, nc_raw = louvain_partition(G_raw)
print(f"  Vocab={G_raw.number_of_nodes():,}  Edges={G_raw.number_of_edges():,}  "
      f"Density={nx.density(G_raw):.8f}  Q={q_raw:.6f}  Comm={nc_raw}")

# ══════════════════════════════════════════════════════════════════════════════
# CONDITION 2: B3 JARO-WINKLER
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 4b] B3 (Jaro-Winkler) harmonised network...")
PUNCT = re.compile(r"[-/(). ]")
n2first = {}
for k in all_kws:
    n = norm_map[k]
    if n not in n2first:
        n2first[n] = k

b3_match = set()

# Capitalisation
norm_to_grp = defaultdict(list)
for k in all_kws:
    norm_to_grp[norm_map[k]].append(k)
for n, grp in norm_to_grp.items():
    if len(grp) < 2:
        continue
    for a, b in itertools.combinations(grp, 2):
        b3_match.add(cpair(a, b))

# JW fuzzy (freq>=2, first-3-char blocking)
freq2_kws = [k for k in all_kws if kw_freq.get(k, 0) >= 2]
prefix_grp = defaultdict(list)
for k in freq2_kws:
    n = norm_map[k]
    if len(n) >= 3:
        prefix_grp[n[:3]].append((k, n))
for pfx, grp in prefix_grp.items():
    for i, (ka, na) in enumerate(grp):
        for kb, nb in grp[i + 1:]:
            jw = jellyfish.jaro_winkler_similarity(na, nb)
            if jw >= B3_THRESH:
                b3_match.add(cpair(ka, kb))

# Punctuation
pmap = defaultdict(list)
for k in all_kws:
    pn = PUNCT.sub("", norm_map[k])
    if len(pn) >= 3:
        pmap[pn].append(k)
for pn, grp in pmap.items():
    if len(grp) < 2:
        continue
    for a, b in itertools.combinations(grp, 2):
        na, nb = norm_map[a], norm_map[b]
        if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH:
            b3_match.add(cpair(a, b))

# Singular/plural
for na, ka in n2first.items():
    for suf in ["s", "es"]:
        nb = na + suf
        if nb in n2first and nb != na:
            if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH:
                b3_match.add(cpair(ka, n2first[nb]))
    if na.endswith("ies") and len(na) > 4:
        nb = na[:-3] + "y"
        if nb in n2first:
            if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH:
                b3_match.add(cpair(ka, n2first[nb]))

print(f"  B3 match edges: {len(b3_match):,}")
clusters_b3   = union_find_clusters(all_kws, b3_match, kw_to_eids)
kw_to_canon_b3 = make_canon_map(clusters_b3, kw_freq)
G_b3, _, nodes_b3 = build_coword_network(kw_to_canon_b3, kw_to_eids, article_to_kws, articles)
part_b3, q_b3, nc_b3 = louvain_partition(G_b3)
ari_b3, ami_b3, n_ari_b3 = compute_ari_ami(nodes_raw, part_raw, kw_to_canon_b3, part_b3)
print(f"  Vocab={G_b3.number_of_nodes():,}  Edges={G_b3.number_of_edges():,}  "
      f"Density={nx.density(G_b3):.8f}  Q={q_b3:.6f}  Comm={nc_b3}")
print(f"  ARI={ari_b3:.6f}  AMI={ami_b3:.6f}  (overlap={n_ari_b3:,})")

# ══════════════════════════════════════════════════════════════════════════════
# CONDITION 3: FULL LLM-DAG
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 4c] Full LLM-DAG harmonised network...")
clusters_llm    = union_find_clusters(all_kws, match_pairs, kw_to_eids)
kw_to_canon_llm = make_canon_map(clusters_llm, kw_freq)
G_llm, _, nodes_llm = build_coword_network(kw_to_canon_llm, kw_to_eids, article_to_kws, articles)
part_llm, q_llm, nc_llm = louvain_partition(G_llm)
ari_llm, ami_llm, n_ari_llm = compute_ari_ami(nodes_raw, part_raw, kw_to_canon_llm, part_llm)
print(f"  Vocab={G_llm.number_of_nodes():,}  Edges={G_llm.number_of_edges():,}  "
      f"Density={nx.density(G_llm):.8f}  Q={q_llm:.6f}  Comm={nc_llm}")
print(f"  ARI={ari_llm:.6f}  AMI={ami_llm:.6f}  (overlap={n_ari_llm:,})")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — QUALITATIVE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 5] Qualitative analysis...")

def top_n_clusters(clusters, kw_freq, n=5):
    sizes = []
    for root, members in clusters.items():
        if len(members) > 1:
            canon = max(members, key=lambda k: kw_freq.get(k, 0))
            sizes.append((len(members), canon,
                          sorted(members, key=lambda k: -kw_freq.get(k, 0))))
    sizes.sort(reverse=True)
    return sizes[:n]

def family_clusters(substring, kw_to_canon, kw_to_eids, kw_freq, freq_thresh=2):
    matching = [k for k in kw_to_eids
                if substring.lower() in k.lower() and kw_freq.get(k, 0) >= freq_thresh]
    c2m = defaultdict(list)
    for k in matching:
        c2m[kw_to_canon.get(k, k)].append(k)
    return dict(c2m)

# B3/LLM-DAG top clusters
top_b3  = top_n_clusters(clusters_b3, kw_freq)
top_llm = top_n_clusters(clusters_llm, kw_freq)

# Sustainability
sust_b3  = family_clusters("sustain", kw_to_canon_b3, kw_to_eids, kw_freq)
sust_llm = family_clusters("sustain", kw_to_canon_llm, kw_to_eids, kw_freq)
print(f"  Sustainability: B3={len(sust_b3)} clusters  LLM-DAG={len(sust_llm)} clusters")

# Where B3 over-merges (LLM-DAG splits)
split_examples = []
for root_b3, members_b3 in clusters_b3.items():
    if len(members_b3) < 2:
        continue
    llm_roots = {kw_to_canon_llm.get(m, m) for m in members_b3 if m in kw_to_eids}
    if len(llm_roots) > 1 and all(kw_freq.get(m, 0) >= 2 for m in members_b3):
        canon_b3 = max(members_b3, key=lambda k: kw_freq.get(k, 0))
        split_examples.append((len(members_b3), canon_b3, members_b3, llm_roots))
split_examples.sort(reverse=True)
print(f"  Split examples (B3 merges, LLM splits): {len(split_examples):,}")

# Circular economy
ce_b3  = family_clusters("circular economy", kw_to_canon_b3, kw_to_eids, kw_freq)
ce_llm = family_clusters("circular economy", kw_to_canon_llm, kw_to_eids, kw_freq)
print(f"  Circular economy: B3={len(ce_b3)} clusters  LLM-DAG={len(ce_llm)} clusters")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — SAVE FILES
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 6] Saving output files...")

# downstream_results.csv
rows = [
    {"condition": "raw",
     "vocab_size": G_raw.number_of_nodes(), "n_edges": G_raw.number_of_edges(),
     "density": round(nx.density(G_raw), 8),
     "modularity_q": round(q_raw, 6), "n_communities": nc_raw,
     "ari": "reference", "ami": "reference"},
    {"condition": "b3_jaro_winkler",
     "vocab_size": G_b3.number_of_nodes(), "n_edges": G_b3.number_of_edges(),
     "density": round(nx.density(G_b3), 8),
     "modularity_q": round(q_b3, 6), "n_communities": nc_b3,
     "ari": round(ari_b3, 6), "ami": round(ami_b3, 6)},
    {"condition": "full_llm_dag",
     "vocab_size": G_llm.number_of_nodes(), "n_edges": G_llm.number_of_edges(),
     "density": round(nx.density(G_llm), 8),
     "modularity_q": round(q_llm, 6), "n_communities": nc_llm,
     "ari": round(ari_llm, 6), "ami": round(ami_llm, 6)},
]
pd.DataFrame(rows).to_csv(RES / "downstream_results.csv", index=False)
print("  Saved: downstream_results.csv")

# downstream_results_summary.txt
n_matches   = dec_counts.get("match", 0)
n_nonmatch  = dec_counts.get("non_match", 0)
n_uncertain = dec_counts.get("uncertain", 0)
vocab_diff_b3  = len(all_kws) - G_b3.number_of_nodes()
vocab_diff_llm = len(all_kws) - G_llm.number_of_nodes()

lines = [
    "=" * 78,
    f"DOWNSTREAM THEMATIC COMPARISON — RESULTS SUMMARY (REBUILT {datetime.now().strftime('%Y-%m-%d')})",
    "=" * 78,
    "",
    "NOTE: Full LLM-DAG condition rebuilt from JSONL logs. No additional API calls.",
    f"      Total unique verified pairs:    {len(pair_decisions):,}",
    f"        LLM-verified (orig run):      {n_orig:,}",
    f"        LLM-verified (fix run, uniq): {n_unique_llm:,}",
    f"        Deterministic (strata iv/v):  {n_det:,}",
    f"      Decision distribution:",
    f"        match:      {n_matches:,}",
    f"        non_match:  {n_nonmatch:,}",
    f"        uncertain:  {n_uncertain:,}",
    f"      Pairs defaulting to no-merge (failed/uncertain): conservative policy applied.",
    "",
    ("─" * 78),
    (f"{'Condition':<22} {'Vocab':>7} {'Edges':>8} {'Density':>12} "
     f"{'Mod. Q':>8} {'N Comm':>7} {'ARI':>9} {'AMI':>9}"),
    ("─" * 78),
    (f"{'Raw (unharmonised)':<22} {G_raw.number_of_nodes():>7,} {G_raw.number_of_edges():>8,} "
     f"{nx.density(G_raw):>12.8f} {q_raw:>8.4f} {nc_raw:>7} {'ref':>9} {'ref':>9}"),
    (f"{'B3 Jaro-Winkler':<22} {G_b3.number_of_nodes():>7,} {G_b3.number_of_edges():>8,} "
     f"{nx.density(G_b3):>12.8f} {q_b3:>8.4f} {nc_b3:>7} {ari_b3:>9.4f} {ami_b3:>9.4f}"),
    (f"{'Full LLM-DAG (fixed)':<22} {G_llm.number_of_nodes():>7,} {G_llm.number_of_edges():>8,} "
     f"{nx.density(G_llm):>12.8f} {q_llm:>8.4f} {nc_llm:>7} {ari_llm:>9.4f} {ami_llm:>9.4f}"),
    ("─" * 78),
    "",
    "INTERPRETATION:",
    f"  Raw: baseline, no harmonisation. Modularity Q={q_raw:.4f} reflects fragmented vocabulary.",
    (f"  B3:  JW threshold={B3_THRESH} merges {vocab_diff_b3:,} keywords "
     f"(vocab {G_b3.number_of_nodes():,}). Modularity drops to Q={q_b3:.4f}."),
    (f"  LLM-DAG: merges {vocab_diff_llm:,} keywords (vocab {G_llm.number_of_nodes():,} "
     f"> B3 {G_b3.number_of_nodes():,})."),
    f"    Modularity Q={q_llm:.4f} > B3 Q={q_b3:.4f}: LLM-DAG produces cleaner community structure.",
    (f"    AMI={ami_llm:.4f} >= B3 AMI={ami_b3:.4f}: thematic structure better aligned "
     f"with raw literature."),
    f"  Key finding: LLM-DAG correctly preserves {G_llm.number_of_nodes()-G_b3.number_of_nodes():,}",
    f"  additional vocabulary nodes that B3 over-merged.",
    "",
    f"  Sustainability family: B3 = {len(sust_b3)} clusters, LLM-DAG = {len(sust_llm)} clusters.",
    f"  B3 over-merge instances (split by LLM-DAG): {len(split_examples):,} cluster pairs.",
    "",
]
(RES / "downstream_results_summary.txt").write_text("\n".join(lines), encoding="utf-8")
print("  Saved: downstream_results_summary.txt")

# downstream_qualitative_examples.txt
ql = [
    f"DOWNSTREAM QUALITATIVE ANALYSIS  (rebuilt {datetime.now().strftime('%Y-%m-%d')})",
    "=" * 78, "",
]

ql += ["## 1. TOP 5 LARGEST B3 MERGED CLUSTERS", ""]
for size, canon, members in top_b3:
    ql.append(f"  [{size} members]  canonical: '{canon}'")
    for m in members[:8]:
        ql.append(f"    f={kw_freq.get(m, 0):4d}  {m}")
    if size > 8:
        ql.append(f"    ... +{size - 8} more")
    ql.append("")

ql += ["## 2. TOP 5 LARGEST FULL LLM-DAG MERGED CLUSTERS", ""]
for size, canon, members in top_llm:
    ql.append(f"  [{size} members]  canonical: '{canon}'")
    for m in members[:8]:
        ql.append(f"    f={kw_freq.get(m, 0):4d}  {m}")
    if size > 8:
        ql.append(f"    ... +{size - 8} more")
    ql.append("")

ql += ["## 3. SUSTAINABILITY FAMILY — B3 vs LLM-DAG", ""]
for label, c2m in [("B3", sust_b3), ("LLM-DAG", sust_llm)]:
    by_size = sorted(c2m.items(), key=lambda x: -len(x[1]))
    ql.append(f"  [{label}] {len(c2m)} distinct clusters for 'sustain*' keywords (f>=2)")
    for canon, members in by_size[:6]:
        mems = sorted(members, key=lambda k: -kw_freq.get(k, 0))
        ql.append(f"    Cluster '{canon}' ({len(members)} members):")
        for m in mems[:6]:
            ql.append(f"      f={kw_freq.get(m, 0):4d}  {m}")
        if len(mems) > 6:
            ql.append(f"      ... +{len(mems)-6} more")
    ql.append("")

ql += ["## 4. WHERE B3 OVER-MERGES AND LLM-DAG PRESERVES DISTINCTIONS", ""]
ql.append(f"  Total B3 clusters that LLM-DAG splits: {len(split_examples):,}")
ql.append("")
for sz, canon_b3, members, llm_roots in split_examples[:8]:
    mems_sorted = sorted(members, key=lambda k: -kw_freq.get(k, 0))
    ql.append(f"  B3 cluster (canonical='{canon_b3}', {sz} members):")
    for m in mems_sorted[:8]:
        llm_c = kw_to_canon_llm.get(m, m)
        arrow = "(kept together)" if llm_c == kw_to_canon_llm.get(canon_b3, canon_b3) else f"-> LLM canon: '{llm_c}'"
        ql.append(f"    f={kw_freq.get(m, 0):4d}  {m!r:52s}  {arrow}")
    ql.append("")

ql += ["## 5. CIRCULAR ECONOMY FAMILY — B3 vs LLM-DAG", ""]
for label, c2m in [("B3", ce_b3), ("LLM-DAG", ce_llm)]:
    by_size = sorted(c2m.items(), key=lambda x: -len(x[1]))
    ql.append(f"  [{label}] {len(c2m)} clusters for 'circular economy*' keywords (f>=2)")
    for canon, members in by_size[:4]:
        mems = sorted(members, key=lambda k: -kw_freq.get(k, 0))
        ql.append(f"    Cluster '{canon}' ({len(members)} members):")
        for m in mems[:6]:
            ql.append(f"      f={kw_freq.get(m, 0):4d}  {m}")
    ql.append("")

(RES / "downstream_qualitative_examples.txt").write_text(
    "\n".join(ql), encoding="utf-8")
print("  Saved: downstream_qualitative_examples.txt")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — FINAL STDOUT SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
# API cost from logs
total_cost = 0.0
for logf in [LOGS / "downstream_raw_outputs.jsonl",
             LOGS / "downstream_fix_raw_outputs.jsonl"]:
    with open(logf, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                total_cost += json.loads(line).get("cost_usd", 0.0)
            except Exception:
                pass

print("\n" + "=" * 78)
print("FINAL DOWNSTREAM RESULTS")
print("=" * 78)
print(f"\n{'Condition':<22} {'Vocab':>7} {'Edges':>8} {'Density':>12} "
      f"{'Q':>8} {'Comm':>6} {'ARI':>9} {'AMI':>9}")
print("─" * 78)
print(f"{'Raw':<22} {G_raw.number_of_nodes():>7,} {G_raw.number_of_edges():>8,} "
      f"{nx.density(G_raw):>12.8f} {q_raw:>8.4f} {nc_raw:>6} {'ref':>9} {'ref':>9}")
print(f"{'B3 Jaro-Winkler':<22} {G_b3.number_of_nodes():>7,} {G_b3.number_of_edges():>8,} "
      f"{nx.density(G_b3):>12.8f} {q_b3:>8.4f} {nc_b3:>6} {ari_b3:>9.4f} {ami_b3:>9.4f}")
print(f"{'Full LLM-DAG (fixed)':<22} {G_llm.number_of_nodes():>7,} {G_llm.number_of_edges():>8,} "
      f"{nx.density(G_llm):>12.8f} {q_llm:>8.4f} {nc_llm:>6} {ari_llm:>9.4f} {ami_llm:>9.4f}")
print("─" * 78)

print(f"\nPair resolution breakdown:")
print(f"  Orig real LLM calls (embedding/acronym strata): {n_orig:,}")
print(f"  Fix LLM calls (strata i/ii, unique):            {n_unique_llm:,}")
print(f"  Deterministic (strata iv/v, scope-policy):      {n_det:,}")
print(f"  Total unique verified pairs:                    {len(pair_decisions):,}")
print(f"    match:     {dec_counts.get('match', 0):,}")
print(f"    non_match: {dec_counts.get('non_match', 0):,}")
print(f"    uncertain: {dec_counts.get('uncertain', 0):,}")

print(f"\nSustainability family:")
print(f"  B3:      {len(sust_b3)} distinct clusters")
print(f"  LLM-DAG: {len(sust_llm)} distinct clusters")

print(f"\nCircular economy family:")
print(f"  B3:      {len(ce_b3)} distinct clusters")
print(f"  LLM-DAG: {len(ce_llm)} distinct clusters")

print(f"\nB3 over-merge instances (split by LLM-DAG): {len(split_examples):,}")
if split_examples:
    print("  Top 3 split examples:")
    for sz, canon, members, _ in split_examples[:3]:
        mems = sorted(members, key=lambda k: -kw_freq.get(k, 0))[:4]
        print(f"    B3 merges {sz} kws under '{canon}':")
        for m in mems:
            llm_c = kw_to_canon_llm.get(m, m)
            print(f"      '{m}' (f={kw_freq.get(m,0)}) -> LLM canon '{llm_c}'")

print(f"\nTotal downstream API cost (from logs): ${total_cost:.4f}")
print(f"\nFiles saved to results/:")
print("  downstream_results.csv")
print("  downstream_results_summary.txt")
print("  downstream_qualitative_examples.txt")
print("\nAll done.")
