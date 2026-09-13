# Human annotation flow (M7 primary benchmark)

These are CONSORT-like COUNTS only -- no keyword strings.

- Prospective primary pairs: 900
- Initial corrected double annotation: 900
- Direct agreements: 614
- Disagreements requiring adjudication: 286
- Final gold: 900
- Partition: circular_economy=400, biomedical_diabetes_mellitus=500

## Provenance (the diabetes re-annotation correction)

- The original Annotator-2 diabetes annotation (500 pairs, all labelled identically) was identified as a degenerate constant-label quality anomaly during a dedicated diagnostic.
- No technical/GUI defect was found to explain it.
- The same, independent Annotator 2 re-annotated the same 500 diabetes pairs after a mandatory synthetic comprehension gate, in a new random order, with no access to the original diabetes labels.
- The original labels were preserved (never deleted) but are superseded and do not influence the gold label or the reported agreement figures.
- The corrected annotation set (original CE 400 + re-annotated diabetes 500) was used for all agreement computation and adjudication reported here.