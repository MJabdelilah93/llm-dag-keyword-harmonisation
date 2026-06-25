# Data Directory

## Overview

This directory contains derived keyword frequency tables and the benchmark annotation
infrastructure. Raw corpus data and files containing Scopus-derived keyword strings
are **not** publicly available due to Elsevier/Scopus licensing restrictions.

---

## Included — no redistribution restrictions

### `derived/`

Keyword frequency tables derived from the corpus. These files contain only
aggregate frequency counts, not raw record metadata.

| File | Description |
|------|-------------|
| `author_keyword_frequencies.csv` | Frequency count per unique author keyword string |
| `index_keyword_frequencies.csv` | Frequency count per unique index keyword string |
| `corpus_summary_report.txt` | Summary statistics of the Scopus corpus |

---

## Restricted — contains Scopus-derived keyword strings

The following files in `data/benchmark/` contain actual author keyword strings
derived from Scopus records. They are **not redistributable** under Elsevier's
Terms of Use and are archived under restricted access on Zenodo:
**https://doi.org/10.5281/zenodo.19451886**

| File | Description |
|------|-------------|
| `gold_benchmark.csv` | 500-pair adjudicated benchmark |
| `dev_set.csv` | Development set (351 pairs) |
| `test_set.csv` | Held-out test set (149 pairs) |
| `candidate_pairs.csv` | Full candidate pool before stratified sampling |
| `annotation_sheet_annotator1_COMPLETED.csv` | Completed annotations, Annotator 1 |
| `annotation_sheet_annotator2_COMPLETED.csv` | Completed annotations, Annotator 2 |
| `disagreement_pairs.csv` | 57 pairs requiring adjudication |
| `adjudication_sheet.csv` | Adjudicated decisions with rationale |
| `agreement_statistics.csv` | Inter-annotator agreement statistics |
| `pilot_annotator1_COMPLETED.csv` | Pilot round labels, Annotator 1 |
| `pilot_annotator2_COMPLETED.csv` | Pilot round labels, Annotator 2 |

To access these files, submit an access request on the Zenodo record page.

---

## Reconstructing the corpus

To reproduce the corpus from scratch, retrieve records from Scopus using the
queries in `configs/scopus_batch_queries.yaml` and follow the step-by-step
procedure in `docs/reproducibility.md`.

**Retrieval date used in the paper:** 3 April 2026.  
Minor differences are expected if the query is re-run at a later date.
