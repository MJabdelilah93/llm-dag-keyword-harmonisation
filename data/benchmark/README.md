# data/benchmark/ — Restricted

This directory previously contained the 500-pair gold-standard benchmark,
annotation files, pilot round labels, and adjudication records.

These files contain Scopus-derived author keyword strings and are not
publicly redistributable under Elsevier's Terms of Use.

**Access:** Request access via the restricted Zenodo dataset record:
https://doi.org/10.5281/zenodo.19451886

**Contents available on Zenodo:**
- `gold_benchmark.csv` — 500 adjudicated pairs with labels and strata
- `dev_set.csv` — development set (351 pairs)
- `test_set.csv` — held-out test set (149 pairs)
- `annotation_sheet_annotator{1,2}_COMPLETED.csv` — completed annotations
- `adjudication_sheet.csv` — adjudicator decisions with rationale
- `agreement_statistics.csv` — inter-annotator agreement (κ = 0.81)
- `pilot_annotator{1,2}_COMPLETED.csv` — pilot round labels

**Reconstruction:** If you have institutional Scopus access, you can
regenerate the corpus and candidate pairs from scratch using the queries in
`configs/scopus_batch_queries.yaml` and the procedure in `docs/reproducibility.md`.
