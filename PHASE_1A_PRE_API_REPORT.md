# Phase 1A Pre-API Report

Repair & Strengthening Programme — Workstream A (current paper), Phase 1A.
Produced 2026-08-24, working exclusively in `repair/current-paper-v1.0.1`.
**No paid API call was made. No GitHub push. No Zenodo publish. No
manuscript edit.**

## A. Author-attestation note status

Recorded in full:
`docs/provenance/annotation_author_attestation_2026-08-24.md`. The
corresponding author confirmed the annotators/adjudicator were author-team
members, the Excel-based process and pilot→calibration→full→adjudication
sequence described in the manuscript, ~39 annotator-hours as an
author-reported approximate total, and 52 (not 50) as the correct pilot
size. Explicitly logged as retrospective, non-contemporaneous evidence
that does not reinterpret the underlying file timestamps. This resolves
the one open item Phase 0A/0B could not close from files alone.

## B. Frozen benchmark manifest

`docs/provenance/phase1_benchmark_freeze_manifest.csv` +
`phase1_benchmark_freeze.md`. Confirmed confusion matrix (independently
re-derived a third time): test n=149, gold uncertain=25, binary
denominator=124, gold match=43, gold non-match=81, TP=41, FP=1, FN=2,
TN=80, precision=0.9762, recall=0.9535, F1=0.9647 — exact match to the
task specification. No label or split membership may change for the rest
of Phase 1.

## C. Bootstrap CI results

`docs/provenance/bootstrap_uncertainty_summary.md` +
`results/current_paper/bootstrap_uncertainty_{per_method,differences}.csv`.
10,000-resample pair-level bootstrap, seed 42, percentile CI, all 7
methods. Full LLM-DAG: F1 0.965 [0.917, 1.000]. F1 advantage over both B3
and B6 has a CI excluding zero; the precision advantage over B3 and the
recall advantage over B6 do not — reported honestly, not overstated.

## D. Error-sensitivity results

`docs/provenance/error_sensitivity_summary.md` +
`results/current_paper/error_sensitivity_analysis.json` (exact, exhaustive
enumeration, not sampled). F1 range across k=1/2/3 changed decisions:
[0.9524, 0.9767] / [0.9398, 0.9885] / [0.9268, 1.0000]. Directly quantifies
the editor's "three errors" comment: a 0.073 F1 swing from 3 of 124
decisions changing, reported for transparency, not as evidence the test
set is now adequate.

## E. Per-stratum analysis

`docs/provenance/per_stratum_analysis_summary.md` +
`results/current_paper/per_stratum_performance.csv`. All 149 rows
accounted for across 10 strata. 4 strata have zero gold-match pairs in
this test-set draw (precision/recall reported as undefined, not 0 or 1).
Stratum vi (near-synonyms) contains both real test-set errors. Stratum
iii (acronyms) has the lowest coverage (0.588), consistent with its known
annotation-stage disagreement.

## F. Three-way evaluation

`docs/provenance/three_way_evaluation_summary.md` +
`results/current_paper/three_way_evaluation.json`. Accuracy 0.886
(exact match to `test_results_summary.txt`), macro-F1 0.825. New finding:
uncertain-class precision = 1.00, recall = 0.44 — the guard never
incorrectly abstains, but misses more than half of genuinely ambiguous
gold pairs. Flagged as a new result to add, not a correction.

## G. Primary-model rerun harness status

`docs/provenance/rerun_stability_harness.md` +
`scripts/current_paper/rerun_stability/`. Complete, working harness;
dry-run validated end-to-end with a synthetic mock client (2 runs);
immutability and real-mode-refusal guards both verified working; the
historical reference run's metrics, computed through the new
multi-run analysis tool, reproduced ground truth exactly. Planned real
call count: 5 × 149 = 745. **Not executed against the real API.**

## H. Second-model candidate comparison

`docs/provenance/second_model_candidate_analysis.md`. Four candidates
researched against official provider pricing (OpenAI, Google, retrieved
2026-08-24): `gpt-5.6-luna`, `gpt-5-nano` (OpenAI); `gemini-2.5-flash-lite`,
`gemini-3.5-flash-lite` (Google). All support genuine structured output
and temperature=0; all cost well under $0.15 for the full dev+test
evaluation.

## I. Recommended second model

**Google `gemini-2.5-flash-lite`** — maximal independence from Anthropic,
genuine schema-constrained structured output (stronger than v1's
historical prompt-only JSON), longer track record than the very recent
`gpt-5.6`/`gemini-3.x` lines, cost immaterial either way. `gpt-5.6-luna`
recorded as the strongest alternative.

## J. Exact API cost estimate

`docs/provenance/phase1b_cost_and_action_checkpoint.md`. Part A (5 Claude
reruns, using the actual historical per-call rate): ≈ $0.1645. Part B
(second model, dev+test single pass): ≈ $0.039. Combined most-likely
scope: **≈ $0.20 USD**. With second-model reruns also included: ≈ $0.26.

## K. Exact manual actions required from author

Seven items enumerated in the cost checkpoint doc: confirm Anthropic
billing headroom; create/confirm a Google AI Studio account and billing;
generate a Gemini API key; set `ANTHROPIC_API_KEY`/`GEMINI_API_KEY` as
local environment variables (never pasted into any chat interface);
explicit written authorisation before a human removes the harness's
`--mode real` guard; post-execution billing verification.

## L. Result-table plan

`docs/provenance/current_paper_result_table_plan.md`. CIs fold into the
existing Table 6 (no new main-text table); one compact rerun-stability
table and one compact cross-model table added to the main text (both
directly answer editor requirements); per-stratum, Louvain
seed-sensitivity, and full rerun/cross-model detail move to supplement.

## M. Updated manuscript impact matrix

`CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md` (Phase 1A section
appended). Nine manuscript areas mapped (abstract, RQ2, methods,
main results, ablation, downstream, reproducibility, limitations,
conclusion) with disposition (RETAIN/NARROW/REPLACE/REMOVE/ADD NEW
RESULT) for each. No prose drafted.

## N. GO/NO-GO recommendation for paid Phase 1B

### Classification: **READY WITH CONDITIONS**

**The primary-model rerun-stability work (Task 6) is fully ready to
execute** — harness built, dry-run validated, cost trivial (~$0.16),
blocked only on: (1) the author confirming Anthropic billing headroom,
(2) explicit authorisation to remove the one-line `--mode real` guard.

**The second-model work (Tasks 7-9) is designed but not yet built** — the
candidate is chosen and the evaluation protocol is fully specified
(including the threshold-transfer-vs-retune decision, resolved in favour
of Option B), but the actual `scripts/current_paper/second_model/`
harness does not exist yet; it needs to be built (a small, low-risk
engineering step mirroring the already-working rerun-stability harness)
before it can run, in addition to the same account/key/authorisation
steps as the primary-model rerun.

**Two items from Phase 0B remain open and are unaffected by Phase 1A's
work**: the public GitHub exposure of restricted map files still awaits
an explicit human decision (`docs/release/v1.0.1_release_plan.md`), and
the 109-term/ARI manuscript-wording decisions still await author
sign-off. Neither blocks Phase 1B's experiments from proceeding, but
both should be resolved before the current paper is actually resubmitted.

### Recommended next steps, in order

1. Author confirms Anthropic + Google billing/account readiness (Task 10 §K).
2. Author gives explicit authorisation to execute the 5 Claude reruns.
3. Build the second-model harness (mirrors Task 6's structure; estimated
   low effort given the existing template).
4. Execute Phase 1B: 5 Claude reruns + second-model dev/test evaluation.
5. Run the pre-specified analyses (Tasks 6's stability report, Task 9's
   cross-model plan) exactly as designed — no new metrics invented after
   seeing the results.
6. Produce a Phase 1B report; only then consider manuscript text changes,
   using `CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md` as the source of
   truth for what changes and why.

**STOP. No paid API call has been made. Awaiting author review and
explicit authorisation before Phase 1B.**
