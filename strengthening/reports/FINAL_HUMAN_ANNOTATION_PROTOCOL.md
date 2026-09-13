# M7 Final Human Annotation Protocol

Frozen design. Package built at commit `2d657e8` (this protocol and the
package manifest were committed on top of it). Package files themselves
live under `strengthening/restricted_local/human_annotation/v1/`
(gitignored; distributed to annotators out-of-band, never committed).

## 1. Primary benchmark

400 circular-economy pairs + 500 diabetes-mellitus pairs = **900 pairs**.
Source files (unmodified since their own respective freeze):
`strengthening/restricted_local/ce/ce_400_annotation_candidates_unlabelled.csv`
and `strengthening/benchmark/biomedical_500_annotation_candidates_unlabelled.csv`.

## 2. Two independent annotators for all 900

Annotator 1 and Annotator 2 each receive all 900 pair IDs, in
independently randomised row order (Annotator 1: shuffle seed 42;
Annotator 2: shuffle seed 43), split across two tabs
(`Circular_Economy_400`, `Diabetes_500`) in their respective workbook.
Neither annotator sees the other's labels, any system/model prediction,
or any sampling metadata (stratum, scores, frequencies, routes).

## 3. Third-adjudicator procedure

Any pair where Annotator 1's label != Annotator 2's label goes to a
third, independent adjudicator, who sees both annotators' labels and
justifications and records a final decision. Agreeing pairs do not
require adjudication.

## 4. Retrieval audit: 30 seeds/domain, top-50 depth

Frozen as **Scenario E (SEEDS30_DEPTH50)**: 30 seed concepts per domain
(circular economy, diabetes mellitus), full top-50-per-route retrieval
depth, derived deterministically from the existing audited FULL 50-seed
inventories (never regenerated). Row counts: CE 3,117 total (2,967
in-pool + 150 outside-pool), diabetes 3,068 total (2,918 in-pool + 150
outside-pool).

## 5. Annotator 1: full retrieval annotation

Annotator 1 labels every Scenario-E row for both domains: 6,185 rows
total (3,117 CE + 3,068 diabetes), independently randomised order (seed
42), split across `Circular_Economy_Retrieval` / `Diabetes_Retrieval`
tabs.

## 6. Annotator 2: outside-pool + 30% stratified in-pool audit

Annotator 2 labels all outside-pool rows (150/domain, 300 total) plus a
**frozen, pre-selected** stratified-random 30% sample of in-pool rows
(889 CE + 877 diabetes = 1,766), selected by (domain, retrieval-route
signature, embedding-cosine difficulty band) using random seed 42 --
selected before any human label existed and independent of any label.
Total Annotator 2 retrieval rows: 2,066. The selection manifest and its
hash are tracked at
`strengthening/provenance/retrieval_audit_scenario_e_selection_manifest.json`.
Annotator 2's workbook does NOT expose which rows are outside-pool vs.
audit-sample, or any route/score/rank/frequency field.

## 7. 2% positive-miss escalation rule

Per domain, independently, after the initial 30% audit is adjudicated:
compute the adjudicated positive-miss rate among audited in-pool rows
(Annotator 1 = non-match or uncertain; Annotator 2 = match; Adjudicator =
match). If > 2% in a domain: expand Annotator 2's coverage in that domain
from 30% to 40% (the additional 10% pre-selected deterministically,
excluding rows already double-coded, same stratification logic, blind to
prior outcomes during selection). If the rate remains > 2% after the 40%
audit: expand to full double annotation for that domain. This 2%
threshold is an operational quality-control trigger, not a universal
statistical standard; Cohen's kappa and raw agreement are reported
descriptively alongside it but are not themselves the escalation trigger.

## 8. Optional bounded context: up to 3 titles

Annotators may consult `05_CONTEXT_LOOKUP_CE.xlsx` /
`06_CONTEXT_LOOKUP_DIABETES.xlsx` -- up to 3 representative article titles
per keyword/string, deterministically selected, no abstracts. CE context
is derived read-only from the local Scopus corpus (kept restricted);
diabetes context from the already licence-verified PMC records. Both
annotators receive the identical context-lookup files. Context must never
be fabricated: if no title is available, the lookup cell is left blank.

## 9. Context-use logging

Every row (primary and retrieval) has a `context_used` column
(yes/no, dropdown) that must be filled in alongside the label.

## 10. Complete blinding rules

Annotators never see: candidate stratum, Jaro-Winkler score, TF-IDF
score, embedding score, frequency, retrieval route, route rank, any
system/model prediction (Claude/OpenAI or otherwise), confidence value,
guard output, expected label, or benchmark/audit sampling metadata
(including outside-pool-vs-audit-sample status). Annotator-visible
primary columns: `row_number, pair_id, domain, string_a, string_b, label,
justification, context_used`. Annotator-visible retrieval columns:
`row_number, retrieval_pair_id, domain, seed_string, candidate_string,
label, justification, context_used`.

## 11. No model predictions visible

No baseline (B1-B8) or LLM-workflow prediction of any kind exists for
these new pairs -- none has been run. There is nothing to hide beyond the
sampling/retrieval metadata listed above.

## 12. Files expected back from each annotator

- Annotator 1: `ANNOTATOR_1_PRIMARY_COMPLETED.xlsx`, later
  `ANNOTATOR_1_RETRIEVAL_COMPLETED.xlsx`
- Annotator 2: `ANNOTATOR_2_PRIMARY_COMPLETED.xlsx`, later
  `ANNOTATOR_2_RETRIEVAL_COMPLETED.xlsx`

Annotators must not rename, reorder, or alter any `pair_id` /
`retrieval_pair_id` value, and must not add or remove rows.

## Human work order

- **Phase H1**: complete the 900-pair primary benchmark first (both
  annotators, independently).
- **Phase H2**: run primary agreement/adjudication
  (`merge_primary_annotations.py` -> `build_primary_adjudication_package.py`
  -> `evaluate_annotation_agreement.py`) before starting retrieval work.
- **Phase H3**: complete the retrieval audit. Retrieval annotation is NOT
  required before the primary benchmark can be validated -- this ordering
  keeps the secondary audit from delaying the main benchmark and reduces
  annotator fatigue.

## Post-annotation automation (implemented, not run on real labels)

`strengthening/human_annotation/validate_completed_workbooks.py`,
`merge_primary_annotations.py`, `build_primary_adjudication_package.py`,
`merge_retrieval_annotations.py`, `build_retrieval_adjudication_package.py`,
`evaluate_annotation_agreement.py`, `evaluate_retrieval_audit_escalation.py`
-- see their docstrings; each has synthetic-data tests under
`strengthening/tests/test_human_annotation_automation.py`.
