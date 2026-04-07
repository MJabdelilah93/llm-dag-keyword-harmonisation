# Data Directory

## Overview

This directory contains the benchmark dataset and derived keyword frequency files. Raw corpus data is not included in this repository due to Elsevier/Scopus licensing restrictions.

## Included Files

### `benchmark/`
The 500-pair benchmark for pairwise concept equivalence evaluation.

| File | Description |
|------|-------------|
| `gold_benchmark.csv` | Full 500-pair annotated benchmark (pair_id, keyword_a, keyword_b, gold_label, stratum) |
| `dev_set.csv` | Development set (351 pairs, used for threshold tuning only) |
| `test_set.csv` | Test set (149 pairs, used for final evaluation only) |
| `candidate_pairs.csv` | Full candidate pool before stratified sampling |
| `annotation_sheet.csv` | Raw annotation template |
| `annotation_sheet_annotator1_COMPLETED.csv` | Completed annotations, Annotator 1 |
| `annotation_sheet_annotator2_COMPLETED.csv` | Completed annotations, Annotator 2 |
| `disagreement_pairs.csv` | The 57 pairs requiring adjudication |
| `adjudication_sheet.csv` | Adjudicated decisions with rationale |
| `agreement_statistics.csv` | Inter-annotator agreement statistics (κ) |
| `agreement_report.txt` | Full agreement computation report |
| `pilot_annotator1_COMPLETED.csv` | Pilot round, Annotator 1 (50 pairs) |
| `pilot_annotator2_COMPLETED.csv` | Pilot round, Annotator 2 (50 pairs) |
| `table3_populated.csv` | Benchmark composition by stratum and label (Table 3 in paper) |

### `derived/`
Keyword frequency tables derived from the corpus (included — no raw records).

| File | Description |
|------|-------------|
| `author_keyword_frequencies.csv` | Frequency of each author keyword string (55,425 unique terms) |
| `index_keyword_frequencies.csv` | Frequency of each index keyword string |
| `corpus_summary_report.txt` | Summary statistics of the Scopus corpus |

## Excluded Files (Licensing)

The following files are excluded from this repository under Elsevier's Terms of Use for Scopus data, which prohibit redistribution of raw export files:

| File | Description |
|------|-------------|
| `raw/scopus_ce_batch1_2017_2021.csv` | Scopus CSV export, circular economy articles 2017–2021 (8,862 records) |
| `raw/scopus_ce_batch1_2017_2021.ris` | Scopus RIS export, batch 1 |
| `raw/scopus_ce_batch2_2022_2024.csv` | Scopus CSV export, circular economy articles 2022–2024 (17,673 records) |
| `raw/scopus_ce_batch2_2022_2024.ris` | Scopus RIS export, batch 2 |
| `interim/scopus_ce_merged_deduped.csv` | Merged and deduplicated corpus (26,535 records) |

## Reconstructing the Corpus

To reproduce the corpus, retrieve records from Scopus using the following queries (requires institutional Scopus access):

**Batch 1 (2017–2021)**
```
TITLE-ABS-KEY("circular economy" OR "circular economies")
AND PUBYEAR > 2016 AND PUBYEAR < 2022
AND (LIMIT-TO(DOCTYPE, "ar") OR LIMIT-TO(DOCTYPE, "re"))
AND (LIMIT-TO(LANGUAGE, "English"))
```
Expected: 8,862 records. Export as CSV with all fields.

**Batch 2 (2022–2024)**
```
TITLE-ABS-KEY("circular economy" OR "circular economies")
AND PUBYEAR > 2021 AND PUBYEAR < 2025
AND (LIMIT-TO(DOCTYPE, "ar") OR LIMIT-TO(DOCTYPE, "re"))
AND (LIMIT-TO(LANGUAGE, "English"))
```
Expected: 17,673 records. Export as CSV with all fields.

Save exports to `data/raw/` with filenames matching the excluded files above, then run:
```bash
python scripts/ingest_profile.py
```
This produces `data/interim/scopus_ce_merged_deduped.csv` (deduplication by EID) and `data/derived/author_keyword_frequencies.csv`.

**Retrieval date:** 3 April 2026. Minor differences are expected if the query is re-run at a later date due to ongoing Scopus indexing.
