# Phase 1A Task 4 — Per-Stratum Benchmark Analysis

Full data: `results/current_paper/per_stratum_performance.csv`. Row counts
sum to exactly 149 (the frozen test set). Stratum labels follow the
convention established in `scripts/generate_benchmark_candidates.py`: i
capitalisation/whitespace, ii spelling variants, iii acronym expansion, iv
punctuation/hyphenation, v singular/plural, vi near-synonyms (embedding
0.75–0.85), vii broader-narrower proxies (embedding 0.60–0.75), viii
ambiguous short forms, ix malformed/encoding artefacts, x weak semantic
links (embedding 0.50–0.60).

## Publication-ready supplementary table draft

| Stratum | n | Gold match | Precision | Recall | F1 | Coverage | Note |
|---|---|---|---|---|---|---|---|
| i — capitalisation | 12 | — | 1.000 | 1.000 | 1.000 | 1.000 | |
| ii — spelling variants | 13 | 0 | — | — | — | 1.000 | No gold matches in this stratum's test-set sample; precision/recall/F1 not meaningful |
| iii — acronym expansion | 17 | — | 1.000 | 0.857 | 0.923 | **0.588** | Lowest coverage of any stratum — the guard abstains most often here, consistent with this being the documented main disagreement source (κ=0.18) at annotation time |
| iv — punctuation/hyphenation | 12 | — | 1.000 | 1.000 | 1.000 | 1.000 | |
| v — singular/plural | 10 | — | 1.000 | 1.000 | 1.000 | 1.000 | Smallest stratum by n (10) — treat as directional only |
| vi — near-synonyms | 22 | — | **0.000** | **0.000** | **0.000** | 1.000 | Contains both of the model's real test-set errors: the sole FP (timber/lumber) and one of the two FNs (social/socioeconomic metabolism) |
| vii — broader-narrower proxies | 22 | 0 | — | — | — | 1.000 | No gold matches in this stratum's test-set sample |
| viii — ambiguous short forms | 18 | — | 1.000 | 1.000 | 1.000 | 1.000 | |
| ix — malformed/encoding artefacts | 11 | 0 | — | — | — | 0.636 | No gold matches; substantial abstention (36%) consistent with this being the stratum error-analysis identified as concentrating missed abstentions |
| x — weak semantic links | 12 | 0 | — | — | — | 1.000 | No gold matches in this stratum's test-set sample |

## Interpretation

- Every one of the model's errors on the held-out test set (1 FP, 2 FN)
  falls within **two** strata: vi (near-synonyms) contains the FP and one
  FN; the second FN (ICT / information communication technology (ICT)
  exploratory-exploitative innovation) falls in stratum iii per the
  original error analysis, though it is absorbed here into iii's overall
  recall of 0.857 alongside otherwise-correct decisions.
- Four strata (ii, vii, ix, x) have **zero gold-match pairs** in this
  particular 149-pair test-set draw. This is a direct consequence of the
  stratified 70/30 split applied to already-small per-stratum benchmark
  quotas (35–75 pairs per stratum in the full 500) — precision/recall/F1
  are correctly reported as undefined for these strata rather than as a
  misleading 0.0 or 1.0. This is itself informative for Phase 1's planning:
  a benchmark expansion should ensure every stratum retains gold-match
  representation in the held-out test split.
- Stratum vi's 0.000/0.000/0.000 line is a real, correctly-computed result
  — not a defect. It says precisely: on the (very few) gold-match pairs in
  this stratum, the model missed at least one, and it also produced at
  least one wrong match. Reporting this stratum's raw counts (rather than
  omitting it) is the more transparent choice.
- Stratum iii's low coverage (0.588) is consistent with, and now
  quantifies at the test-set level, the annotation-stage finding that this
  stratum was the primary source of inter-annotator disagreement.

This table is intended as a supplementary-material draft, not a
replacement for Table 6's main benchmark result — see
`docs/provenance/current_paper_result_table_plan.md` (Task 11) for where
it belongs in the manuscript's table budget.
