"""
materialize_downstream_cache.py
=================================
PHASE 0B / TASK 7-9 support — one-time, read-only materialisation of the
corpus + frozen decision structures needed for the downstream determinism
tests, so that the expensive corpus/JSONL parsing (~6 min) does not have to
be repeated inside each of the 20+ fresh subprocesses that Task 8 requires.

This caching is scientifically neutral: the cached structures (all_kws,
kw_freq, kw_to_eids, article_to_kws, articles, and the three precomputed
kw_to_canon_* maps) are built from deterministic dict/list operations over
files read in a fixed order — none of it depends on PYTHONHASHSEED. Only
the LATER step of turning these into a graph (in downstream_deterministic.py)
is hash-seed-sensitive, and that step is NOT cached — it re-runs fresh in
every subprocess, which is exactly what Task 8 needs to test.

Cluster/canonical-label assignment is also precomputed once here rather than
per hash-seed run, because Phase 0A/0B already established (and this
repository's own union-find mathematics guarantees) that cluster membership
is independent of iteration order — only the graph-construction/Louvain
layer is order-sensitive. Precomputing it does not hide anything Task 8 is
meant to detect.

Reads the historical evidence tree read-only. Writes a pickle containing
real Scopus-derived keyword strings to restricted_local/ only.
"""
import argparse
import itertools
import json
import os
import pickle
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd
import jellyfish


def normalise(s):
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"\s+", " ", s.lower().strip())


def cpair(a, b):
    return (min(a, b), max(a, b))


def union_find_clusters(all_kws, match_edges, kw_to_eids):
    parent = {}
    def find(x):
        if x not in parent: parent[x] = x
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        px, py = find(x), find(y)
        if px != py: parent[px] = py
    for (a, b) in match_edges:
        if a in kw_to_eids and b in kw_to_eids: union(a, b)
    clusters = defaultdict(list)
    for k in all_kws: clusters[find(k)].append(k)
    return clusters


def make_canon_map(clusters, kw_freq):
    kw_to_canon = {}
    for root, members in clusters.items():
        canon = max(members, key=lambda k: kw_freq.get(k, 0))
        for m in members: kw_to_canon[m] = canon
    return kw_to_canon


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"))
    ap.add_argument("--output", default=None)
    args = ap.parse_args()
    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")

    evidence_root = Path(args.evidence_root)
    intern = evidence_root / "data" / "interim" / "scopus_ce_merged_deduped.csv"
    logs = evidence_root / "results" / "llm_logs"

    repo_root = Path(__file__).resolve().parents[2]
    out_path = Path(args.output) if args.output else repo_root / "restricted_local" / "downstream_cache.pkl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df_c = pd.read_csv(intern, usecols=["EID", "Author Keywords"], encoding="utf-8")
    df_c = df_c[["EID", "Author Keywords"]]
    kw_to_eids = defaultdict(set)
    article_to_kws = {}
    for row in df_c.itertuples(index=False):
        eid, cell = str(row[0]), row[1]
        if pd.isna(cell) or not str(cell).strip():
            article_to_kws[eid] = []
            continue
        kws = [k.strip() for k in str(cell).split(";") if k.strip()]
        article_to_kws[eid] = kws
        for k in kws: kw_to_eids[k].add(eid)
    all_kws = list(kw_to_eids.keys())
    kw_freq = {k: len(v) for k, v in kw_to_eids.items()}
    assert len(all_kws) == 55425

    pair_decisions = {}
    with open(logs / "downstream_raw_outputs.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                if e.get("prompt_hash", "") in ("auto_accept_high_jw", "auto_reject_low_jw"): continue
                ka, kb = e.get("keyword_a", ""), e.get("keyword_b", "")
                if ka and kb: pair_decisions[cpair(ka, kb)] = e.get("decision", "uncertain")
            except Exception: pass
    with open(logs / "downstream_fix_raw_outputs.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                if e.get("error") == "api_failed": continue
                ka, kb = e.get("keyword_a", ""), e.get("keyword_b", "")
                if ka and kb: pair_decisions[cpair(ka, kb)] = e.get("decision", "uncertain")
            except Exception: pass
    with open(logs / "downstream_deterministic_completions.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                ka, kb = e.get("keyword_a", ""), e.get("keyword_b", "")
                if ka and kb:
                    p = cpair(ka, kb)
                    if p not in pair_decisions: pair_decisions[p] = e.get("decision", "match")
            except Exception: pass
    match_pairs = {k for k, d in pair_decisions.items() if d == "match"}

    B3_THRESH = 0.92
    norm_map = {k: normalise(k) for k in all_kws}
    n2first = {}
    for k in all_kws:
        n = norm_map[k]
        if n not in n2first: n2first[n] = k
    b3_match = set()
    norm_to_grp = defaultdict(list)
    for k in all_kws: norm_to_grp[norm_map[k]].append(k)
    for n, grp in norm_to_grp.items():
        if len(grp) < 2: continue
        for a, b in itertools.combinations(grp, 2): b3_match.add(cpair(a, b))
    freq2_kws = [k for k in all_kws if kw_freq.get(k, 0) >= 2]
    prefix_grp = defaultdict(list)
    for k in freq2_kws:
        n = norm_map[k]
        if len(n) >= 3: prefix_grp[n[:3]].append((k, n))
    for pfx, grp in prefix_grp.items():
        for i, (ka, na) in enumerate(grp):
            for kb, nb in grp[i+1:]:
                if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH: b3_match.add(cpair(ka, kb))
    PUNCT = re.compile(r"[-/(). ]")
    pmap = defaultdict(list)
    for k in all_kws:
        pn = PUNCT.sub("", norm_map[k])
        if len(pn) >= 3: pmap[pn].append(k)
    for pn, grp in pmap.items():
        if len(grp) < 2: continue
        for a, b in itertools.combinations(grp, 2):
            na, nb = norm_map[a], norm_map[b]
            if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH: b3_match.add(cpair(a, b))
    for na, ka in n2first.items():
        for suf in ["s", "es"]:
            nb = na + suf
            if nb in n2first and nb != na:
                if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH: b3_match.add(cpair(ka, n2first[nb]))
        if na.endswith("ies") and len(na) > 4:
            nb = na[:-3] + "y"
            if nb in n2first:
                if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH: b3_match.add(cpair(ka, n2first[nb]))

    kw_to_canon_raw = {k: k for k in all_kws}
    clusters_b3 = union_find_clusters(all_kws, b3_match, kw_to_eids)
    kw_to_canon_b3 = make_canon_map(clusters_b3, kw_freq)
    clusters_llm = union_find_clusters(all_kws, match_pairs, kw_to_eids)
    kw_to_canon_llm = make_canon_map(clusters_llm, kw_freq)

    cache = {
        "all_kws": all_kws,
        "kw_freq": kw_freq,
        "kw_to_eids": dict(kw_to_eids),
        "article_to_kws": article_to_kws,
        "articles": list(article_to_kws.keys()),
        "kw_to_canon_raw": kw_to_canon_raw,
        "kw_to_canon_b3": kw_to_canon_b3,
        "kw_to_canon_llm": kw_to_canon_llm,
    }
    with open(out_path, "wb") as f:
        pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Cache written: {out_path} ({out_path.stat().st_size:,} bytes)")
    print(f"all_kws={len(all_kws)} articles={len(cache['articles'])} "
          f"clusters_b3={len(clusters_b3)} clusters_llm={len(clusters_llm)}")


if __name__ == "__main__":
    main()
