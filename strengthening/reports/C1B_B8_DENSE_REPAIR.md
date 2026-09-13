# C1B — B8 Dense-Retrieval Repair Report

## 0. Git
Starting commit: `ca147ab`
Ending commit: `dbd1bad`
Branch: `strengthen/m7-2026` throughout, clean before and after

## 1. Frozen B8 specification (verified pre-gold)
- `top_k=5` (default in both `pipeline.py` and `dense_retrieval.py`) and `min_similarity=None` -- confirmed via `git log` to have been committed at `b0fb960`, well BEFORE the gold freeze (`83c46f0`). Not re-selected by looking at benchmark performance.
- Dense model: `sentence-transformers/all-MiniLM-L6-v2` (unchanged).
- Normalisation: lexical route uses `legacy_normalise` (byte-identical after normalisation only); dense route uses raw cosine similarity computed manually (dot product / norms), not `normalize_embeddings=True` at encode time -- unchanged.
- Seed/universe construction, pair orientation/dedup: unchanged (`lexical_anchor`, `union_candidates`, `dedupe_pairs`).
- Deterministic tie behaviour: `numpy.argsort(-similarities, kind="stable")` -- ties broken by pool order. Preserved exactly in the new batched path (verified by equivalence tests).
- **Confirmed distinct from H3's `top_k_per_route=50`** (protocol_v1.yaml, retrieval-audit-specific) -- not conflated with B8's own `top_k=5`.

## 2. Evaluation universe (verified, with a documented gap)
- **CE**: `generate_ce_candidates.build_universe(freq_df, seed=42)` applied to the legacy `concept_harmonisation/data/derived/author_keyword_frequencies.csv` (read-only, hash `8fd003c6...`) → **4,000 keywords** (top 3,500 by frequency + 500 seeded-random low-frequency). Universe hash: `fa78ca42c3390...`.
- **Diabetes**: `generate_diabetes_candidates`'s strict-eligible-keyword frequency table from `strengthening/data_pmc/pmc_diabetes_author_keywords_raw.csv` (hash `c1e5090f...`) → **4,092 keywords**, no subsampling needed. Universe hash: `8e776457b0b4b...`.
- Both are deterministic, pre-existing, pre-gold code paths -- reused verbatim, never reimplemented.
- **Documented gap**: 249/687 (36%) unique CE benchmark strings fall outside the 4,000-item universe, because the legacy generator's separate "structural groups" route (case/plural/initials matching) searched the full, intractable ~55k-keyword universe -- a route B8 has no equivalent of. 0/769 diabetes strings are missing. Reported explicitly, not silently substituted.

## 3. Dense bottleneck profiling
`dense_retrieve(seed, universe, ...)` calls `model.encode([seed, *pool])` -- i.e. re-encodes the (near-)entire universe on **every seed query**. Measured: 414.6ms/seed at a 200-item universe; 4,651ms/seed at a 1,000-item universe (139.5s for just 30 seeds). Extrapolated to the real ~4,000-item universes with ~700-800 seeds: multiple hours. Root cause confirmed to be redundant re-encoding, not redundant model loading (already process-cached) or an un-vectorisable similarity computation.

## 4. Optimisation (algorithm unchanged)
Added `encode_universe_once()` + `dense_retrieve_batch()` to `dense_retrieval.py` as a **pure addition** (0 lines of the existing `dense_retrieve` changed; all 35 pre-existing B8 tests pass unmodified). Encodes the universe once, reuses the matrix per seed, same cosine formula, same stable-sort tie-break, same top-k-then-min_similarity filter order, same rank semantics.

## 5. Equivalence test
7 new tests (`test_dense_retrieval_batch.py`): identical neighbour identities/ordering vs. the original per-seed `dense_retrieve`, across full-universe seeding, `min_similarity` filtering, smaller `top_k`, precomputed embeddings, and a seed-subset case. Measured speedup at 1,000 items: 139.5s → 3.5s for 30 seeds (**~40x**), zero mismatches. All passed -- no divergence requiring a stop/diagnose.

## 6. B8 candidate generation (dense enabled, real universes)
| Domain | Universe | Seeds | Encode | Dense retrieval | Total | Candidates | Reduction ratio | Lexical-only | Dense-only | Both |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CE | 4,000 | 687 | 34.4s | 20.7s | 57.2s | 3,316 | 0.99959 | 0 | 3,230 | 205 |
| Diabetes | 4,092 | 769 | 12.2s | 11.8s | 26.5s | 3,327 | 0.99960 | 0 | 3,703 | 142 |

Candidate sets frozen and SHA-256 hashed BEFORE gold was joined: CE `aa494e5b...`, diabetes `4c0875bb...` (`B8_DENSE_CANDIDATE_GENERATION.json`).

## 7. Final benchmark capture (computed strictly after freezing)
| Partition | N | Gold-match | Gold-match captured | **Benchmark capture rate** |
|---|---:|---:|---:|---:|
| CE400 | 400 | 103 | 29 | **0.2816** |
| Diabetes500 | 500 | 161 | 137 | **0.8509** |
| Pooled900 | 900 | 264 | 166 | **0.6288** |

CE's lower rate is directly explained by the Section 2 universe gap (many CE gold-match pairs involve a string outside the 4,000-item universe and can never be captured). This term is used exclusively as "benchmark capture rate" -- never "pair completeness"/recall.

## 8. Final B8 evaluation logic confirmed
`predict_b8_for_benchmark()` (unchanged from C1, reused verbatim): captured pairs reuse a lookup against an existing B7-over-900 prediction set (none exists yet in this phase, so all 440 captured pairs are correctly left `None`/pending, never fabricated); uncaptured pairs predict non-match structurally. `classify_pair()`/`client.classify()` is never called by this module -- confirmed by code inspection and by synthetic tests (`test_predict_b8_reuses_b7_and_never_calls_anything_for_uncaptured`, pre-existing from C1). **Zero additional paid LLM calls.**

## 9. C1 diagnostic preserved
`B8_BENCHMARK_EVALUATION_STRUCTURAL_STATS.{json,md}` (C1's lexical-only, 72/900-capture result) is **unchanged, untouched, not overwritten** -- it remains available as an internal diagnostic and is explicitly not the final reported result (that role is now held by `B8_FINAL_BENCHMARK_CAPTURE.md`, Section 7 above).

## 10. Safety / tests
- Frozen gold hashes: unchanged (verified before and after).
- Legacy tracked outputs unchanged: `results/tuned_thresholds.json`, `openai_dev_freeze_manifest.json`, `downstream_results_corrected.csv` hashes all match.
- Legacy CE keyword-frequency file (read-only access): unchanged (`8fd003c6...`).
- No H3 working/completed files exist.
- No paid API call: this environment has live `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`, but no code path in this task ever passed `execute_paid=True` or called `B7Client`/`OpenAIClient` for real -- B8's candidate generation is entirely local (embeddings + lexical matching), and the capture computation only performs a dictionary lookup against a (currently empty) B7-prediction map.
- No manuscript edit, no legacy result overwrite, no push.
- Tests: 13 new (7 equivalence + 6 logic/hash), whole suite 440 passed, 0 failures.
- Commit: 8 files changed, `dense_retrieval.py` diff is a pure addition (132 insertions, 0 deletions).

B8-DENSE READINESS: GO
