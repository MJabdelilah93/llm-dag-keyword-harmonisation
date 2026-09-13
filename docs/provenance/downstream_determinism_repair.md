# Downstream Determinism Repair (Tasks 7-9)

**Status: root cause diagnosed and fixed; reproducibility verified;
algorithmic sensitivity separately characterised. Original implementation
(`scripts/rebuild_downstream.py`) left completely untouched.**

## Task 7 — Root cause and fix

**Environment at time of repair (2026-08-24):** Python 3.12.6, networkx
3.6.1, python-louvain 0.16, scikit-learn 1.8.0, numpy 2.4.2, pandas 3.0.1.
**None of these versions are pinned in `requirements.txt`**, and the exact
versions used for the original 2026-04 run are unknown (no lockfile exists)
— see `docs/environment/current_paper_environment.md` for the
ORIGINAL-VERSION-UNKNOWN vs. CURRENT-PIN distinction.

**Diagnosis.** In the original `scripts/rebuild_downstream.py`,
`build_coword_network()` computes `nodes = {c for c, f in c_freq.items() if
f >= freq_thresh}` — a Python **set** — and then calls
`G.add_nodes_from(nodes)`, iterating that set directly. Python set iteration
order for strings depends on their hash values, which are randomised
per-process by `PYTHONHASHSEED` unless explicitly fixed. Edge insertion was
already deterministic (`itertools.combinations(sorted(ns), 2)`), and cluster
membership is unaffected by iteration order (a mathematical property of
union-find) — which is exactly why Phase 0A found vocab/edges/density
reproduced exactly while modularity/community-count/ARI/AMI did not.

**Fix.** `scripts/current_paper/downstream_deterministic.py` changes exactly
one thing: `nodes_sorted = sorted(c for c, f in c_freq.items() if f >=
freq_thresh)`, then `G.add_nodes_from(nodes_sorted)`. Louvain's own
`random_state` parameter is passed explicitly throughout (already true of
the original). No other logic differs from `scripts/rebuild_downstream.py`.

## Task 8 — Hash-seed reproducibility test

20 fresh subprocesses, `PYTHONHASHSEED` = 0 through 19, Louvain
`random_state` fixed at 42 throughout. Each subprocess independently loads
the frozen decision logs (via a shared, order-neutral pickle cache — see
`scripts/current_paper/materialize_downstream_cache.py`) and rebuilds all
three condition graphs from scratch.

| Condition | Runs | Distinct results | Fully identical? |
|---|---|---|---|
| Raw | 20 | 1 | ✅ |
| B3 Jaro-Winkler | 20 | 1 | ✅ |
| Full LLM-DAG | 20 | 1 | ✅ |

**Result: `ALL_CONDITIONS_FULLY_REPRODUCIBLE = true`.** Every one of
vocab, edges, density, modularity Q, community count, ARI and AMI was
bit-identical across all 20 hash seeds for all three conditions. The
sorted-insertion fix fully eliminates the hash-seed sensitivity found in
Phase 0A. Full per-run data: `results/current_paper/hashseed_reproducibility_test.csv`;
machine-readable verdict: `results/current_paper/hashseed_reproducibility_summary.json`.

## Task 9 — Louvain seed sensitivity (a different question)

With graph construction now deterministic, a separate question remains:
how much do Q/community-count/ARI/AMI vary purely because Louvain's *own*
algorithmic seed changes? Each condition's graph was built exactly once
(deterministic ordering) and re-partitioned under Louvain `random_state`
0 through 49 — 50 seed-matched triples (Raw/B3/LLM-DAG all repartitioned at
the same seed per iteration, so ARI/AMI comparisons are paired, not
mismatched).

| Metric | B3 median (IQR) | LLM-DAG median (IQR) | LLM &gt; B3? |
|---|---|---|---|
| Modularity Q | 0.2175 (0.2161-0.2185) | 0.2361 (0.2348-0.2372) | **100% of seeds** — ranges do not overlap at all (B3 max 0.2203 &lt; LLM-DAG min 0.2302) |
| Community count | 5 (5-6) | 5 (5-5) | not a directional claim |
| ARI vs. Raw | 0.2011 (0.1940-0.2149) | 0.2024 (0.1945-0.2193) | **56% of seeds** — ranges heavily overlap; paired difference median +0.0024, IQR [-0.0104, +0.0177] straddles zero |
| AMI vs. Raw | 0.2011 (0.1924-0.2128) | 0.2197 (0.2128-0.2327) | **84% of seeds**; paired difference median +0.0206, IQR [+0.0086, +0.0292] — mostly positive, small negative tail |

Full distribution: `results/current_paper/downstream_seed_sensitivity.csv`;
summary statistics: `results/current_paper/downstream_seed_sensitivity_summary.json`.

### Claim classification

| Downstream claim | Classification | Basis |
|---|---|---|
| LLM-DAG preserves more distinct vocabulary than B3 (3,464 vs. 2,880) | **ROBUST** | Purely a function of deterministic clustering; identical on every run and every seed by construction |
| LLM-DAG produces higher network modularity (Q) than B3 | **ROBUST** | Zero overlap across 50 Louvain seeds |
| LLM-DAG's community structure is better aligned with the raw literature (AMI) | **MOSTLY ROBUST** | LLM-DAG wins 84% of seeds; median difference clearly positive, but not universal — report as a distribution, not a single point estimate |
| LLM-DAG's community structure is better aligned with the raw literature (ARI) | **NOT SUPPORTED** | LLM-DAG wins only 56% of seeds (statistically indistinguishable from a coin flip at this sample size); paired-difference IQR straddles zero |

**Recommendation:** retain the vocabulary-preservation and modularity claims
as reported. De-emphasise or remove the ARI-based directional claim — it is
not robust to community-detection stochasticity, and the manuscript should
not select a favourable seed to preserve it. If AMI is retained, report it
as a median with an interquartile range (e.g. "AMI = 0.220, IQR
[0.213, 0.233], vs. B3 AMI = 0.201, IQR [0.192, 0.213], across 50
Louvain seeds") rather than the single point estimates currently in
`results/downstream_results.csv`.

No significance test was mechanically applied to these paired seed
differences — with only-algorithmic (not sampling) repetition across 50
correlated seeds on the same underlying data, a formal p-value would not
answer the scientific question asked here (whether the claim is
seed-robust), so the classification above is made directly from the
distributions and win-proportions.
