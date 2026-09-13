# Phase 1A Task 8 — Second-Model Evaluation Protocol

**Status: design only. Not executed. No second-provider API call made.**

## Design principle

The second model (recommended: `gemini-2.5-flash-lite`, Task 7) is
evaluated with **equal evidential completeness** to the primary model —
same benchmark, same splits, same metrics, same uncertainty quantification
— while `claude-haiku-4-5-20251001` remains the manuscript's narrative
primary model. The second model's role is a robustness check ("does the
LLM-DAG *method* generalise across model families"), not a
model-comparison shootout for its own sake.

## Fixed (must be identical to the primary-model evaluation)

- **Gold benchmark**: the frozen 500-pair gold standard
  (`data/benchmark/gold_benchmark.csv`), unchanged.
- **Dev/test split**: the frozen 351/149 split
  (`data/benchmark/{dev,test}_set.csv`), identical pair membership.
  **No re-splitting, no re-stratification.**
- **Label definitions**: match/non_match/uncertain, identical scope rules
  (`appendices/appendix_b_annotation_guide.md`).
- **Evidence fields per call**: the same fields the Task 6 harness already
  records for the primary model (timestamp, model identifier returned by
  the API, request parameters, response metadata, token usage, cost,
  prompt hash, pair identifier, raw response, parsed response, final
  guarded decision) — the second-model harness (Task 8 deliverable, to be
  built alongside Task 6's harness before Phase 1B) must produce
  structurally identical output files.
- **Guard logic**: G1–G4 as verified for v1 (JSON parse, required fields,
  valid decision enum, confidence threshold), applied identically in
  structure. G5 remains unimplemented for both models, consistent with
  the current-paper scope (Phase 0B Task 13) — this is not the moment to
  retrofit a safeguard that never existed in v1.
- **Output schema (conceptually)**: `{decision, confidence, justification}`
  — for the second model this can be *enforced* via native structured
  output (Task 7 §C), which is a strictly stronger guarantee than v1's
  prompt-only JSON request, not a deviation from it.
- **No test-set threshold tuning**: the test set is accessed once for
  final reporting, exactly as for the primary model.

## The one open design decision: threshold transfer vs. re-tuning

**Option A — transfer the primary-model's threshold (0.50) unchanged.**
Simple, and avoids any appearance of tuning the second model to look more
favourable. Risk: 0.50 was selected specifically for Claude Haiku's
confidence-score distribution: a different model's confidence calibration
could be systematically shifted (over- or under-confident relative to
Haiku), making an untuned transfer an unfair handicap or an unfair
advantage in either direction, not a neutral choice.

**Option B — tune the second model's own confidence threshold on the dev
set, under the identical pre-specified rule already used for the primary
model** (grid sweep over [0.50, 0.95] step 0.05, maximise F1 subject to
coverage ≥ 0.70; see `configs/v1_execution_config.yaml`). Test set still
accessed only once, after the threshold is frozen — so this is not
test-set leakage, it is the same disciplined dev/test separation already
applied to B3/B4/B5/the primary guard.

### Recommendation: **Option B**

Rationale: a model's raw confidence score is a property of that model's
own calibration, not a universal quantity comparable across providers at
face value. Forcing every model to use a threshold selected for a
*different* model's calibration is not "keeping things equal" — it
introduces exactly the kind of hidden, model-specific unfairness that
undermines a robustness claim. The scientifically cleaner choice is to
apply the *same procedure* (dev-set grid sweep, pre-specified objective,
frozen before any test-set access) to both models, which is precisely
what a fair, reproducible robustness comparison requires. This has to be
decided and documented **before** Phase 1B execution, not chosen after
seeing which option produces a better-looking number.

## Required analyses (equal completeness to the primary model)

1. Full held-out test-set metrics (precision, recall, F1, coverage),
   using the identical `binary_metrics()` logic already verified for v1
   (Phase 0B), applied to the second model's guarded decisions.
2. Bootstrap 95% CIs, identical procedure to Task 2 (pair-level
   resampling, N=10,000, seed=42, percentile CI).
3. Per-stratum analysis, identical structure to Task 4.
4. Three-way evaluation, identical structure to Task 5.
5. Cross-model agreement and error-overlap analysis — see Task 9.

## Deliverable for Phase 1B (not built yet, scoped here)

A `scripts/current_paper/second_model/` harness mirroring
`scripts/current_paper/rerun_stability/`'s structure: a `llm_client.py`
with a real Gemini client (lazy-imported `google-genai`) and the same
`MockClient` pattern for dry-run validation; a `run_second_model.py`
driver over dev then test. The existing `bootstrap_uncertainty_analysis.py`
/ `per_stratum_analysis.py` / `three_way_analysis.py` scripts (Tasks 2/4/5)
each currently hardcode the `results/test_predictions.csv` column names —
they require a small, mechanical parameterisation (accept a
`--prediction-column` argument instead of a hardcoded `METHODS` list)
before they can be reused for the second model's predictions; this is
straightforward but has not been done yet, since there is no second-model
prediction file to run them against until Phase 1B.
