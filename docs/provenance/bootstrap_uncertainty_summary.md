# Phase 1A Task 2 — Bootstrap Uncertainty Analysis

## Method

Pair-level bootstrap resampling with replacement over all 149 held-out
test pairs (not restricted to the "decided" subset, so that resampled
coverage/abstention is correctly propagated). N = 10,000 resamples,
`random.Random(42)` (Python standard library, not numpy, for a
dependency-light and independently checkable procedure). Percentile CI
(2.5th/97.5th percentile of the resampled statistic) — a simple, slightly
conservative choice appropriate at n=149; not bias-corrected-and-accelerated
(BCa), which would require more assumptions than this benchmark's size
comfortably supports. Paired differences (Full_LLM_DAG − B3,
Full_LLM_DAG − B6) reuse the identical resample index list for both
methods at each iteration, so the CI on the difference correctly reflects
the pairing (same 149 test pairs for every method).

Full per-method results: `results/current_paper/bootstrap_uncertainty_per_method.csv`.
Paired differences: `results/current_paper/bootstrap_uncertainty_differences.csv`.

## Headline results (95% bootstrap CI)

| Method | F1 | 95% CI | Coverage |
|---|---|---|---|
| B1 Exact | 0.436 | [0.261, 0.594] | 1.000 |
| B2 Normalised | 0.436 | [0.261, 0.594] | 1.000 |
| B3 Jaro-Winkler | 0.846 | [0.747, 0.925] | 1.000 |
| B4 TF-IDF | 0.786 | [0.675, 0.875] | 1.000 |
| B5 Embedding | 0.806 | [0.692, 0.896] | 1.000 |
| B6 Naive LLM | 0.886 | [0.805, 0.950] | 0.993 |
| **Full LLM-DAG** | **0.965** | **[0.917, 1.000]** | **0.926** |

Every point estimate matches the values independently re-verified across
Phase 0A, Phase 0B, and this analysis exactly. The CI widths — roughly
±0.05-0.10 F1 for most methods — are a direct, quantitative expression of
the "three errors" fragility already established via denominator analysis:
they are wide relative to the 3-decimal precision at which these numbers
are typically quoted in the manuscript.

## Paired differences (does the CI exclude zero?)

| Comparison | Metric | Point difference | 95% CI | Excludes zero? |
|---|---|---|---|---|
| LLM-DAG − B3 | Precision | +0.033 | [−0.049, 0.128] | No |
| LLM-DAG − B3 | Recall | +0.186 | [0.077, 0.311] | **Yes** |
| LLM-DAG − B3 | F1 | +0.119 | [0.043, 0.212] | **Yes** |
| LLM-DAG − B6 | Precision | +0.110 | [0.026, 0.210] | **Yes** |
| LLM-DAG − B6 | Recall | +0.047 | [−0.044, 0.143] | No |
| LLM-DAG − B6 | F1 | +0.078 | [0.017, 0.153] | **Yes** |

## Interpretation — do not overinterpret

The F1 advantage over both B3 and B6 is reasonably well supported (the CI
on the difference excludes zero for F1 in both comparisons). However:

- The **precision** advantage over B3 is **not** distinguishable from zero
  at this sample size — B3 already achieves near-ceiling precision (0.943,
  CI up to 1.0), and the observed +0.033 point difference is well within
  bootstrap noise.
- The **recall** advantage over B6 is likewise **not** distinguishable
  from zero — B6's recall (0.907) is already close to Full LLM-DAG's
  (0.954).
- These are not null results to be hidden — they are an honest description
  of what a 149-pair (124-decided-pair) benchmark can and cannot
  distinguish. The manuscript should report the CIs alongside the point
  estimates (see `CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md`, item 16)
  rather than implying a precision entirely justified by three decimal
  places.
- No formal multiple-comparisons correction was applied across the six
  paired-difference tests above; with only two comparisons of real
  interest (vs. B3, vs. B6) pre-specified by this task, this is a minor
  consideration, noted for completeness rather than acted on.
