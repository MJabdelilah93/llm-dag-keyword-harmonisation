# C1 Frozen-Inference Preflight Report

## 1. Git
Starting commit: `47a2b79`
Ending commit: `b6f97be`
Working tree: clean before, clean after (only intended files committed)
Branch: `strengthen/m7-2026` throughout

## 2. Gold hash verification
- `PRIMARY_GOLD_900_FINAL.xlsx`: `bb90618580e944e54904c231efca83f50eebc1ef5eb4ea7f0fd8e803adbbec0a` -- MATCH
- `PRIMARY_GOLD_900_FINAL.csv`: `89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479` -- MATCH
- Re-verified again after all work: unchanged

## 3. Frozen thresholds and exact provenance
| Parameter | Value | Source | Hash |
|---|---|---|---|
| Primary M7 guard threshold | 0.50 | `results/tuned_thresholds.json` | `87715a44...849836` |
| B3 Jaro-Winkler | 0.92 | same file | same |
| B4 TF-IDF | 0.68 | same file | same |
| B5 Embedding | 0.85 | same file | same |
| OpenAI guard threshold | 0.80 | `results/current_paper/phase1b/openai_dev_freeze_manifest.json` | `499c3a27...7673d87` |

All read and hash-checked at run time; none recomputed against the new 900.

## 4. B1-B5 local execution status and prediction counts
Executed for real (deterministic, free). CE400=400, diabetes500=500, pooled900=900 predictions each, all 5 methods. Pooled F1: B1=0.4286, B2=0.4286, B3=0.8740, B4=0.7650, B5=0.8637 (full table: `B1_B5_FROZEN_INFERENCE_EVALUATION.md`). Selective-prediction demonstrated (margin-based proxy confidence, explicitly not genuine model confidence).

## 5. Primary M7 paid-run readiness
`primary_m7_runner.py`: dry-run confirms exactly 1 Anthropic request/pair, 900 total for the new partitions. Frozen prompt/config/threshold loaded and hash-verified. NOT executed for real.

## 6. B6 paid-run readiness
`b6_runner.py`: dry-run confirms exactly 1 request/pair, 900 total. Exact legacy prompt/parsing reused verbatim. NOT executed for real.

## 7. B7 real-client implementation status
`B7Client.classify(a, b, execute_paid=False)` (new keyword-only parameter, default preserves the prior unconditional raise for every existing call site, including B8's). `execute_paid=True` delegates to a new, lazily-imported `real_client.py` (fails safely, before any import, if `ANTHROPIC_API_KEY` is absent). All 86 pre-existing B7/B8 tests pass unmodified; 6 new mock-only tests added. NOT executed for real.

## 8. B8 corrected benchmark-evaluation status and zero-duplicate-call confirmation
`b8_benchmark_eval.py` implemented and run for real (lexical-only; dense retrieval found impractically slow at this universe size in this session -- see report's performance note, a genuine follow-up, not a fabricated result). 72/900 benchmark pairs captured. Confirmed by code inspection and a synthetic test: captured pairs reuse an existing B7 prediction; uncaptured pairs predict non-match structurally; `classify_pair()`/`client.classify()` is never called by this module -- **zero additional LLM calls**.

## 9. OpenAI frozen-inference readiness
`openai_second_provider_runner.py`: dry-run confirms exactly 1 request/pair, 900 total, frozen 0.80 threshold (hash-verified against its source manifest, aborts on mismatch). NOT executed for real.

## 10. Exact static paid-request matrix
| Method | New requests | Provider |
|---|---:|---|
| Primary M7 | 900 | Anthropic |
| B6 | 900 | Anthropic |
| B7 | 900 | Anthropic |
| B8 | 0 | (reuses B7) |
| OpenAI | 900 | OpenAI |

**Total: 2,700 Anthropic + 900 OpenAI** -- matches the task's expected logical design exactly, verified from code (not assumed). `pooled900` is the union of ce400+diabetes500, not an additional 900.

## 11. Historical token-usage statistics
Real, recorded AGGREGATE totals only (no per-call arrays survive locally):
- Anthropic, 5 real reruns (149 pairs each, 745 total): mean 422.7 input / 94.7 output tokens per pair. Per-call percentiles NOT available locally.
- OpenAI, 2 real runs (351+149=500 total): mean 442.9 input / 57.7 output tokens per pair. Per-call percentiles NOT available locally.
- B6: no real token/cost data survives in this worktree at all (Zenodo-only); estimated only via the primary workflow's rate as an explicitly-labelled proxy.

## 12. Cost estimate (current $1/$5 Claude, $0.20/$1.25 GPT-5.4-nano rates)
| Method | Expected | Conservative (1.5x) | Worst-case (2x) |
|---|---:|---:|---:|
| Primary M7 | $0.8066 | $1.2099 | $1.6132 |
| B6 (proxy) | $0.8066 | $1.2099 | $1.6132 |
| B7 (proxy) | $0.8066 | $1.2099 | $1.6132 |
| OpenAI | $0.1446 | $0.2170 | $0.2893 |
| B8 | $0.0000 | -- | -- |

**Combined expected: $2.5644** for all four paid methods across 900 new pairs. 1.5x/2x are explicit heuristic safety margins (no real per-call percentile exists locally to derive a true p95), clearly labelled as such, not measured.

## 13. Selective-prediction readiness
`strengthening/metrics/selective.py` demonstrated working end-to-end on B1-B5's real predictions using a margin-based proxy confidence (`|similarity-threshold|`), explicitly labelled as non-genuine. The scientifically meaningful analysis awaits real LLM-based predictions (genuine guard confidence). `conformal_prediction.py` remains un-promoted. 7 gold-uncertain labels noted as too few for a stable headline estimate.

## 14. Observed-transitive-contradiction diagnostic readiness and available triangle count
Implemented and run for real on B1-B5. **6 fully-observed closed triangles** found in the 900-pair sample -- below the pre-set threshold of 10, so no consistency analysis was forced on them (reported as-is). Contradiction diagnostic itself: B1/B2 = 0; B3 = 13/629 (2.07%); B4 = 54/629 (8.59%); B5 = 7/629 (1.11%) gold non-match pairs incorrectly connected -- all direct errors, zero transitive-only contradictions at this scale.

## 15. CE downstream reproducibility result
All 5 replay scripts confirmed zero-API-call by AST-level source inspection. **Honest finding: a live replay cannot be executed in this specific worktree** -- required restricted inputs (`data/interim/scopus_ce_merged_deduped.csv`, 3 downstream JSONL logs, `restricted_local/downstream_cache.pkl`) are absent (Zenodo-only or never materialized here). The already-committed authoritative corrected results remain unchanged and are confirmed internally consistent (`corrected_maps_manifest.json` -- `all_checks_pass: true`).

## 16. Biomedical release-precheck result
497 CC BY / 3 CC0 accounting reconfirmed exactly. Result: `READY_FOR_FUTURE_RELEASE_DECISION`. Safe/methodology-internal/requires-review field lists produced (`BIOMEDICAL_RELEASE_MANIFEST.md`). **No publication or upload performed.**

## 17. Tests
New tests: 42 (36 in `test_c1_frozen_inference_preflight.py` + 6 in `test_b7_real_client.py`)
Whole suite: 427 passed
Failures: 0 (one real, unrelated finding caught and fixed: a leftover zero-progress H3 retrieval working file from a prior task's smoke test, confirmed zero labels, then removed)

## 18. Files created/changed
31 files (commit `b6f97be`): 2 modified (`b7_direct_relation/client.py`, `BIOMEDICAL_RELEASE_READINESS.md` -- timestamp-only regeneration, content otherwise identical), 29 new (14 `strengthening/experiments/*.py` modules incl. `__init__.py`, `real_client.py`, 12 new tracked report files, 2 new test files). No restricted data, no working/completed human files, no logs, no context files, and no restricted strings were committed (all under `strengthening/restricted_local/`, gitignored, verified).

## 19. Confirmations
- **No paid call occurred**: verified both structurally (every `execute_paid=True` in real code is inside a docstring or a default-`False` parameter declaration; the ONLY actual `execute_paid=True` invocations are in 2 tests, both with the transport fully mocked via `sys.modules` injection and the API key monkeypatched to a fake value) and by audit of every command actually run this session (no `--execute-paid` flag ever passed).
- **Important disclosure**: this environment has live `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` set. Safety therefore rests entirely on the explicit `execute_paid` gate, exactly as designed -- confirmed to hold throughout.
- **No H3 label exists**: confirmed; one leftover zero-progress `ANTHROPIC_1_RETRIEVAL_WORKING.xlsx` from a prior task's smoke test (0 non-blank labels) was found and removed.
- **Frozen gold hashes unchanged**: confirmed (Section 2).
- **Legacy tracked outputs unchanged**: confirmed (`tuned_thresholds.json`, `openai_dev_freeze_manifest.json`, `downstream_results_corrected.csv` hashes all match pre-task values).
- **No manuscript file changed**: confirmed (manuscript is out of scope for this repo entirely, per `strengthening/README.md`; no manuscript-named file appears anywhere in this session's diff).
- **No remote push occurred**: confirmed.

PAID-RUN READINESS: GO
