# Data Access Guide

Explains what is available where and how to access it.

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

---

## Public — Zenodo software record (Zenodo-SW)

**DOI:** https://doi.org/10.5281/zenodo.20931435

Frozen GitHub release tag v1.0.0. Includes all openly available content
listed above. Cite this DOI when referencing the pipeline code or workflow
implementation.

---

## Restricted — Zenodo dataset record (Zenodo-DATA)

**DOI:** https://doi.org/10.5281/zenodo.20923992

Access via Zenodo access request (reason: Scopus-derived content). Cite this
DOI when referencing the benchmark, annotation artefacts, or audit logs.

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
