# Primary H1 inter-annotator agreement (900-pair benchmark)

Generated: 2026-09-08T17:09:26.447830+00:00

Both completed workbooks passed independent validation (900 rows each, 400 CE + 500 diabetes, unique pair_ids, all labels/context_used values from the allowed sets, no changed strings, no system metadata). Terminology: figures below are reported as *inter-annotator agreement* (Cohen's kappa), never as "reliability".

## Overall (N=900)
- N: 900
- Agreements: 422
- Disagreements: 478
- Raw agreement proportion: 0.4689
- Cohen's kappa (inter-annotator agreement, nominal 3-class): 0.1408
- Annotator 1 label distribution: {'non-match': 623, 'match': 267, 'uncertain': 10}
- Annotator 2 label distribution: {'match': 670, 'non-match': 209, 'uncertain': 21}
- Confusion matrix (rows=Annotator 1, cols=Annotator 2):

  | | match | non-match | uncertain |
  |---|---:|---:|---:|
  | **match** | 238 | 25 | 4 |
  | **non-match** | 426 | 182 | 15 |
  | **uncertain** | 6 | 2 | 2 |

## Circular Economy only (N=400)
- N: 400
- Agreements: 258
- Disagreements: 142
- Raw agreement proportion: 0.645
- Cohen's kappa (inter-annotator agreement, nominal 3-class): 0.3051
- Annotator 1 label distribution: {'non-match': 290, 'match': 103, 'uncertain': 7}
- Annotator 2 label distribution: {'non-match': 209, 'match': 170, 'uncertain': 21}
- Confusion matrix (rows=Annotator 1, cols=Annotator 2):

  | | match | non-match | uncertain |
  |---|---:|---:|---:|
  | **match** | 74 | 25 | 4 |
  | **non-match** | 93 | 182 | 15 |
  | **uncertain** | 3 | 2 | 2 |

## Diabetes Mellitus only (N=500)
- N: 500
- Agreements: 164
- Disagreements: 336
- Raw agreement proportion: 0.328
- Cohen's kappa (inter-annotator agreement, nominal 3-class): 0.0
- Annotator 1 label distribution: {'non-match': 333, 'match': 164, 'uncertain': 3}
- Annotator 2 label distribution: {'match': 500}
- Confusion matrix (rows=Annotator 1, cols=Annotator 2):

  | | match | non-match | uncertain |
  |---|---:|---:|---:|
  | **match** | 164 | 0 | 0 |
  | **non-match** | 333 | 0 | 0 |
  | **uncertain** | 3 | 0 | 0 |

## Disagreement types (overall, unordered)

- match vs non-match: 451
- match vs uncertain: 10
- non-match vs uncertain: 17
- other/malformed: 0

### Directional breakdown

- annotator_1=non-match / annotator_2=match: 426
- annotator_1=uncertain / annotator_2=match: 6
- annotator_1=non-match / annotator_2=uncertain: 15
- annotator_1=match / annotator_2=non-match: 25
- annotator_1=uncertain / annotator_2=non-match: 2
- annotator_1=match / annotator_2=uncertain: 4

## Context-use cross-tabulation (overall)

| Pattern | N | Proportion of total | Disagreements | Disagreement rate |
|---|---:|---:|---:|---:|
| neither | 892 | 0.9911 | 474 | 0.5314 |
| annotator_1_only | 6 | 0.0067 | 4 | 0.6667 |
| annotator_2_only | 2 | 0.0022 | 0 | 0.0 |
| both | 0 | 0.0 | 0 | None |

## Historical context only (NOT a statistical comparison)

- Legacy pilot/full-round Cohen's kappa (original benchmark): 0.8075
- This is the ORIGINAL legacy benchmark's full-round Cohen's kappa, included here purely as historical background. It is NOT a statistical comparison against the new 900-pair benchmark's agreement figures above -- different annotators, different pairs, different domains.

## Notable observation (reported factually, no root-cause speculation)

Annotator 2's label distribution for the diabetes-mellitus domain is {'match': 500} -- i.e. every one of the 500 diabetes pairs was labelled 'match' by Annotator 2, which is why that domain's Cohen's kappa is exactly 0.0 despite a 32.8% raw overlap (a rater with a degenerate, constant label has, by definition, zero agreement beyond chance). Annotator 2's circular-economy distribution for the same annotator over the same session is varied and unremarkable. This pattern is flagged here for human review before relying on the diabetes-domain adjudication outcome -- no cause is asserted.