# Corrected H2 inter-annotator agreement (after diabetes re-annotation)

Generated: 2026-09-09T09:30:56.196923+00:00

SUPERSEDES the diabetes-domain figures in PRIMARY_H1_INTERANNOTATOR_AGREEMENT.md (that report is preserved unchanged as provenance). Annotator 2's circular-economy labels are byte-identical to the original H1 completion (verified below); Annotator 2's diabetes labels come from the independent re-annotation session (new randomised order, mandatory comprehension gate, no access to the superseded original diabetes labels).

## Overall (N=900)
- N: 900
- Agreements: 614
- Disagreements: 286
- Raw agreement proportion: 0.6822
- Cohen's kappa (inter-annotator agreement, nominal 3-class): 0.3099
- Annotator 1 label distribution: {'non-match': 623, 'match': 267, 'uncertain': 10}
- Corrected Annotator 2 label distribution: {'non-match': 588, 'match': 263, 'uncertain': 49}
- Confusion matrix (rows=Annotator 1, cols=corrected Annotator 2):

  | | match | non-match | uncertain |
  |---|---:|---:|---:|
  | **match** | 140 | 113 | 14 |
  | **non-match** | 120 | 471 | 32 |
  | **uncertain** | 3 | 4 | 3 |

## Circular Economy only (N=400)
- N: 400
- Agreements: 258
- Disagreements: 142
- Raw agreement proportion: 0.645
- Cohen's kappa (inter-annotator agreement, nominal 3-class): 0.3051
- Annotator 1 label distribution: {'non-match': 290, 'match': 103, 'uncertain': 7}
- Corrected Annotator 2 label distribution: {'non-match': 209, 'match': 170, 'uncertain': 21}
- Confusion matrix (rows=Annotator 1, cols=corrected Annotator 2):

  | | match | non-match | uncertain |
  |---|---:|---:|---:|
  | **match** | 74 | 25 | 4 |
  | **non-match** | 93 | 182 | 15 |
  | **uncertain** | 3 | 2 | 2 |

## Diabetes Mellitus only (N=500, corrected)
- N: 500
- Agreements: 356
- Disagreements: 144
- Raw agreement proportion: 0.712
- Cohen's kappa (inter-annotator agreement, nominal 3-class): 0.3361
- Annotator 1 label distribution: {'non-match': 333, 'match': 164, 'uncertain': 3}
- Corrected Annotator 2 label distribution: {'non-match': 379, 'match': 93, 'uncertain': 28}
- Confusion matrix (rows=Annotator 1, cols=corrected Annotator 2):

  | | match | non-match | uncertain |
  |---|---:|---:|---:|
  | **match** | 66 | 88 | 10 |
  | **non-match** | 27 | 289 | 17 |
  | **uncertain** | 0 | 2 | 1 |

## Disagreement types (overall, unordered)

- match vs non-match: 233
- non-match vs uncertain: 36
- match vs uncertain: 17
- other/malformed: 0

## Context-use cross-tabulation (overall)

| Pattern | N | Proportion of total | Disagreements | Disagreement rate |
|---|---:|---:|---:|---:|
| neither | 892 | 0.9911 | 282 | 0.3161 |
| annotator_1_only | 6 | 0.0067 | 4 | 0.6667 |
| annotator_2_only | 2 | 0.0022 | 0 | 0.0 |
| both | 0 | 0.0 | 0 | None |

## Provenance

The ORIGINAL H2 report (PRIMARY_H1_INTERANNOTATOR_AGREEMENT.{json,md}) is preserved unchanged for provenance. Its diabetes-domain figures are SUPERSEDED by this corrected report; its overall and circular-economy figures are unaffected/reproduced here. This corrected report is the one to use going forward.