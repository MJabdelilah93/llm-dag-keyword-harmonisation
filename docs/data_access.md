# Data Access Guide

Explains what is available where and how to access it.

> **Two separate Zenodo records will exist after tagging v1.0.0:**
> - **Zenodo-SW** (public software record): DOI minted automatically when
>   GitHub release tag `v1.0.0` is archived via the Zenodo GitHub integration.
>   This DOI is different from the one below and will be confirmed after tagging.
> - **Zenodo-DATA** (restricted dataset record, existing deposit):
>   https://doi.org/10.5281/zenodo.19451886

---

## Openly available — this GitHub repository

| Content | Location |
|---------|----------|
| Pipeline source code | `src/` |
| Scripts | `scripts/` |
| Configuration files | `configs/` |
| Prompt templates (v1.0.0) | `prompts/v1.0.0/` |
| JSON schema for LLM output | `schemas/` |
| Documentation | `docs/` |
| Aggregate paper results (Tables 7–10) | `results/paper_v1/` |
| Synthetic examples (no corpus data) | `examples/` |
| Corpus summary statistics (no keyword strings) | `data/derived/README.md` |

---

## Public — Zenodo software record (Zenodo-SW)

Frozen GitHub release tag `v1.0.0`. Includes all openly available content
listed above. DOI will be confirmed after the release tag is created.

---

## Restricted — Zenodo dataset record (Zenodo-DATA)

**DOI:** https://doi.org/10.5281/zenodo.19451886  
Access via Zenodo access request (reason: Scopus-derived content).

| Content | Files |
|---------|-------|
| 500-pair benchmark | `benchmark/gold_benchmark.csv`, `dev_set.csv`, `test_set.csv` |
| Annotation and adjudication files | `benchmark/annotation_sheet_annotator*.csv`, `adjudication_sheet.csv` |
| LLM decision logs (JSONL) | `audit/test_raw_outputs.jsonl`, `ablation_A2_raw_outputs.jsonl`, `ablation_A4_raw_outputs.jsonl` |
| Full error audit | `audit/error_analysis.csv`, `test_pair_justifications.jsonl` |
| Keyword mapping table | `mapping/cluster_membership.csv`, `accepted_match_edges.csv` |
| Keyword frequency tables | `data/author_keyword_frequencies.csv`, `index_keyword_frequencies.csv` |
| VOSviewer export files | `vosviewer_exports/` |
| Downstream harmonisation maps | `mapping/b3_map.csv`, `llm_dag_map.csv` |

---

## Not redistributable — raw Scopus exports

Raw Scopus CSV exports are excluded under Elsevier Terms of Use.
Readers with institutional Scopus access can reconstruct the corpus using
the queries in `configs/scopus_batch_queries.yaml` and the procedure in
`docs/reproducibility.md`.
