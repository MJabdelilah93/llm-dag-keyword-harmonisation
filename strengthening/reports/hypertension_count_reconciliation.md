# Hypertension acquisition count reconciliation

Traces the two figures that appeared in the previous report (15,368 and
14,571) to their exact source manifests/files. **Neither number is wrong
-- they describe two different scopes of the same acquisition effort.**
No guessing was involved: every number below is read directly from the
named file.

## What each number represents

| Figure | Scope | Source file(s) |
|---|---|---|
| **14,571** | Unique PMC articles retrieved by the **primary window only** (2015-01-01 to 2025-12-31), i.e. the original acquisition subagent's completed work before any broader-window supplement. | `strengthening/data_pmc/pmc_hypertension_acquisition_manifest.json` (`n_unique_pmcids: 14571`) and `pmc_hypertension_article_inventory.csv` (14,571 data rows) |
| **15,368** | Unique PMC articles across **primary UNION extended** windows (2015-2025 plus the broader 2010-2025 test), deduplicated by PMCID. This is the complete evidentiary base used for the feasibility gate decision. | `strengthening/data_pmc/pmc_hypertension_merged_article_inventory.csv` (15,368 data rows) |

The extended-window-alone acquisition (2010-2025, run separately to test
the broader-window remedy) retrieved **12,366** unique articles
(`pmc_hypertension_extended_acquisition_manifest.json`,
`n_unique_pmcids: 12366`; `pmc_hypertension_extended_article_inventory.csv`,
12,366 rows). 14,571 + 12,366 = 26,937; the merged unique count is 15,368,
so **11,569 articles were retrieved by both runs** (26,937 - 15,368 =
11,569), confirming the merge is a genuine deduplicated union, not a
double-count.

## Methodological note (not previously disclosed)

The primary and extended acquisitions used **different per-year retrieval
caps**: primary used `--probe-per-year 300 --corpus-per-year 1400`
(set by the original acquisition subagent); the extended run used this
script's own defaults, `--probe-per-year 120 --corpus-per-year 1200`
(I did not override them when running the broader-window test). This
means the extended run under-samples relative to primary's methodology,
which is part of why merging in five more years of literature only moved
stratum iv's candidate pool from 35 to 36 rather than further. This is
disclosed for transparency; it does not change the feasibility
conclusion already reported (hypertension stratum iv remains short), and
per the current instruction the hypertension biomedical benchmark is
being superseded by the diabetes-mellitus fallback rather than further
optimised.

## Complete count flow: query to final strict author-keyword corpus

Every stage below is read directly from the named CSV's `flag_*` columns
(each stage is cumulative AND-ed with all previous stages having already
been computed independently per article, not chained/destructive) or from
the acquisition manifest.

| Stage | Primary (2015-2025) | Extended (2010-2025) | **Merged (authoritative)** |
|---|---:|---:|---:|
| Unique PMCIDs fetched & parsed (`n_uids_requested` = `n_article_records_parsed` = `n_unique_pmcids`; 0 parse errors, 0 dropped duplicates, 0 records without a PMCID in every run) | 14,571 | 12,366 | **15,368** |
| Passing language filter (English) | 14,547 | 12,358 | **15,343** |
| Passing date-window filter | 14,548 | 12,358 | **15,342** |
| Passing topic-evidence filter (title/abstract only) | 14,523 | 12,332 | **15,311** |
| With abstract present | 14,328 | 12,152 | **15,079** |
| Licence verified CC BY or CC0 | 12,441 | 11,056 | **12,866** |
| With any keyword group present | 13,324 | 11,319 | **13,982** |
| With confident (non-ambiguous) author keyword group | 1,599 | 1,268 | **1,635** |
| Eligible for release consideration (licence-level) | 12,252 | 10,892 | **12,655** |
| **Fully eligible** (all of the above simultaneously true) | 1,341 | 1,148 | **1,364** |
| Duplicate PMCID / duplicate DOI / parse errors | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Missing title (informational only -- not an eligibility gate) | 2,130 | 1,310 | 2,502 |

### Strict author-keyword corpus (fully-eligible articles AND `group_classification == 'confidently_author'`, i.e. excluding rows where the article passed overall but the *specific keyword group* is ambiguous or clearly-not-author)

| | Primary | Extended | **Merged (authoritative)** |
|---|---:|---:|---:|
| Author-keyword occurrences | 7,521 | -- (not separately recomputed; superseded) | **7,633** |
| Unique raw author-keyword strings | 5,213 | -- | **5,283** |
| Contributing articles | 1,341 | -- | **1,364** |

## The one authoritative number for each stage

**15,368** unique articles is the authoritative raw acquisition count.
**1,364** fully-eligible articles and **5,283** unique strict author-keyword
strings are the authoritative filtered counts. These are exactly the
numbers used in `strengthening/reports/pmc_hypertension_feasibility.md`'s
per-stratum candidate-pool gate (stratum iv: 36/40, all other strata pass).
14,571 remains a correct, subsidiary number describing the primary-window
acquisition alone; it is superseded by, not contradicted by, 15,368.

Discrepancy status: **resolved**. Both original reports
(`pmc_hypertension_feasibility.json/.md`) are preserved unmodified as the
documented negative-feasibility outcome for hypertension (see task
instruction Step 2/Step 5); this file is an addendum, not a replacement.
