"""
downstream_deterministic.py
=============================
PHASE 0B / TASK 7 — deterministic-ordering downstream analysis.

Phase 0A discovered that vocab/edges/density reproduce exactly on rerun, but
Louvain modularity/community-count/ARI/AMI do not — and that ARI ranking
between B3 and LLM-DAG reversed on one legitimate same-seed rerun.

Root-cause diagnosis (confirmed by code inspection of the original
scripts/rebuild_downstream.py): `nodes = {c for c, f in c_freq.items() if
f >= freq_thresh}` builds a Python SET, and `G.add_nodes_from(nodes)` then
iterates that set directly. Python set iteration order depends on element
hash values, which for strings are randomised per-process by PYTHONHASHSEED
unless explicitly fixed — so the graph's internal node ordering (and hence
whatever order Louvain's local-moving heuristic visits nodes in) could
differ between runs even with Louvain's own random_state fixed.

By contrast, edge insertion order was ALREADY deterministic in the original
script (`itertools.combinations(sorted(ns), 2)` — `sorted()` fixes it), and
cluster membership is unaffected because union-find's final connected
components do not depend on the order match-edges are processed.

This file changes exactly one thing relative to the original algorithm:
`sorted(...)` is applied wherever a set is turned into a sequence that
determines graph or downstream iteration order. No other logic differs.
The original scripts/rebuild_downstream.py is left completely untouched.

Emits per-condition metrics as JSON to stdout (numbers only — no keyword
strings), so it is safe to invoke from a subprocess harness and capture.
"""
import argparse
import itertools
import json
import os
import pickle
import sys
from pathlib import Path

import networkx as nx
from sklearn.metrics import adjusted_rand_score, adjusted_mutual_info_score


def build_coword_network_deterministic(kw_to_canon, kw_to_eids, article_to_kws, articles, freq_thresh=5):
    canon_to_eids = {}
    # `article_to_kws` iteration is a dict -> insertion-order-preserving (deterministic
    # regardless of hash seed, per CPython 3.7+ dict semantics). `kws` is a list ->
    # deterministic. No unordered set is iterated in this loop.
    for eid in articles:
        for k in article_to_kws[eid]:
            c = kw_to_canon.get(k, k)
            canon_to_eids.setdefault(c, set()).add(eid)
    c_freq = {c: len(e) for c, e in canon_to_eids.items()}

    # FIX: sort before turning the filtered set into the graph's node insertion order.
    nodes_sorted = sorted(c for c, f in c_freq.items() if f >= freq_thresh)
    nodes_set = frozenset(nodes_sorted)   # O(1) membership test only, never iterated

    G = nx.Graph()
    G.add_nodes_from(nodes_sorted)   # deterministic node insertion order

    for eid in articles:              # `articles` is a list -> deterministic
        kws = article_to_kws[eid]     # list -> deterministic
        ns = sorted({kw_to_canon.get(k, k) for k in kws if kw_to_canon.get(k, k) in nodes_set})
        for a, b in itertools.combinations(ns, 2):   # already sorted -> deterministic
            if G.has_edge(a, b):
                G[a][b]["weight"] += 1
            else:
                G.add_edge(a, b, weight=1)
    return G, c_freq, nodes_set


def louvain_partition(G, seed):
    import community as community_louvain
    part = community_louvain.best_partition(G, resolution=1.0, random_state=seed)
    q = community_louvain.modularity(part, G)
    nc = len(set(part.values()))
    return part, q, nc


def compute_ari_ami(nodes_raw, part_raw, kw_to_canon_harm, part_harm):
    common = sorted({k for k in nodes_raw if kw_to_canon_harm.get(k, k) in part_harm})
    y_raw = [part_raw.get(k, -1) for k in common]
    y_harm = [part_harm.get(kw_to_canon_harm.get(k, k), -1) for k in common]
    return (adjusted_rand_score(y_raw, y_harm), adjusted_mutual_info_score(y_raw, y_harm), len(common))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True, help="Path to the pickle from materialize_downstream_cache.py")
    ap.add_argument("--louvain-seed", type=int, default=42)
    args = ap.parse_args()

    with open(args.cache, "rb") as f:
        cache = pickle.load(f)

    all_kws = cache["all_kws"]
    kw_to_eids = cache["kw_to_eids"]
    article_to_kws = cache["article_to_kws"]
    articles = cache["articles"]

    results = {"python_hashseed": os.environ.get("PYTHONHASHSEED", "not set"),
               "louvain_seed": args.louvain_seed, "conditions": {}}

    G_raw, _, nodes_raw = build_coword_network_deterministic(cache["kw_to_canon_raw"], kw_to_eids, article_to_kws, articles)
    part_raw, q_raw, nc_raw = louvain_partition(G_raw, args.louvain_seed)
    results["conditions"]["raw"] = {
        "vocab": G_raw.number_of_nodes(), "edges": G_raw.number_of_edges(),
        "density": nx.density(G_raw), "modularity_q": q_raw, "n_communities": nc_raw,
        "ari": None, "ami": None,
    }

    G_b3, _, nodes_b3 = build_coword_network_deterministic(cache["kw_to_canon_b3"], kw_to_eids, article_to_kws, articles)
    part_b3, q_b3, nc_b3 = louvain_partition(G_b3, args.louvain_seed)
    ari_b3, ami_b3, n_b3 = compute_ari_ami(nodes_raw, part_raw, cache["kw_to_canon_b3"], part_b3)
    results["conditions"]["b3_jaro_winkler"] = {
        "vocab": G_b3.number_of_nodes(), "edges": G_b3.number_of_edges(),
        "density": nx.density(G_b3), "modularity_q": q_b3, "n_communities": nc_b3,
        "ari": ari_b3, "ami": ami_b3, "ari_ami_overlap": n_b3,
    }

    G_llm, _, nodes_llm = build_coword_network_deterministic(cache["kw_to_canon_llm"], kw_to_eids, article_to_kws, articles)
    part_llm, q_llm, nc_llm = louvain_partition(G_llm, args.louvain_seed)
    ari_llm, ami_llm, n_llm = compute_ari_ami(nodes_raw, part_raw, cache["kw_to_canon_llm"], part_llm)
    results["conditions"]["full_llm_dag"] = {
        "vocab": G_llm.number_of_nodes(), "edges": G_llm.number_of_edges(),
        "density": nx.density(G_llm), "modularity_q": q_llm, "n_communities": nc_llm,
        "ari": ari_llm, "ami": ami_llm, "ari_ami_overlap": n_llm,
    }

    print(json.dumps(results))


if __name__ == "__main__":
    main()
