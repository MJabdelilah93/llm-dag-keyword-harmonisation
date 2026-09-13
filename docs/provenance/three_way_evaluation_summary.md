# Phase 1A Task 5 — Three-Way Classification Analysis

Full data: `results/current_paper/three_way_evaluation.json`,
`results/current_paper/three_way_confusion_matrix.csv`.

## Confusion matrix (gold rows × predicted columns, n=149)

| Gold \\ Pred | match | non_match | uncertain |
|---|---|---|---|
| match (43) | 41 | 2 | 0 |
| non_match (81) | 1 | 80 | 0 |
| uncertain (25) | 1 | 13 | 11 |

## Headline numbers

| Metric | Value |
|---|---|
| Overall accuracy | 0.8859 |
| Macro-F1 | 0.8246 |
| Match: precision / recall / F1 | 0.9535 / 0.9535 / 0.9535 |
| Non-match: precision / recall / F1 | 0.8421 / 0.9877 / 0.9091 |
| Uncertain: precision / recall / F1 | **1.0000** / **0.4400** / 0.6111 |

## Consistency check against existing manuscript-proxy statements

`INTERNAL_PROJECT_STATE.md` states "11 correct abstentions, 14 missed
abstentions, 0 incorrect abstentions" for the primary model — this matches
exactly: the uncertain row's confusion-matrix cells are 11 (correct,
gold=uncertain & pred=uncertain), 14 (missed, gold=uncertain & pred≠
uncertain: 1+13), and both off-diagonal cells in the match/non_match rows
for pred=uncertain are 0 (no incorrect abstentions — the model never
abstained on a pair with a decided gold label). Overall accuracy (0.8859)
matches `results/test_results_summary.txt`'s `three_way_acc` field for
Full_LLM_DAG exactly.

## Flag for manuscript wording

The manuscript's existing framing emphasises that the guard produces
**zero incorrect abstentions**, which is accurate and worth keeping.
However, this analysis surfaces a complementary point not currently
stated as a class-level metric anywhere in the existing manuscript-proxy
documents: **the uncertain class has perfect precision (1.00) but low
recall (0.44)**. In plain terms: whenever the model does abstain, it is
always right to — but it fails to abstain on the majority (56%, 14/25) of
pairs that the gold-standard annotators considered genuinely ambiguous.
This is a real, class-level asymmetry that the current "0 incorrect
abstentions" framing does not fully convey, and should be added to the
three-way evaluation subsection (see
`CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md`, updated item on the
three-way evaluation, Phase 1A) — classified as ADD NEW RESULT, not a
correction to an existing wrong number.
