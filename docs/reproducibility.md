# Reproducibility Guide

Step-by-step instructions for a licensed Scopus user to regenerate the corpus
and reproduce the benchmark results from scratch.

**Paper reference:** El Majjaoui et al. (2026), Section 2.6.  
**Requirements:** Python 3.10+, institutional Scopus access, Anthropic API key.

---

## Step 1: Clone the repository

```bash
git clone https://github.com/MJabdelilah93/llm-dag-keyword-harmonisation.git
cd llm-dag-keyword-harmonisation
git checkout v1.0.0
pip install -r requirements.txt
```

---

## Step 2: Retrieve the corpus from Scopus

Run both queries in Scopus Advanced Search on **3 April 2026** (or note the date
of your retrieval for reproducibility purposes).

**Batch 1 (2017–2021):**
```
TITLE-ABS-KEY("circular economy" OR "circular economies")
AND PUBYEAR > 2016 AND PUBYEAR < 2022
AND (LIMIT-TO(DOCTYPE, "ar") OR LIMIT-TO(DOCTYPE, "re"))
AND (LIMIT-TO(LANGUAGE, "English"))
```
Expected: 8,862 records. Export as CSV (all fields).
Save to: `data/raw/scopus_ce_batch1_2017_2021.csv`

**Batch 2 (2022–2024):**
```
TITLE-ABS-KEY("circular economy" OR "circular economies")
AND PUBYEAR > 2021 AND PUBYEAR < 2025
AND (LIMIT-TO(DOCTYPE, "ar") OR LIMIT-TO(DOCTYPE, "re"))
AND (LIMIT-TO(LANGUAGE, "English"))
```
Expected: 17,673 records. Export as CSV (all fields).
Save to: `data/raw/scopus_ce_batch2_2022_2024.csv`

---

## Step 3: Ingest and profile

```bash
python scripts/ingest_profile.py
```

Produces:
- `data/interim/scopus_ce_merged_deduped.csv` (26,535 records, dedup by EID)
- `data/derived/author_keyword_frequencies.csv` (55,425 unique strings)

---

## Step 4: Generate benchmark candidates

```bash
python scripts/generate_benchmark_candidates.py
```

Produces: `data/benchmark/candidate_pairs.csv` with all ten strata.

---

## Step 5: Run baselines (no API key needed)

```bash
python scripts/run_baselines.py
```

Reproduces Table 7 (B1–B5) from deterministic methods.

---

## Step 6: Reproduce LLM results from JSONL logs (no API key needed)

```bash
python scripts/rebuild_downstream.py
python scripts/run_error_analysis.py
```

All LLM results can be reconstructed from the archived JSONL logs without
re-running any API calls.

---

## Step 7: Re-run LLM verification (requires API key)

```bash
export ANTHROPIC_API_KEY="your-key-here"
python scripts/run_full_workflow.py
python scripts/run_ablations.py
```

Note: exact token-level reproducibility of justification text is not guaranteed
across separate API sessions even at temperature=0. Decision labels and
confidence scores are stable in practice.

---

## Step 8: Downstream comparison

```bash
python scripts/run_downstream.py
python scripts/run_downstream_analysis.py
```

---

## Step 9: Figures

```bash
python scripts/figure1_dag_workflow.py
python scripts/figure2_thematic_comparison.py
python scripts/export_vosviewer.py
```

---

## Notes on minor differences

- Scopus indexing changes over time; re-running the query after 3 April 2026
  will return additional records. Minor count differences are expected.
- JSONL log files for large downstream runs (51 MB, 27 MB) are archived on
  Zenodo: https://doi.org/10.5281/zenodo.19451886
