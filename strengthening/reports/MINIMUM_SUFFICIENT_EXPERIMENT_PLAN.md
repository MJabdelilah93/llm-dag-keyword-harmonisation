# M7 minimum-sufficient strengthened experiment plan

This is an EXECUTION SPECIFICATION for the remaining M7 strengthening
phase, not manuscript prose. It documents, for each remaining
experiment: exact inputs, exact scripts/modules, exact frozen
configuration and its provenance, expected outputs, paid/free status,
and the no-retuning / no-H3 guardrails that apply throughout.

## 1. Datasets and hashes

| Dataset | N | Role | Hash / provenance |
|---|---:|---|---|
| Legacy CE development | 351 | tuning only, never touched again | `frozen_dev_set_sha256: d5713c7974cd6c8fe88633132c9c07b816a9f688f2614e12b02f12dbc4dd282e` (Zenodo-hosted, restricted) |
| Legacy CE held-out test | 149 | legacy held-out, unchanged | `results/test_predictions.csv` (149 data rows, confirmed by direct count) |
| Prospective CE | 400 | new held-out | `PRIMARY_GOLD_900_FINAL.{xlsx,csv}`, domain=circular_economy |
| Prospective diabetes | 500 | new held-out | `PRIMARY_GOLD_900_FINAL.{xlsx,csv}`, domain=biomedical_diabetes_mellitus |
| **Total held-out** | **1,049** | 149 + 400 + 500 | |
| **Total labelled corpus** | **1,400** | 351 + 1,049 | |

Frozen prospective gold (verified before every run in this phase):

- `PRIMARY_GOLD_900_FINAL.xlsx` -- `bb90618580e944e54904c231efca83f50eebc1ef5eb4ea7f0fd8e803adbbec0a`
- `PRIMARY_GOLD_900_FINAL.csv` -- `89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479`

Frozen-inference input builder: `strengthening/experiments/frozen_inputs.py` -- reads ONLY pair_id/domain/string_a/string_b from the gold CSV (never any gold-derived column), aborts on hash mismatch, and validates CE400=400 / diabetes500=500 / pooled900=900, zero duplicates, zero missing strings, CE/diabetes disjoint, pooled = exact union.

## 2. Legacy development vs. held-out separation (hard rule)

The 351-pair legacy development set is the ONLY data any threshold, prompt, or hyperparameter in this plan was ever tuned against. The 900 new prospective pairs (and the 149 legacy held-out pairs) are evaluation-only, forever. No script in this plan re-runs a threshold search against the new 900 -- every threshold below is READ from a historical frozen artefact and hash-verified before use, never recomputed here.

## 3. Frozen thresholds/configuration (exact provenance)

| Parameter | Value | Source file | Hash |
|---|---|---|---|
| Primary M7 guard confidence threshold | 0.50 | `results/tuned_thresholds.json` | `87715a443597ffa697551968d3a5784d4c4978fb539087cc94bdce7230849836` |
| B3 Jaro-Winkler threshold | 0.92 | same file | same hash |
| B4 TF-IDF char-ngram threshold | 0.68 | same file | same hash |
| B5 sentence-embedding threshold | 0.85 | same file | same hash |
| OpenAI second-provider guard threshold | 0.80 | `results/current_paper/phase1b/openai_dev_freeze_manifest.json` | hash-verified at read time in `openai_second_provider_runner.py` |
| B7 relation labels/prompt | fixed 4-way (same_as/broader/narrower/other), no threshold | `strengthening/baselines/b7_direct_relation/prompt_builder.py` | n/a (categorical, not thresholded) |
| B8 retrieval config | `embedding_model=all-MiniLM-L6-v2`, default `top_k=5` | `strengthening/config/protocol_v1.yaml` + `pipeline.py` defaults | unchanged |
| B1/B2 | no tuning (exact / normalised exact match) | n/a | n/a |

Model configuration (unchanged, `configs/model_config.yaml`): `claude-haiku-4-5-20251001`, temperature 0, max_tokens 256. Frozen prompts: `prompts/v1.0.0/system_prompt.txt` + `user_prompt_standard.txt` (read verbatim, never re-typed).

## 4. Primary M7

- Input: CE400 + diabetes500 frozen-inference inputs (pair_id/domain/string_a/string_b only)
- Script: `strengthening/experiments/primary_m7_runner.py` (wraps `scripts/run_full_workflow.py`'s exact single-call-per-pair request logic)
- Config: frozen prompt + model config + 0.50 threshold (Section 3)
- Output: (once run for real) `strengthening/restricted_local/experiments/primary_m7_requests/` for the request log; predictions joined with gold in a later evaluation step
- Paid: YES (Anthropic), 900 new requests total (not 1,800 -- see Section 9)
- Status: dry-run implemented and verified; NOT executed for real in this phase

## 5. B1-B8

- B1/B2/B3/B4/B5: `strengthening/experiments/b1_b5_baselines.py` -- deterministic, free, **executed for real in this phase**. Predictions: `strengthening/restricted_local/experiments/b1_b5_predictions/`. Evaluation (gold joined post-hoc): `strengthening/experiments/b1_b5_evaluation.py`, results in `strengthening/reports/B1_B5_FROZEN_INFERENCE_EVALUATION.{json,md}`.
- B6: `strengthening/experiments/b6_runner.py` -- dry-run implemented; paid (Anthropic), NOT executed for real.
- B7: `strengthening/baselines/b7_direct_relation/client.py` (`classify(..., execute_paid=True)`) + `real_client.py` -- real transport now implemented and gated; NOT executed for real (no `execute_paid=True` was ever passed with a real key in this phase).
- B8: `strengthening/experiments/b8_benchmark_eval.py` -- corrected benchmark-evaluation adapter (Section 6 below). Structural stats are gold-independent and free; captured-pair prediction reuses B7's per-pair result (adds zero new LLM calls).

## 6. B8 corrected evaluation design (see Section 12 for full detail)

For every one of the 900 frozen pairs: run B8's own lexical+dense retrieval (no gold) to decide if the pair is "captured"; if captured, reuse B7's prediction for that exact pair (never re-call the classifier); if not captured, predict non-match structurally. Scored against ALL 900 eligible pairs, never only the captured subset. "Benchmark capture rate" (defined precisely in the module) is reported only post-hoc, gold selecting the denominator only, and is explicitly NOT pair completeness / retrieval recall / an unbiased estimate of unseen equivalences.

## 7. OpenAI second-provider robustness

- Script: `strengthening/experiments/openai_second_provider_runner.py`
- Model: `gpt-5.4-nano-2026-03-17`, `reasoning.effort="none"`, temperature 0, frozen threshold 0.80 (Section 3)
- Paid: YES (OpenAI), 900 new requests, dry-run only in this phase

## 8. Bootstrap / statistical metrics

`strengthening/metrics/binary.py` (`bootstrap_ci`, `paired_bootstrap_difference`) -- percentile bootstrap over items, seed 42, 10,000 resamples by default. Already exercised for real on the B1-B5 results (Section 5). To be re-run once each LLM-based method's real predictions exist, including paired method-difference intervals (e.g. primary vs. best baseline).

## 9. Selective-prediction metrics

`strengthening/metrics/selective.py` (coverage, selective risk, risk-coverage curve, AURC, threshold sensitivity, coverage-at-target-precision). Demonstrated now on B1-B5 using a MARGIN-based confidence proxy (`|similarity - frozen_threshold|`), explicitly NOT a genuine model confidence -- see caveat in `b1_b5_evaluation.py`. The scientifically meaningful selective-prediction analysis requires the LLM-based methods' genuine guard-confidence field (primary M7, OpenAI) and must wait for real execution. `conformal_prediction.py` remains opt-in and is NOT promoted into this plan. With only 7 gold-uncertain labels in the 900-pair benchmark, uncertain-class metrics must be reported descriptively, never as a stable headline estimate.

## 10. Candidate-generation diagnostics (no human retrieval gold)

`strengthening/candidate_gen/retrieval_audit_burden_analysis.py` -- already computed prior to this phase; gold-independent (candidate counts, reduction ratio, per-route contribution/overlap, retention by difficulty band, annotation-time estimates). `strengthening/metrics/retrieval.py`'s `candidate_count`/`exhaustive_comparisons`/`reduction_ratio` are explicitly gold-independent and reused directly by `b8_benchmark_eval.py`. `pair_completeness`/`pairs_quality` correctly return `None` (never a fabricated number) without gold. Does NOT claim unbiased end-to-end pair completeness -- the benchmark was not built as an exhaustive retrieval-gold universe.

## 11. Reduced transitivity diagnostic (replaces invalid full cluster-gold plan)

`strengthening/experiments/transitive_contradiction_diagnostic.py`. Full B-cubed / exact-cluster-recovery is INVALID here: `strengthening/metrics/cluster.py` itself requires gold and predicted partitions to cover exactly the same item set (raises `ValueError` otherwise), and the 900-pair benchmark is a sampled pairwise subset, not an exhaustive partition -- manufacturing a "gold partition" from it via connected-components would silently misattribute sampling gaps to model failure. Instead: build predicted connected components from each method's predicted match edges, then check how many GOLD NON-MATCH pairs end up in the same predicted component (direct vs. transitive-only), reported as a lower-bound safety diagnostic, never as complete cluster precision/recall. Closed-triangle count (triples with all 3 pairwise gold judgments present) is computed and only analysed further if large enough (threshold: 10).

## 12. Downstream reproducibility check

`strengthening/experiments/downstream_reproducibility_check.py`. Confirms by source inspection that `scripts/rebuild_downstream.py` and its four companions make zero API calls. Honest finding: a live replay cannot actually be executed in THIS worktree (required restricted inputs -- `data/interim/scopus_ce_merged_deduped.csv`, three downstream JSONL logs, `restricted_local/downstream_cache.pkl` -- are all absent locally, Zenodo-only or never materialized here). The already-committed authoritative corrected results (`results/current_paper/downstream_results_corrected.csv`, `corrected_maps_manifest.json` with `all_checks_pass: true`) remain the current source of truth and are left unchanged.

## 13. Release preparation (biomedical/diabetes)

`strengthening/experiments/biomedical_release_manifest.py`. Precheck only -- no publication. Preserves 497 CC BY / 3 CC0 accounting; separates safe-public / methodology-internal / requires-separate-review fields (full lists in the generated manifest and in `BIOMEDICAL_RELEASE_READINESS.md`).

## 14. No-retuning rule (exact)

No script in this plan may compute a threshold, prompt variant, top-k, or any other hyperparameter as a function of the 900-pair prospective gold, or of the 149-pair legacy held-out test set. All thresholds are read from historical, hash-verified, pre-900-pair artefacts (Section 3). Gold is joined to already-frozen predictions only in a separate evaluation step, after predictions are written to disk.

## 15. No-H3 rule (exact)

H3 retrieval-audit annotation is NOT resumed, NOT started, and its packages are NOT touched. B8's evaluation in this plan uses ONLY its own internal (free, local) lexical/dense retrieval mechanism plus B7's per-pair classification -- it has no dependency on human retrieval-audit labels of any kind.

## 16. Paid vs. free steps

| Step | Paid? |
|---|---|
| B1-B5 | No |
| Primary M7 | Yes (Anthropic) |
| B6 | Yes (Anthropic) |
| B7 | Yes (Anthropic) |
| B8 | No (reuses B7, zero new calls) |
| OpenAI second-provider | Yes (OpenAI) |
| Bootstrap / selective-prediction / transitivity diagnostic / candidate-gen diagnostics / downstream reproducibility / release precheck | No |

See `strengthening/reports/COST_PREFLIGHT_AND_PAID_REQUEST_MATRIX.md` for the exact request counts and cost projection.

## 17. Expected output paths

- Frozen inputs: `strengthening/restricted_local/experiments/frozen_inputs/`
- B1-B5 predictions: `strengthening/restricted_local/experiments/b1_b5_predictions/`
- B1-B5 evaluation (tracked, safe): `strengthening/reports/B1_B5_FROZEN_INFERENCE_EVALUATION.{json,md}`
- B8 benchmark predictions (restricted): `strengthening/restricted_local/experiments/b8_benchmark_eval/`
- B8 structural stats (tracked, safe): `strengthening/reports/B8_BENCHMARK_EVALUATION_STRUCTURAL_STATS.{json,md}`
- Cost preflight (tracked, safe): `strengthening/reports/COST_PREFLIGHT_AND_PAID_REQUEST_MATRIX.{json,md}`
- Transitivity diagnostic (tracked, safe): `strengthening/reports/OBSERVED_TRANSITIVE_CONTRADICTION_DIAGNOSTIC.{json,md}`
- Downstream reproducibility (tracked, safe): `strengthening/reports/CE_DOWNSTREAM_REPRODUCIBILITY_CHECK.{json,md}`
- Biomedical release manifest (tracked, safe): `strengthening/reports/BIOMEDICAL_RELEASE_MANIFEST.{json,md}`
- Final preflight report: `strengthening/reports/C1_FROZEN_INFERENCE_PREFLIGHT.md`
