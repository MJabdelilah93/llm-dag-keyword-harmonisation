# Diabetes-mellitus licence independent audit

Generated: 2026-09-07T10:32:55.164799+00:00

Recomputed directly from `strengthening/data_pmc/pmc_diabetes_article_inventory.csv` row-level `licence_code` values and the acquisition manifest -- not copied from any prior summary field.

## Pipeline stage counts
- Raw query result count (esearch, unfiltered): 141860
- Fetched: 15106
- Parsed: 15106
- Unique PMCID: 15106
- English-eligible: 15098
- Date-eligible: 15093
- Topic-eligible (title/abstract only): 14913
- Abstract present: 14851

## Licence classification (independently recomputed, all 15,106 articles)
| Bucket | Count |
|---|---:|
| CC BY | 12977 |
| CC0 | 76 |
| CC BY-SA | 0 |
| CC BY-NC | 684 |
| CC BY-NC-SA | 196 |
| CC BY-NC-ND | 869 |
| other Creative Commons | 8 |
| publisher/custom | 0 |
| missing/unclassified | 296 |
| other | 0 |

Raw licence_code breakdown: {'by': 12977, 'by-nc-nd': 869, 'by-nc': 684, 'unknown': 215, 'by-nc-sa': 196, 'none': 81, 'cc0': 76, 'by-nd': 8}
Unmapped codes (if any): []

## CC BY/CC0 x keyword-group crosstab
- CC BY/CC0 articles with any keyword group: 12474
- CC BY/CC0 articles with a confidently-author keyword group: 1073
- **Fully eligible strict articles: 1066**
- Strict keyword occurrences: 6029
- Strict unique keyword strings: 4092
- Strict contributing articles: 1066

## Verdict on the previously reported '12,364 CC BY' figure
**Status: CORRECTED**

12,364 does not appear in any committed data or report file (verified by direct search). It was a transcription error in the prior conversational summary text, not a computation or data error -- the underlying strengthening/reports/pmc_diabetes_feasibility.json already contained the correct value (cc_by_count=12977), matching this independent recomputation exactly.

Independently recomputed CC BY = **12977**; CC0 = **76**. The prior summary field in `strengthening/reports/pmc_diabetes_feasibility.json` already stated cc_by_count=12977, cc0_count=76 -- matching this independent recomputation. No committed file required correction; `strengthening/reports/pmc_diabetes_feasibility.json`/`.md` are confirmed accurate and are NOT modified by this audit (this file is an independent addendum, per instruction not to overwrite evidence silently).