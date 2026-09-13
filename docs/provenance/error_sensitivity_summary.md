# Phase 1A Task 3 — Error-Sensitivity Analysis

## Method

Exact (not sampled) combinatorial enumeration. The 124 gold-decided test
pairs sit in TP=41, FP=1, FN=2, TN=80. A single changed decision moves one
pair between the two cells that share its gold label (TP↔FN for
gold=match; FP↔TN for gold=non-match). For k = 1, 2, 3 changed decisions,
every valid combination of such moves was enumerated exactly (4, 9, and 15
valid combinations respectively — small enough for exhaustive search, no
approximation), and precision/recall/F1/accuracy computed for each. Best
case and worst case are the true maximum and minimum across that exhaustive
set — neither was chosen to make a point; both come from the same search.

Full detail: `results/current_paper/error_sensitivity_analysis.json` (per-k
summary) and `results/current_paper/error_sensitivity_all_combinations.csv`
(every enumerated combination).

## Results

| k | F1 worst case | F1 baseline | F1 best case | Range |
|---|---|---|---|---|
| 1 | 0.9524 (−0.0123) | 0.9647 | 0.9767 (+0.0120) | 0.0243 |
| 2 | 0.9398 (−0.0249) | 0.9647 | 0.9885 (+0.0238) | 0.0487 |
| 3 | 0.9268 (−0.0379) | 0.9647 | 1.0000 (+0.0353) | 0.0732 |

- **Worst case, k=1**: one true positive relabelled a false negative
  (recall drops from 0.9535 to 0.9302). F1 falls to 0.9524.
- **Worst case, k=3**: three true positives relabelled false negatives
  (the single worst-case direction at every k tested — converting TPs to
  FNs consistently hurts more than converting TNs to FPs, because the
  gold-match pool is small, n=43). F1 falls to 0.9268 — a 3.8-point drop
  from a single-digit number of relabelled decisions.
- **Best case, k=3**: fixing both current false negatives and the single
  false positive yields a perfect F1 = 1.0 on this test set — illustrating
  that the *current* result is itself only 3 decisions away from a
  perfect score in either direction.

## Direct answer to the editor's "three errors" comment

A swing of **0.0732 in F1** (worst case 0.9268 to best case 1.0000) from
changing only 3 of 124 decided decisions is a direct, exact, quantitative
demonstration that the current test set is exactly as fragile as the
editor's comment suggested. This is reported here for transparency, **not**
as a claim that the existing 149-pair test set has become sufficient — the
opposite: it is presented as direct supporting evidence for why the
enhanced study's substantially larger test set (Mayr requirement 5) is
necessary. No scenario here was manufactured to be favourable; both
directions are reported from the same exhaustive enumeration.
