# Phase 1A Task 11 — Current-Paper Result Table Plan

**Status: planning only. The manuscript itself has not been edited.**

## Constraint

The manuscript is not present in this workspace (confirmed absent,
2026-08-23 audit) — it lives in Overleaf. This plan is written against the
table/figure inventory recorded in `INTERNAL_PROJECT_STATE.md` (7 tables,
2 figures) and the newer numbering implied by `results/llm_logs/README.md`
("paper tables 7-10"), and should be reconciled against the actual current
draft before implementation.

## Recommendation: what stays in the main paper vs. moves to supplement

| # | Table/content | Recommended location | Rationale |
|---|---|---|---|
| 1 | **Main benchmark table with CIs** (existing Table 6, now with bootstrap 95% CIs added per method) | **Main paper** | This is the anchor result; adding CIs in-line (e.g. "F1 = 0.965 [0.917, 1.000]") costs no additional table budget and directly answers the "three errors" concern with a number, not just prose |
| 2 | **Second-model comparison** (once it exists) | **Main paper, condensed** — full per-stratum/three-way breakdown moves to supplement | The headline cross-model agreement/κ and the primary+second-model F1 side by side belongs in the main results section as the direct answer to the editor's "two or more models" ask; the full breakdown (Task 8/9) is supplementary detail |
| 3 | **Rerun-stability table** (once it exists) | **Main paper, one compact table** — the full transition matrix and per-run detail move to supplement | A single row of "5/5 runs, X% exact agreement, κ=Y, F1 range [a,b]" is the direct, compact answer to "formal rerun-stability testing"; the mechanics belong in supplement |
| 4 | **Per-stratum supplementary table** (Task 4) | **Supplement** | Ten rows with several undefined cells is exactly supplementary-table material — informative for a careful reader, not headline evidence |
| 5 | **Louvain seed-sensitivity supplementary table** (Phase 0B Task 9) | **Supplement** | Same reasoning; also directly supports the decision to drop the ARI-based directional claim from the main text (Phase 0B/manuscript matrix) |
| 6 | **Error-sensitivity analysis** (Task 3) | **Main paper, one short paragraph + a small inline table** (worst/best F1 at k=1,2,3) | This is the single most direct rebuttal to the editor's specific comment and deserves visibility in the main text, not buried in supplement — but it is compact enough (3 rows) not to need a full table slot |
| 7 | **Three-way evaluation** (Task 5) | **Main paper retains the existing summary sentence; the new uncertain-class precision/recall finding is a one-sentence addition, not a new table** | Low table-budget cost for a genuinely new, informative finding |

## Avoiding manuscript overload

- Total **new** main-text table content: CIs added to the existing Table 6
  (no new table), one compact rerun-stability table, one compact
  cross-model table, and a 3-row error-sensitivity table (could be merged
  into the same figure/table as the rerun-stability summary to conserve
  budget).
- Total **new** supplementary tables: per-stratum performance,
  Louvain seed-sensitivity, full rerun-stability transition matrix and
  per-run detail, full cross-model agreement/error-overlap breakdown.
- This keeps the main paper's table count to roughly the same order as
  before repair (Table 6 gains columns, not rows; two new compact tables
  are added for rerun-stability and cross-model results — both are
  requirements the editor explicitly asked for, so their presence in the
  main text is well-justified rather than scope creep) while pushing
  genuinely detailed/exploratory material to supplement, consistent with
  how the per-stratum and seed-sensitivity material is already scoped in
  this repair.

## Figures

No new main-text figure is proposed here. Figure 2 (once rebuilt from the
corrected map, Phase 0B Task 11) remains the sole downstream-analysis
figure; its caption should be updated to report the Q value as a median
with the seed-sensitivity range (Phase 0B), not a bare point estimate.
