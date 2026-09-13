# Phase 1B Results Report — Real Paid API Execution

**Date:** 2026-08-24
**Branch:** `repair/current-paper-v1.0.1`
**Scope:** 5 fresh Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) reruns of
the frozen 149-pair test set, and one real OpenAI `gpt-5.4-nano-2026-03-17`
development (N=351) + held-out test (N=149) run. No Gemini call was made.
No other OpenAI model was called. No third model was called.

---

## A. Executive summary

Both authorised paid-execution stages completed successfully within the
USD 2.00 hard stop (actual: **USD 0.2473**, 12.36% of ceiling). Two
findings matter most:

1. **The primary model's rerun stability is empirically very high**
   (Fleiss' kappa = 0.9929) — this is new, real evidence, not a
   validated-but-unexecuted harness as in Phase 1A.
2. **The second-model (OpenAI) cross-model robustness check is only
   partially supported.** GPT-5.4 nano, run under a protocol using the
   same task, benchmark, and decision policy — but with a
   development-tuned confidence threshold and provider-appropriate
   generation parameters, not an identical or untuned one (see Section
   C-E and the corrected protocol-wording note below) — scores
   meaningfully lower (F1 = 0.8916 vs Claude's 0.9647), and the F1/recall
   gap is statistically credible (paired bootstrap 95% CI excludes
   zero; the precision gap's CI does not). The editor's "two or more
   models" condition is procedurally satisfied; the implicit hope that a
   second model would simply confirm the first is not.

**2026-08-24 reconciliation audit (this revision):** an independent
review identified several internal inconsistencies in the first version
of this report — a mislabelled coverage/n_decided denominator, a
cross-model "error superset" claim that mixed two different correctness
definitions (true under one, false under the other), an overreaching
benchmark-size-robustness claim, imprecise causal language around
abstention vs. precision, inaccurate "identical/non-tuned" protocol
wording, and four verbatim restricted-data examples that were mistakenly
quoted inline. All are corrected in this revision; the full audit trail
— every issue checked, source artefact, recomputed value, old vs.
corrected interpretation — is in
`docs/provenance/phase1b_final_reconciliation_audit.md`. **No number
in Sections F-J below changed as a result of this audit** — every
correction is to labelling, scope, and interpretation, not to the
underlying real-execution data.

Three process anomalies occurred during execution; all were caught
before any API cost was incurred or before the one-shot held-out test
set was touched (Section Q gives the exact timing of each).

---

## B. Pre-flight verification (before any paid call)

- `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`: confirmed present at User
  environment-variable scope (boolean check only; values never printed,
  logged, or committed at any point in this phase).
- Active branch: `repair/current-paper-v1.0.1`, working tree clean
  before execution began.
- Tasks 1-4 artefacts confirmed present and unmodified; full test suite
  (48 tests, including the 15 OpenAI-harness tests) passing before the
  first real call.
- `$2.00` hard stop preserved throughout; actual spend never approached
  it (see Section O).
- No Gemini call made at any point in this engagement (confirmed again
  here; unchanged since the original supersession).

---

## C-E. Model verification, adapter, and parameter-mapping recap

Full detail in `docs/provenance/openai_gpt54_nano_verification_2026-08-24.md`,
`scripts/current_paper/second_model/openai/`, and
`docs/provenance/cross_provider_parameter_mapping.md` (all committed in
the Tasks 1-4 commit, prior to this execution). Key settings actually
used for every real OpenAI call: `reasoning.effort="none"`,
`temperature=0`, `max_output_tokens=256`, schema-enforced structured
output (`strict=true`), `store=false`, no seed (unsupported for this
model family, disclosed not fabricated).

**What is and is not identical across the two model conditions
(reconciliation audit correction, item 6):** the task, the frozen
benchmark (same dev/test pairs), the prompt text (byte-identical
`prompts/v1.0.0/*.txt`), and the decision policy (guard G1-G4, three-way
label set) are identical. The **confidence threshold is NOT identical
by design** — each model's threshold was independently development-tuned
via the same pre-specified rule (maximise F1 s.t. coverage≥0.70),
yielding 0.80 for OpenAI and 0.50 for Claude's historical/frozen
threshold; this is "identical procedure, different tuned value," not
"identical value." **Generation parameters are prospectively
provider-appropriate, not forced equal**: OpenAI uses schema-enforced
structured output where Claude's historical call used prompt-only JSON;
OpenAI has no `seed` where a hypothetical Gemini condition would have
had one; `reasoning.effort` has no Claude analogue at all. The correct
characterisation is "same task and decision policy, provider-appropriate
parameters, independently tuned threshold" — not "identical, non-tuned
protocol."

---

## F. Claude Haiku 4.5 rerun stability (real evidence)

Five fresh real reruns (`real_run_1`..`real_run_5`) plus the historical
2026-04 reference, all against the frozen 149-pair test set, identical
protocol (temperature=0, max_tokens=256, no auxiliary context, no top_p).
Full report: `results/current_paper/rerun_stability/real_phase1b_stability_report.json`.

| Metric | Value |
|---|---|
| Fleiss' kappa (6 raters: 5 real + historical) | **0.9929** |
| Pairs whose label ever changed across all 6 conditions | **1 / 149 (0.67%)** |
| Nature of the one unstable pair | oscillates between `non_match` and `uncertain` only — never flips to/from `match`; contributes 8 of the 15 pairwise-run comparisons that disagree |
| Pairwise exact label agreement | 0.9933-1.0000 across all 15 run-pairs |
| Mean pairwise confidence stdev (5 real runs) | 0.0019 |
| Precision / Recall / F1 range across all 6 conditions | **exactly 0.9762 / 0.9535 / 0.9647 in every single condition — zero width** |
| Coverage range | 0.9262-0.9329 (the only metric affected by the one unstable pair, since it is a non_match/uncertain wobble that never touches the `match` class the binary metric is computed over) |

**Interpretation (reconciliation audit note, item 7): four distinct
claims, not one, and only the first three are directly measured here —
this is empirical stability evidence for six real conditions on one
149-pair benchmark, not a general determinism guarantee:**

1. **Exact 3-way label stability**: 148/149 (99.33%) — one pair's label
   is not identical across all 6 conditions.
2. **Nature of the one unstable pair**: oscillates only between
   `non_match` and `uncertain`; never touches `match`.
3. **Coverage varies slightly** (0.9262-0.9329) as a direct consequence
   of (2) — this is the only aggregate metric the wobble affects.
4. **Precision, recall, and F1 are invariant** (bit-identical: 0.9762 /
   0.9535 / 0.9647) across all 6 conditions — because the wobble never
   crosses into or out of the `match` class these metrics are computed
   over.

This is materially stronger evidence than Phase 1A's dry-run-validated-
but-unexecuted harness could offer. It supports the claim that, **for
this specific benchmark, this specific model snapshot, and this
temperature=0 configuration, empirically observed rerun variability is
very low** — it does not establish that the model is deterministic in
general (Anthropic's own documentation does not guarantee bitwise
determinism at temperature=0), nor does it bound variability for any
other benchmark, prompt, or model version.

---

## G-H. OpenAI development run and threshold freeze

Real run `real_dev_1`, N=351, 0 errors, 0 reasoning tokens (confirms
`reasoning.effort="none"` took effect as intended, not merely requested).

Full threshold grid (`results/current_paper/second_model/openai/dev_run_real_dev_1/threshold_candidate_table.csv`):

| Threshold | Precision | Recall | F1 | Coverage |
|---|---|---|---|---|
| 0.50-0.75 | 0.8585 | 0.901 | 0.8792 | 0.7692 |
| **0.80** | **0.901** | **0.901** | **0.901** | **0.735** |
| 0.85 | 0.901 | 0.901 | 0.901 | 0.735 |
| 0.90 | 0.9286 | 0.901 | 0.9146 | 0.5613 (below floor) |
| 0.95 | 0.9773 | 0.8515 | 0.9101 | 0.3647 (below floor) |

Rule (fixed before any OpenAI call): maximise F1 subject to coverage
≥0.70. **Selected: 0.80** (ties with 0.85; the pre-specified ascending-grid
tie-break — fixed in Phase 1B Tasks 1-2's original design, unchanged here
— deterministically picks the lower value).

**Frozen and committed** in
`results/current_paper/phase1b/openai_dev_freeze_manifest.json`
(commit `60c753a`) **before** the held-out test run touched any
test-set data — the auditable pre-registration this phase's Task 6
required.

---

## I. OpenAI held-out test results

Real run `real_test_1`, N=149, exactly once, 0 errors, threshold=0.80
applied per the frozen manifest.

| Metric | Point estimate | 95% bootstrap CI (N=10,000, seed=42) |
|---|---|---|
| Precision | 0.9250 | [0.8298, 1.0000] |
| Recall | 0.8605 | [0.7447, 0.9545] |
| F1 | 0.8916 | [0.8101, 0.9545] |
| Coverage | 0.7584 | [0.6913, 0.8255] |

**Denominator clarification (reconciliation audit correction):** the
figure "111" is the count of definitive (non-abstained) predictions
among the **N=124 gold-binary subset** (match/non-match pairs only),
i.e. **111/124 = 0.8952** — this is the denominator `precision` and
`recall` above are computed over. It is NOT "111/149"; that mislabelling
in the original version of this report has been corrected. The
**coverage** figure (0.7584) uses a different, larger denominator: it is
computed over **all 149 test pairs** regardless of gold label —
113 definitive predictions among all 149 (149 − 36 abstentions = 113;
113/149 = 0.7584). Full breakdown, including the equivalent figures for
Claude (0 abstentions on the 124 gold-binary pairs; 11 abstentions among
all 149, entirely on gold-uncertain pairs):
`results/current_paper/phase1b/reconciliation_coverage_breakdown.json`.

| | Among all 149 | Among gold-binary N=124 |
|---|---|---|
| OpenAI definitive predictions | 113 | 111 |
| OpenAI abstentions | 36 | 13 |
| OpenAI coverage (definitive/denominator) | 0.7584 | 0.8952 |
| Claude (majority) definitive predictions | 138 | 124 |
| Claude (majority) abstentions | 11 | 0 |
| Claude (majority) coverage | 0.9262 | 1.0000 |

For comparison, the primary model's historical/real result on the same
test set: precision 0.9762, recall 0.9535, F1 0.9647, coverage (over all
149) ≈0.926-0.933 across the 5 real reruns.

---

## J. Three-way metrics, including uncertain-class behaviour

Full detail: `results/current_paper/phase1b/openai_test_three_way_evaluation.json`.

- Accuracy: 0.8725, macro F1: 0.8486.
- Confusion matrix (gold rows × pred cols): match→{match:37, non_match:1,
  uncertain:5}; non_match→{match:3, non_match:70, uncertain:8};
  uncertain→{match:2, non_match:0, uncertain:23}.
- **Uncertain-class precision: 0.6389** (13 of 36 predicted-uncertain
  pairs are not actually gold-uncertain) vs **uncertain-class recall:
  0.92** (only 2 of 25 gold-uncertain pairs are missed). GPT-5.4 nano
  abstains liberally — it rarely misses a genuinely ambiguous pair, but
  it also frequently abstains on pairs that do have a clear gold label,
  which is the direct mechanism behind its lower coverage/recall in the
  binary evaluation above.

---

## K. Per-stratum results (counts-first; small strata flagged)

Full table: `results/current_paper/phase1b/openai_test_per_stratum_performance.csv`.

| Stratum | n | Precision | Recall | F1 | Coverage | Note |
|---|---|---|---|---|---|---|
| i | 12 | 1.0 | 1.0 | 1.0 | 1.0 | — |
| ii | 13 | n/a | n/a | n/a | 0.923 | no predicted/gold matches in stratum |
| **iii** | **17** | 1.0 | **0.4286** | 0.6 | 0.176 | low recall — 4/7 gold matches missed |
| iv | 12 | 1.0 | 0.9167 | 0.9565 | 0.917 | — |
| ix | 11 | n/a | n/a | n/a | 0.182 | no predicted/gold matches; entirely gold-uncertain stratum |
| v | 10 | 1.0 | 1.0 | 1.0 | 1.0 | — |
| **vi** | **22** | **0.0** | **0.0** | **0.0** | 0.818 | **3 false-positive "match" calls, 0 true positives (1 gold match in stratum, missed)** |
| vii | 22 | n/a | n/a | n/a | 0.909 | no predicted/gold matches in stratum |
| viii | 18 | 1.0 | 1.0 | 1.0 | 0.722 | — |
| x | 12 | n/a | n/a | n/a | 1.0 | no predicted/gold matches in stratum |

**Stratum `vi` (n=22) is the clearest descriptive weak point**: OpenAI
produces zero true positives and 3 false positives out of 1 gold match
and 21 gold non-matches. **Reconciliation audit correction (item 8):**
the original version of this report characterised this as "not
statistical noise," an inferential claim no formal test in this report
actually supports (n=22 is itself a small stratum, and no significance
test was run on the stratum-level counts specifically). The defensible
statement is purely descriptive: **in this sample, this stratum shows
concentrated errors (3/3 predicted matches are false positives) — worth
naming specifically if per-stratum cross-model results enter the
manuscript, but not a claim about whether this pattern would replicate
on a larger or different sample of the same stratum.**

---

## L-N. Cross-model comparison: agreement, error overlap, disagreements vs gold

**Reconciliation audit correction: the original version of this section
mixed a binary-decided-only correctness definition with three-way
examples, producing an apparent contradiction (a stated "only Claude
wrong = 0" alongside worked examples of OpenAI being right where Claude
was wrong). These are now reported as two separate, non-comparable
analyses, per the audit
(`docs/provenance/phase1b_final_reconciliation_audit.md`, item 2).
"Claude" throughout = majority vote across the 5 real reruns (justified:
kappa=0.9929 among the 5 reruns themselves, only 1/149 pairs ever
disagreed, so majority vote is effectively unanimous-vote).**

### N1. Primary binary evaluation (gold restricted to match/non-match, N=124)

Full detail: `results/current_paper/phase1b/reconciliation_binary_contingency.json`.

**Abstention scoring policy (stated explicitly, as required):** a
prediction of `uncertain` on a gold match/non-match pair is scored as
**NOT CORRECT** — a missed decision, kept distinct from an actively
**WRONG_DECIDED** misclassification.

| | Claude (of 124) | OpenAI (of 124) |
|---|---|---|
| CORRECT | 121 | 107 |
| WRONG_DECIDED (active error) | 3 | 4 |
| ABSTAINED | 0 | 13 |

**2×2 correctness contingency:**

| | Value |
|---|---|
| Both correct | 107 |
| Claude correct, OpenAI not correct | 14 |
| OpenAI correct, Claude not correct | 0 |
| Both not correct | 3 |

Under this binary, decided-pairs framing, OpenAI's 17 "not correct"
outcomes split as **13 abstentions + 4 active misclassifications** —
abstention, not active error, is the dominant component (76% of its
"not correct" outcomes).

### N2. Full three-way evaluation (all 149 pairs, all 3 labels)

Full detail: `results/current_paper/phase1b/reconciliation_threeway_contingency.json`,
`reconciliation_claude_threeway_confusion_matrix.csv`. Correctness here
= predicted label exactly equals gold label (`uncertain` predicted on a
gold-`uncertain` pair counts as correct).

**Claude's own three-way confusion matrix (not computed in the original
report):**

| Gold \ Pred | match | non_match | uncertain |
|---|---|---|---|
| match (43) | 41 | 2 | 0 |
| non_match (81) | 1 | 80 | 0 |
| uncertain (25) | 1 | 13 | 11 |

Notable, previously unreported: **Claude abstains on zero gold
match/non-match pairs**, but also abstains on only **11 of 25 (44%)**
gold-`uncertain` pairs — the other 14 are forced into a definitive
(and, by definition, gold-mismatching) `match`/`non_match` call. This is
the mirror image of OpenAI's behaviour (which abstains liberally,
including on decidable pairs).

**OpenAI's three-way confusion matrix** (unchanged from Section J):
match→{match:37, non_match:1, uncertain:5}; non_match→{match:3,
non_match:70, uncertain:8}; uncertain→{match:2, non_match:0,
uncertain:23}.

**Three-way correctness contingency (vs. gold, all 149):**

| | Value |
|---|---|
| Both correct | 118 |
| Claude correct, OpenAI wrong | 14 |
| **OpenAI correct, Claude wrong** | **12** |
| Both incorrect | 5 |

**Model-to-model agreement (Claude's predictions vs. OpenAI's
predictions, not vs. gold):** exact agreement 81.21%; Cohen's kappa
0.6852 (see Section on kappa interpretation below for how to present
this number without an unearned qualitative label).

### N3. What must not be conflated

**N1 and N2 use different denominators, different label sets, and
different treatment of gold-`uncertain` pairs, and must never be quoted
interchangeably.** N1's "Claude correct, OpenAI not correct = 14" and
N2's "Claude correct, OpenAI wrong = 14" are numerically identical by
coincidence of this dataset (N1 excludes gold-uncertain pairs entirely;
N2's 14 count happens to consist of the same 14 pairs, all of which have
gold match/non-match labels) — but N2 additionally shows **12 pairs
where OpenAI is correct and Claude is wrong**, entirely invisible to the
N1 framing because N1 excludes the gold-`uncertain` pairs where all 12
of those cases occur. See Section 3 (Claim 13) below for what this means
for the "error superset" claim.

### Note on presenting Cohen's kappa (reconciliation audit, item 9)

**0.6852, computed on 149 three-way predictions, with 81.21% raw exact
agreement.** Both numbers are the empirical result. A qualitative label
("substantial," "moderate," etc., per conventions such as Landis &
Koch 1977) is an interpretive convention layered on top of the number,
not part of the measurement itself, and different conventions draw the
category boundaries differently. If the manuscript or this report
attaches a qualitative label to this kappa value, it must be marked
explicitly as a conventional interpretation (e.g. "0.6852, which on the
Landis-Koch scale is conventionally labelled 'substantial agreement'"),
never presented as if the label itself were the empirical finding.

---

## O. Paired uncertainty analysis (statistical comparison)

Paired bootstrap (same 10,000 resamples, same indices, applied to both
models simultaneously — `results/current_paper/phase1b/cross_model_paired_bootstrap_differences.csv`):

| Metric | OpenAI − Claude | 95% CI | Excludes zero? |
|---|---|---|---|
| Precision | −0.0512 | [−0.1282, 0.0000] | **No** |
| Recall | −0.0930 | [−0.1892, −0.0208] | **Yes** |
| F1 | −0.0731 | [−0.1405, −0.0225] | **Yes** |

**This is the single most important quantitative finding of Phase 1B**:
the F1 and recall gaps are statistically credible (CI excludes zero); the
precision gap is not (CI includes zero).

**Reconciliation audit correction — conservative causal wording
(item 5):** the original version of this report stated the aggregate
gap is "driven by abstention, not precision," treating the precision
CI's inclusion of zero as evidence that precision is *equal*. That
overstates what a CI containing zero establishes. The precise,
defensible statement is:

- OpenAI's **abstention rate is higher** (13/124 vs. Claude's 0/124 on
  the gold-binary subset — Section N1) — this is a directly observed
  count, not inferred.
- OpenAI's **recall is lower**, and the recall-difference CI excludes
  zero — this gap is statistically credible.
- OpenAI's **active decided-pair errors** (4 wrong_decided out of 124)
  are few in absolute count, and slightly outnumbered by Claude's own
  (3 of 124) plus one abstention (Section N1's 4×4 breakdown).
- The **precision point estimate** is lower for OpenAI (0.9250 vs.
  0.9762), but the **paired-bootstrap CI on that difference includes
  zero** — meaning this sample does not provide statistically resolved
  evidence of a precision difference **in either direction**. This is
  not the same as evidence that precision is equal; absence of a
  resolved difference is not evidence of no difference.

**Conservative summary:** the data support that OpenAI's lower F1 is
associated with, and substantially attributable to, its higher
abstention rate and consequent recall loss — a mechanistically direct
link (an abstained gold-match pair is scored as a miss). Whether
OpenAI's precision genuinely differs from Claude's on this task remains
statistically unresolved with N=124, not settled in the negative.

---

## P. Exact API usage and cost, by provider/model/run

Full detail: `results/current_paper/phase1b/cost_report.json`.

| Provider | Run | Pairs | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| Anthropic | real_run_1 | 149 | 62,981 | 14,137 | 0.0334 |
| Anthropic | real_run_2 | 149 | 62,981 | 14,128 | 0.0334 |
| Anthropic | real_run_3 | 149 | 62,981 | 14,105 | 0.0334 |
| Anthropic | real_run_4 | 149 | 62,981 | 14,071 | 0.0333 |
| Anthropic | real_run_5 | 149 | 62,981 | 14,111 | 0.0334 |
| **Anthropic total** | | 745 | | | **0.1669** |
| OpenAI | dev_real_dev_1 | 351 | 155,436 | 20,140 | 0.0563 |
| OpenAI | test_real_test_1 | 149 | 66,023 | 8,712 | 0.0241 |
| **OpenAI total** | | 500 | | | **0.0804** |
| **Combined total** | | 1,245 | | | **0.2473 (12.36% of $2.00 ceiling)** |

Note: the combined total above is the actual metered cost of the 1,245
real API calls made in this phase. It is not to be confused with any
prepaid account balance either provider may hold.

---

## Q. API/retry/structured-output anomalies

**Zero retries across all 1,245 real API calls** (both providers). **Zero
G1/G2/G3 guard triggers** (no malformed JSON, no missing required
fields, no invalid decision labels) across any real call — both
Claude's prompt-only JSON request and OpenAI's schema-enforced structured
output produced 100% well-formed, parseable responses. The only guard
activity was 4 legitimate G4 triggers (confidence below the 0.80
threshold) in the OpenAI test run — expected behaviour, not an anomaly.

**Reconciliation audit correction (item 11):** the three anomalies below
are of genuinely different kinds and occurred at different points
relative to network calls, cost, test-set access, and commit/push — they
must not be summarised under one blanket "all caught before any cost"
statement, which was true for two of the three but not the second.

1. **Missing `openai` package** — a pre-flight, no-cost anomaly. The
   first dev-run attempt failed at client construction
   (`ModuleNotFoundError`), **before any network call, before any cost,
   before any test-set access, and before any commit**. Fixed by
   installing the already-pinned `openai==3.3.1`.
2. **Restricted-data handling gap** — a **post-hoc, post-cost, post-commit**
   anomaly, unlike (1) and (3). Real model `justification` text (from
   API calls that had already been made and already cost money) was
   found, after the fact, to quote the actual Scopus-derived keyword
   pairs verbatim. This was noticed **before the raw output files were
   committed** (so the raw files themselves were correctly kept out of
   git via a `.gitignore` extension — no raw restricted content reached
   any commit), but the fix's own explanatory documentation **was
   committed with the leak still present**: two files
   (`docs/provenance/phase1b_real_raw_outputs_manifest.md`,
   `PHASE_1B_RESULTS_REPORT.md`) quoted verbatim real keyword-pair
   examples inline, and these commits were not caught until this
   reconciliation audit. Full detail, exact commits, and remediation
   options: `docs/provenance/phase1b_final_reconciliation_audit.md`,
   item 10. **This anomaly was not caught before commit** — it was
   caught, and only partially remediated (redaction, not history
   rewrite), during this later audit. No scientific result is affected;
   this is a data-handling/repository-hygiene issue, not a computation
   error.
3. **Dev-manifest schema mismatch** — a pre-flight, no-cost anomaly, like
   (1). The first held-out test-run attempt was pointed at the human-readable `openai_dev_freeze_manifest.json`
   (Task 6's audit artefact), which uses a different JSON structure than
   `run_test_evaluation.py` expects (that script's `--dev-manifest`
   contract is the auto-generated `dev_manifest.json`). The script failed
   with a `KeyError` at manifest-parsing time, **before** constructing any
   client or reading any test-set row. Zero cost, zero test-set access.
   Fixed by pointing `--dev-manifest` at the correct auto-generated file;
   the frozen threshold (0.80) and all other pre-registered values were
   unaffected and unchanged.

No frozen-protocol mismatch occurred (the frozen threshold and dev/test
separation were never actually violated — item 3 was caught before any
manifest was misapplied), no gold-label leakage into prompts occurred
(tested and confirmed clean, Tasks 1-4), and no cost anomaly occurred in
the sense of unexpected spend. Items 1 and 3 were caught by the
harness's own pre-flight checks exactly as designed; **item 2 was not** —
it was caught only during this later reconciliation audit, after two
commits already contained the leaked text. That gap in the harness's own
checks (no automated scan for restricted-content patterns in newly
authored documentation before commit) is itself worth noting as a
process improvement for any future phase, though not one this audit
implements.

---

## R. Reviewer-style interpretation — robust vs. weak/unsupported claims

**Robust, well-supported claims:**
- The primary model's benchmark performance (F1=0.9647) is independently
  re-verified across 5 fresh real reruns plus history, with essentially
  zero variance in the binary metrics (Fleiss' kappa=0.9929).
- The workflow's superiority over string-similarity baselines (Phase 1A
  bootstrap CIs, unchanged) stands independent of this phase's findings.
- The second-model check was executed with full methodological rigor: no
  gold-label leakage, no post-hoc threshold tuning on the test set, exact
  snapshot pinning, pre-registered dev-freeze commit before test access.
  The *process* of the cross-model check is not in question.

**Weak or unsupported claims — must not appear in the manuscript as
written:**
- **"The workflow generalises across model families"** is NOT supported
  as an unqualified claim. It is supported only in the narrow,
  qualified sense that a second model *can* be run through the same
  pipeline and produce internally coherent (if weaker) results — not that
  it reproduces the primary finding's magnitude.
- **Any claim that GPT-5.4 nano and Claude Haiku are interchangeable**
  for this task is directly contradicted by the paired-bootstrap F1/recall
  gap (CI excludes zero).
- **Any value-for-value comparison of raw confidence scores between
  providers** is unsupported — the two models' confidence distributions
  differ in shape (OpenAI's low-confidence tail is 3x larger), and both
  show discretized, non-continuous self-reported values.
- Carried forward, unchanged, from Phase 0B/1A (re-confirmed, not
  re-litigated, this phase): the ARI-based downstream superiority claim
  remains NOT SUPPORTED; the 109-term claim remains unreproducible; A3
  remains an invalid independent no-context ablation.
- **"The primary result is robust to the small test-set size"** is NOT
  supported as an unqualified claim (Claim 12, corrected). Phase 1A's
  own exact error-sensitivity bounds show the opposite: a handful of
  changed decisions materially moves F1. This phase's real rerun-
  stability finding (Claim 5) shows the pinned model does not itself
  spontaneously produce such changes on repeated real runs — a
  narrower, genuinely supported claim that must not be substituted for
  the broader small-sample-robustness claim.
- **"OpenAI's errors are a superset of Claude's"** holds only for the
  binary, decided-pairs framing (Claim 13, corrected) — it is false for
  the full three-way task, where 12 pairs exist where OpenAI is right
  and Claude is wrong.

**Thirteen claim verdicts (expanded from Phase 1A's 7):**

| # | Claim | Verdict |
|---|---|---|
| 1 | Primary model outperforms string-similarity baselines (F1/P/R) | **SUPPORTED** (unchanged, Phase 1A bootstrap CIs) |
| 2 | Downstream ARI-based clustering superiority | **NOT SUPPORTED** (unchanged, Phase 0B) |
| 3 | "109-term" claim reproducibility | **CANNOT REPRODUCE** (unchanged, Phase 0B) |
| 4 | A3 is a valid independent no-context ablation | **NOT SUPPORTED** (unchanged, Phase 0B) |
| 5 | Primary model LLM-level rerun stability | **SUPPORTED, VERY HIGH** (NEW — real evidence, kappa=0.9929) |
| 6 | Editor's "two or more models" condition is satisfied | **SUPPORTED procedurally** (NEW — real, rigorous execution) |
| 7 | Workflow conclusions are robust across model families (performance parity) | **NOT SUPPORTED** (NEW — real F1/recall gap, CI excludes zero) |
| 8 | GPT-5.4 nano's precision (on decided pairs) is worse than Claude's | **INCONCLUSIVE** (NEW — CI includes zero) |
| 9 | GPT-5.4 nano's lower aggregate F1/recall is associated with its higher abstention rate; its precision difference from Claude is statistically unresolved | **SUPPORTED (recall/abstention link); INCONCLUSIVE (precision difference)** — corrected from the original "driven by abstention, not precision" wording, which overstated what a CI containing zero establishes (item 5) |
| 10 | Raw confidence values are directly comparable across providers | **NOT SUPPORTED** (NEW — distributional evidence) |
| 11 | GPT-5.4 nano's uncertain-class calibration is reliable | **NOT SUPPORTED** (NEW — precision 0.6389) |
| 12 | Primary result's robustness to small test-set size (benchmark-size robustness), as distinct from claim 5's rerun-stability finding | **NOT SUPPORTED AS ORIGINALLY WORDED — corrected (item 4).** Phase 1A's own exact error-sensitivity bounds show a 3-decision perturbation on N=124 swings F1 across 0.927-1.000 (a ~0.073-point range — comparable in magnitude to the cross-model F1 gap this report treats as "statistically credible" elsewhere). This is exactly the small-test-set sensitivity the editor's review criticised, and it is not resolved by claim 5's finding: rerun stability shows the *pinned model, run repeatedly, does not spontaneously produce this perturbation*; it does not show the *result would be unchanged if a few gold labels or borderline decisions had gone differently*. These are different questions; only the first is supported by real Phase 1B evidence. |
| 13 | Cross-model error overlap shows OpenAI errors are a superset of Claude's | **PARTIALLY SUPPORTED — corrected (item 3).** TRUE for the primary binary evaluation, decided pairs only (N=124, gold match/non-match): 0 pairs where OpenAI is correct and Claude is not (Section N1). **FALSE for the full three-way task** (all 149 pairs, all 3 labels): 12 pairs exist where OpenAI is correct (mostly by correctly predicting `uncertain` on a gold-`uncertain` pair) and Claude is wrong (Section N2). The superset claim must be scoped to the binary-decided framing whenever stated; it does not hold unqualified. |

---

## S. Updated manuscript correction matrix

See `CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md`, new section "Phase
1B Manuscript Impact Matrix (Update)" (10 rows). No manuscript prose was
edited — per standing instruction, this remains a correction matrix only.

---

## T. Table/figure plan reassessment

Existing plan: `docs/provenance/current_paper_result_table_plan.md`
(Phase 1A). This phase's real data warrants exactly two additions, not a
wholesale redesign:
1. A compact cross-model summary row/table (primary vs second model,
   clearly labelled "Primary workflow result" vs "Cross-model robustness
   result" per the standing instruction not to promote GPT to co-primary).
2. A one-line disclosure note wherever confidence is discussed, that
   values are not cross-provider-comparable.
No new table is warranted for the per-stratum cross-model breakdown or
the confidence-distribution comparison merely because the data now
exist — both are adequately served by prose referencing the committed
CSV/JSON artefacts, per the standing instruction against adding tables
without a reader-facing need.

---

## U. Journal-readiness classification

Not a single READY/NOT READY verdict. **Reconciliation audit correction
(item 12): four distinct readiness questions, kept separate, since a
"yes" on one must never be read as implying a "yes" on another:**

| Readiness question | Status |
|---|---|
| **1. Computational Phase 1B execution complete?** | **YES.** All 21 authorised tasks' real-execution work is done: verification, adapter, tests, real dev+test runs, full downstream analysis. No further paid calls are needed to write up these results. |
| **2. Evidence/report internally consistent?** | **YES, as of this reconciliation audit** — it was NOT before. The audit found and corrected a mislabelled denominator, a scope-mixing error in the cross-model claim, an overreaching robustness claim, imprecise causal wording, inaccurate protocol-identity wording, and a restricted-data leak. No underlying number changed; several *interpretations and labels* did. |
| **3. Repository ready for public release / submission-linking?** | **NO at the time this section was written; YES as of the 2026-08-24 public-history cleanup** (`docs/provenance/public_history_cleanup_2026-08-24.md`) — see below for the historical record and the update. |
| **4. Manuscript ready?** | **NOT STARTED, by design.** No prose was drafted or edited in this or the prior Phase 1B pass. Content needed to draft the relevant sections exists in the correction matrix and this report. |

**[2026-08-24 UPDATE — all three items below are now resolved and
live-verified.]** Following an isolated, explicit author confirmation
obtained specifically for the destructive-history-rewrite step, a
public-history cleanup removed all three items from `origin/main`'s
history and live content, and separately scrubbed item (a) from the
repair branch's own (never-public) history. Full record, exact SHAs,
and verification: `docs/provenance/public_history_cleanup_2026-08-24.md`.
The historical explanation of the three original items follows,
retained for the audit trail:

**On question 3 specifically — the repository was NOT ready for
public release or submission-linking, for THREE reasons, only the first
of which this phase created:**

- **(a) NEW, this audit, local-only:** the restricted-data leak found in
  item 10 — two files on this branch contain (in git history; redacted
  from current file content) verbatim real Scopus-derived keyword-pair
  quotes. Nothing has been pushed, so there is no current public
  exposure from this specific item, but the branch's history is not
  clean and should not be pushed, merged, or shared as-is until an
  author decision is made on remediation.
- **(b) PRE-EXISTING, catalogued, NOT resolved by this phase:** the
  Phase 0B-identified exposure of
  `results/downstream_harmonisation_maps/{raw,b3,full_llm_dag}_map.csv`
  remains prepared but not executed on the actual public repository
  (`docs/release/v1.0.1_release_plan.md`).
- **(c) PRE-EXISTING, NEWLY DISCOVERED this audit, and apparently
  ALREADY LIVE on the public repository (more severe than (a) or (b)):**
  the reconciliation audit's restricted-content scan (Item 10, "Additional
  finding" subsection) found that `results/error_analysis.csv`,
  `results/test_predictions.csv`, and `results/test_predictions_baselines.csv`
  — containing raw keyword strings and, for the first file, full model
  justification text quoting them — are present on this repository's
  `origin/main` remote-tracking ref, i.e. **were never removed from the
  original public release** and were not part of Phase 0B's
  already-catalogued remediation inventory. This is a new finding, not
  previously documented anywhere in this repair effort.

**None of (a), (b), or (c) should be characterised as "does not block
manuscript drafting" in a way that implies unimportance** — they block
*repository/submission readiness* specifically, a distinct gate from
manuscript drafting. A manuscript can be drafted while all three remain
open; the repository cannot be responsibly linked from a submission, or
pushed/shared publicly, while any of them do. **(c) in particular
warrants prompt author attention independent of this phase's manuscript
timeline**, since — pending the author's own direct verification on
GitHub, which this no-network audit could not perform — it may
represent a live, ongoing public exposure of restricted content that
predates this entire repair engagement.

**This phase's own computational classification: COMPLETE (question
1).** That completeness does not extend to questions 3 or 4, which
remain open and are not close to resolved merely because question 1 is.

---

## V. Standing prohibitions — confirmed observed

- Manuscript prose: **not edited.**
- GitHub: **not pushed.**
- Zenodo: **not published.**
- Enhanced multi-domain study: **not begun.**
- Gemini: **not called**, at any point in this or any prior phase.
- Any other OpenAI model besides `gpt-5.4-nano-2026-03-17`: **not called.**
- Any third model: **not called.**
- API keys: **never printed, logged, or committed** — every check in this
  phase was presence-only (boolean), and every real invocation pulled the
  key into a subprocess environment without displaying it.

**Awaiting author/ChatGPT review, per standing instruction, before any
further action.**
