# M7 primary gold-standard freeze

Generated: 2026-09-09T13:37:08.198589+00:00

Definitive 900-pair prospective primary gold standard: direct-agreement label for the 614 corrected-H2 agreement rows, third-adjudicator label for the 286 corrected-H2 disagreement rows. No other rule was used. The superseded original Annotator-2 diabetes labels never influenced the gold label.

## Final gold distribution

### Overall (N=900)

- match: 264 (0.2933)
- non-match: 629 (0.6989)
- uncertain: 7 (0.0078)

### Circular Economy (N=400)

- match: 103 (0.2575)
- non-match: 291 (0.7275)
- uncertain: 6 (0.015)

### Diabetes Mellitus (N=500)

- match: 161 (0.322)
- non-match: 338 (0.676)
- uncertain: 1 (0.002)

## Corrected pre-adjudication agreement (reproduced independently)

- overall: N=900, agreements=614, disagreements=286, raw=0.6822, kappa=0.3099
- circular_economy: N=400, agreements=258, disagreements=142, raw=0.645, kappa=0.3051
- biomedical_diabetes_mellitus: N=500, agreements=356, disagreements=144, raw=0.712, kappa=0.3361

## Adjudication outcomes

- Disagreements adjudicated: 286
- CE rows: 142, Diabetes rows: 144
- Final adjudicated label distribution: {'match': 124, 'non-match': 158, 'uncertain': 4}
- Adjudicator context use: 1 (0.0035)
- Selection kind: {'selected_one_of_the_two_proposed': 280, 'selected_third_label_not_proposed': 6}
- By disagreement type: {'match vs non-match': {'match': 112, 'non-match': 120, 'uncertain': 1}, 'match vs uncertain': {'match': 11, 'non-match': 4, 'uncertain': 2}, 'non-match vs uncertain': {'non-match': 34, 'match': 1, 'uncertain': 1}}

## Human context-use summary (descriptive only)

- annotator_1_context_use_count: 6
- annotator_1_context_use_rate: 0.0067
- annotator_2_corrected_context_use_count: 2
- annotator_2_corrected_context_use_rate: 0.0022
- adjudicator_context_use_count: 1
- adjudicator_context_use_rate: 0.0035
- gold_from_direct_agreement_without_either_context: 610
- gold_from_direct_agreement_with_at_least_one_context: 4
- gold_from_adjudication_without_adjudicator_context: 285
- gold_from_adjudication_with_adjudicator_context: 1
- Descriptive only -- no claim is made that context use caused better or worse decisions.

## Human annotation flow

- Prospective primary pairs: 900
- Direct agreements: 614
- Disagreements requiring adjudication: 286
- Final gold: 900
- Partition: {'circular_economy': 400, 'biomedical_diabetes_mellitus': 500}

Provenance:
- The original Annotator-2 diabetes annotation (500 pairs, all labelled identically) was identified as a degenerate constant-label quality anomaly during a dedicated diagnostic.
- No technical/GUI defect was found to explain it.
- The same, independent Annotator 2 re-annotated the same 500 diabetes pairs after a mandatory synthetic comprehension gate, in a new random order, with no access to the original diabetes labels.
- The original labels were preserved (never deleted) but are superseded and do not influence the gold label or the reported agreement figures.
- The corrected annotation set (original CE 400 + re-annotated diabetes 500) was used for all agreement computation and adjudication reported here.

## Verification

- Row-by-row verification passed: True
- Direct-agreement rows: 614, adjudicated rows: 286
- CE rows: 400, Diabetes rows: 500