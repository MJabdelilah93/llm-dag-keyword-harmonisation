# C4 — Diabetes strict author-keyword frequency descriptive audit

Read-only descriptive-summary task for M7 Table 2. No new data retrieved, no API call made, no
benchmark/annotation/frozen result changed. This file is the only artefact created; nothing was
committed (per instruction).

## Authoritative input identification

- **File**: `strengthening/data_pmc/pmc_diabetes_author_keywords_raw.csv`
- **SHA-256**: `c1e5090f1b13144aaf393bd2384e19d728d730d6c8bc3a27aabaf57a179778a9`
  — independently recomputed from the file on disk and matches the value already frozen in
  `strengthening/reports/B8_DENSE_CANDIDATE_GENERATION.json` →
  `universes.biomedical_diabetes_mellitus.source_sha256` exactly.
- **Filter applied**: the exact, unmodified `load_strict_eligible_keywords()` filter from
  `strengthening/candidate_gen/generate_diabetes_candidates.py` (lines 70-74):
  `kw[(kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author")]`.

## Prerequisite verification (performed BEFORE any frequency calculation)

| Statistic | Frozen value | Reproduced value | Match |
|---|---:|---:|---|
| Fully-eligible contributing articles (`pmcid.nunique()`) | 1,066 | 1,066 | **YES** |
| Confidently-author keyword occurrences (`len(strict)`) | 6,029 | 6,029 | **YES** |
| Unique raw author-keyword strings (`keyword_raw.nunique()`) | 4,092 | 4,092 | **YES** |

All three prerequisite totals matched exactly. Calculation proceeded.

## Results (denominator = 4,092 unique keyword strings, per instruction)

| Statistic | Count | Percentage |
|---|---:|---:|
| Unique keyword strings with frequency = 1 (singletons) | **3,527** | **86.2%** |
| Unique keyword strings with frequency ≥ 5 | **109** | **2.7%** |
| Unique keyword strings with frequency ≥ 10 | **43** | **1.1%** |

Sum of all per-keyword frequencies over the 4,092 unique strings: 6,029 — matches the frozen
occurrence total exactly (internal consistency check).

## Exact code/command used

Primary computation (pandas, reusing the exact same filter and the exact same groupby-based
frequency construction as `generate_diabetes_candidates.py:build_frequency_and_provenance`):

```python
import pandas as pd

p = "strengthening/data_pmc/pmc_diabetes_author_keywords_raw.csv"
kw = pd.read_csv(p, low_memory=False)
strict = kw[(kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author")].copy()

freq_df = strict.groupby("keyword_raw").size().reset_index(name="frequency")
assert len(freq_df) == 4092

n_singleton = int((freq_df["frequency"] == 1).sum())
n_ge5 = int((freq_df["frequency"] >= 5).sum())
n_ge10 = int((freq_df["frequency"] >= 10).sum())
denom = 4092
# singleton: 3527 (86.2%); f>=5: 109 (2.7%); f>=10: 43 (1.1%)
```

## Independent cross-check

A second, structurally independent method — `collections.Counter` over the raw `keyword_raw`
column values (no pandas `groupby`, no shared aggregation code path with the primary method) —
was run against the same filtered `strict` dataframe:

```python
from collections import Counter

counter = Counter(strict["keyword_raw"].tolist())
assert len(counter) == 4092
c_singleton = sum(1 for v in counter.values() if v == 1)
c_ge5 = sum(1 for v in counter.values() if v >= 5)
c_ge10 = sum(1 for v in counter.values() if v >= 10)
```

Result: `(c_singleton, c_ge5, c_ge10) == (3527, 109, 43)` — **identical to the primary method**,
and `sum(counter.values()) == 6029`, matching the frozen occurrence total. Cross-check: **PASS**.

## Status

No file other than this report was created or modified. No frozen scientific result was altered.
Not committed (per instruction — pending explicit commit approval).
