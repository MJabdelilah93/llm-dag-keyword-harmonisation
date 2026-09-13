# M7 strengthening: annotation handoff plan

**UPDATE (post-ChatGPT-review resolution pass):** the biomedical track's
blocker is now resolved via the pre-specified diabetes-mellitus fallback
(hypertension is preserved, unmodified, as a documented failed-feasibility
outcome -- see `strengthening/reports/pmc_hypertension_feasibility.md` and
`strengthening/reports/hypertension_count_reconciliation.md`). Both
tracks now have complete, quota-exact benchmark files. **Human annotation
has still not begun and should not begin until this report is reviewed.**

Status: **both circular-economy and biomedical tracks are technically
ready for human annotation**, pending final sign-off on the retrieval-
audit design (see `strengthening/reports/retrieval_audit_burden_
analysis.md` -- a separate, still-open decision that does not block the
two benchmarks themselves).

## 1. Which files need human annotation

| File | Domain | Pairs | Status |
|---|---|---|---|
| `strengthening/restricted_local/ce/ce_400_annotation_template.csv` | circular_economy | 400 | **ready** |
| `strengthening/benchmark/biomedical_500_annotation_template.csv` | biomedical_diabetes_mellitus | 500 | **ready** |

Retrieval-audit files (separate from the two benchmarks above, used later
for candidate-recall evaluation, not part of this annotation round --
design still under review, see burden-analysis report):

| File | Domain | Rows | Status |
|---|---|---|---|
| `strengthening/restricted_local/ce/retrieval_audit_ce_seeds_candidates.csv` | circular_economy | 5,127 (50 seeds) | generated, not yet annotated, design under review |
| `strengthening/retrieval_audit/biomedical_diabetes_retrieval_audit_seeds_candidates.csv` | biomedical_diabetes_mellitus | 5,069 (50 seeds) | generated, not yet annotated, design under review |

## 2. Exact number of pairs

400 circular-economy pairs + 500 biomedical (diabetes-mellitus) pairs =
900 total, ready for annotation once reviewed. Hypertension (the original
primary biomedical topic) remains documented as a failed-feasibility
outcome (stratum iv fell short, 36/40, even after one broader time-window
test) and was superseded, not corrected -- both reports are preserved.

## 3. Which files are restricted vs open

- `strengthening/restricted_local/ce/*.csv` -- **restricted** (real
  Scopus-derived keyword strings, gitignored, Elsevier licensing).
  Annotators must be given these files directly (e.g. a controlled
  spreadsheet copy) and must not re-publish or commit them anywhere.
- `strengthening/benchmark/biomedical_500_annotation_template.csv` --
  **open/redistributable** (497 CC BY + 3 CC0 sourced PMC diabetes-
  mellitus content).

## 4. How two independent annotators should work

Each annotator works from their own blank copy of the template
(`annotator_1_label`/`annotator_1_justification`/`context_used_1` for one,
the `_2` columns for the other), independently and without seeing the
other annotator's entries or any system-predicted label/score/route
column beyond what the template already exposes (candidate provenance
routes/scores are visible by design -- they are not predictions, just
retrieval metadata -- but no model has produced a match/non-match/
uncertain judgement on these pairs at all yet, so there is nothing to be
blind to on that front). Use exactly the three labels `match` /
`non-match` / `uncertain`, applying the policy already frozen in
`strengthening/config/protocol_v1.yaml` (`labels.policy`): spelling,
punctuation/hyphenation, and singular/plural variants that denote the
same concept are `match`; unambiguous acronym expansions are `match`;
broader/narrower and related-but-distinct pairs are `non-match`; ambiguous
acronyms, context-dependent equivalence, and malformed/underspecified
pairs are `uncertain`. The candidate `stratum` column is sampling metadata
only -- it must never be used to infer or shortcut a label.

## 5. When bounded context may be consulted

Frequency counts (`frequency_a`/`frequency_b`) are always visible. Beyond
that, annotators may consult bounded external context (e.g. a quick
definition lookup) only when the pair cannot be judged from the strings
alone, exactly as in the legacy benchmark's annotation guide -- this is a
carry-over policy from the legacy protocol, not a new invention.

## 6. How context use must be recorded

Whenever any context beyond the two raw strings was consulted, the
annotator must record what was consulted in `context_used_1` /
`context_used_2` (e.g. "looked up abbreviation X on Y"). An empty
context-used field is itself a record: it means the label was judged from
the strings alone.

## 7. Third-annotator adjudication process

Any pair where `annotator_1_label` != `annotator_2_label` goes to a third,
independent adjudicator, who sees both annotators' labels and
justifications and records a final decision in `adjudicated_label` plus
`adjudicator_notes` explaining the resolution. Pairs where both annotators
agree do not require adjudication; `adjudicated_label` may be left blank
and the agreed label treated as final (mirroring the legacy benchmark's
adjudication scope).

## 8. Annotators must be blind to all system predictions

No match/non-match/uncertain prediction from any baseline (B1-B8) or the
primary/second-model LLM workflow exists for these new pairs yet -- none
has been run. Annotators see only: the two strings, frequencies, stratum
label (metadata, not a hint to use for labeling), and candidate-generation
provenance (which retrieval route(s) surfaced the pair and their raw
similarity scores) so they understand why the pair was sampled, not what
its answer should be.

## Resolved: biomedical topic (was a blocker, now closed)

The original biomedical topic, hypertension, could not reach 500 pairs
under the frozen ten-stratum quota (stratum iv fell short at 36/40, even
after one broader time-window test) and is preserved, unmodified, as a
documented negative-feasibility outcome. Per the pre-specified protocol
(diabetes mellitus was always the designated fallback after both a
primary-window and broader-window hypertension failure), the diabetes-
mellitus benchmark was activated as a full replacement and reached all
ten stratum quotas exactly (500/500, see
`strengthening/reports/pmc_diabetes_feasibility.md`). No candidates were
fabricated, no quota was reallocated, and hypertension pairs were not
mixed with diabetes pairs.

## Open item (not a blocker to the two benchmarks): retrieval-audit design

The retrieval-audit annotation workload (separate from the two 400/500
benchmarks above) has four candidate designs analysed in
`strengthening/reports/retrieval_audit_burden_analysis.{md,json}`, ranging
from ~254.9 combined annotator-hours (FULL, 45s/judgement planning
assumption) down to ~47.7 hours (REDUCED-3). This decision is left to
ChatGPT/the user and does not block distributing the two benchmark
templates for annotation.
