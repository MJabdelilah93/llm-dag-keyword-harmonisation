"""
run_louvain_sensitivity.py
=============================
PHASE 0B / TASK 9 — community-detection SEED SENSITIVITY, separated from
REPRODUCIBILITY (Task 8). Task 8 established that, once graph insertion is
made deterministic, identical inputs + a fixed Louvain random_state produce
identical outputs regardless of PYTHONHASHSEED. This script instead asks a
different question: how much do the reported metrics vary purely because
Louvain's OWN algorithmic seed changes, on the SAME deterministic graphs?

Builds each condition's graph once (deterministic ordering, from Task 7's
implementation) and re-runs Louvain community detection under random_state
0-49 on that same fixed graph. For each seed, Raw/B3/LLM-DAG are all
re-partitioned at that seed so ARI/AMI comparisons are seed-matched pairs,
not comparing a seed-42 Raw partition against an arbitrary-seed harmonised
partition.

Writes results/current_paper/downstream_seed_sensitivity.csv (numbers only).
"""
import csv
import pathlib
import pickle
import statistics
import sys

import networkx as nx
from sklearn.metrics import adjusted_rand_score, adjusted_mutual_info_score

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from downstream_deterministic import build_coword_network_deterministic, compute_ari_ami

REPO = pathlib.Path(__file__).resolve().parents[2]
CACHE = REPO / "restricted_local" / "downstream_cache.pkl"
OUT_CSV = REPO / "results" / "current_paper" / "downstream_seed_sensitivity.csv"

N_SEEDS = 50


def louvain_partition(G, seed):
    import community as community_louvain
    part = community_louvain.best_partition(G, resolution=1.0, random_state=seed)
    q = community_louvain.modularity(part, G)
    nc = len(set(part.values()))
    return part, q, nc


def main():
    if not CACHE.exists():
        sys.exit(f"ERROR: cache not found at {CACHE}")
    with open(CACHE, "rb") as f:
        cache = pickle.load(f)

    all_kws = cache["all_kws"]
    kw_to_eids = cache["kw_to_eids"]
    article_to_kws = cache["article_to_kws"]
    articles = cache["articles"]

    # Build each condition's graph ONCE — deterministic ordering (Task 7),
    # so this is a fair "same graph, different Louvain seed" experiment.
    G_raw, _, nodes_raw = build_coword_network_deterministic(cache["kw_to_canon_raw"], kw_to_eids, article_to_kws, articles)
    G_b3, _, nodes_b3 = build_coword_network_deterministic(cache["kw_to_canon_b3"], kw_to_eids, article_to_kws, articles)
    G_llm, _, nodes_llm = build_coword_network_deterministic(cache["kw_to_canon_llm"], kw_to_eids, article_to_kws, articles)
    print(f"Graphs built once: raw={G_raw.number_of_nodes()}n/{G_raw.number_of_edges()}e "
          f"b3={G_b3.number_of_nodes()}n/{G_b3.number_of_edges()}e "
          f"llm={G_llm.number_of_nodes()}n/{G_llm.number_of_edges()}e")

    rows = []
    for seed in range(N_SEEDS):
        part_raw, q_raw, nc_raw = louvain_partition(G_raw, seed)
        part_b3, q_b3, nc_b3 = louvain_partition(G_b3, seed)
        part_llm, q_llm, nc_llm = louvain_partition(G_llm, seed)
        ari_b3, ami_b3, _ = compute_ari_ami(nodes_raw, part_raw, cache["kw_to_canon_b3"], part_b3)
        ari_llm, ami_llm, _ = compute_ari_ami(nodes_raw, part_raw, cache["kw_to_canon_llm"], part_llm)
        rows.append({"louvain_seed": seed,
                      "raw_q": q_raw, "raw_comm": nc_raw,
                      "b3_q": q_b3, "b3_comm": nc_b3, "b3_ari": ari_b3, "b3_ami": ami_b3,
                      "llm_q": q_llm, "llm_comm": nc_llm, "llm_ari": ari_llm, "llm_ami": ami_llm,
                      "llm_minus_b3_ari": ari_llm - ari_b3, "llm_minus_b3_ami": ami_llm - ami_b3,
                      "llm_beats_b3_ari": ari_llm > ari_b3, "llm_beats_b3_ami": ami_llm > ami_b3})
        if seed % 10 == 0:
            print(f"seed={seed}: llm_ari={ari_llm:.4f} b3_ari={ari_b3:.4f} llm_ami={ami_llm:.4f} b3_ami={ami_b3:.4f}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows: w.writerow(r)

    def stats(key):
        vals = [r[key] for r in rows]
        return {"median": statistics.median(vals), "min": min(vals), "max": max(vals),
                "q1": statistics.quantiles(vals, n=4)[0], "q3": statistics.quantiles(vals, n=4)[2]}

    summary = {
        "n_seeds": N_SEEDS,
        "raw_q": stats("raw_q"), "raw_comm": stats("raw_comm"),
        "b3_q": stats("b3_q"), "b3_comm": stats("b3_comm"), "b3_ari": stats("b3_ari"), "b3_ami": stats("b3_ami"),
        "llm_q": stats("llm_q"), "llm_comm": stats("llm_comm"), "llm_ari": stats("llm_ari"), "llm_ami": stats("llm_ami"),
        "paired_diff_ari": stats("llm_minus_b3_ari"), "paired_diff_ami": stats("llm_minus_b3_ami"),
        "proportion_seeds_llm_beats_b3_ari": sum(r["llm_beats_b3_ari"] for r in rows) / N_SEEDS,
        "proportion_seeds_llm_beats_b3_ami": sum(r["llm_beats_b3_ami"] for r in rows) / N_SEEDS,
    }
    import json
    print(json.dumps(summary, indent=2, default=str))
    with open(REPO / "results" / "current_paper" / "downstream_seed_sensitivity_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote: {OUT_CSV}")


if __name__ == "__main__":
    main()
