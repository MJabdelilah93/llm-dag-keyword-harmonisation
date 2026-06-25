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
| Aggregate results (Tables 7–10) | `results/paper_v1/` |
| Benchmark LLM logs (dev, test, ablations) | `results/llm_logs/` |
| VOSviewer export files | `outputs/figures/vosviewer_exports/` |
| Derived keyword frequency tables | `data/derived/` |
| Synthetic examples | `examples/` |

---

## Public — Zenodo software record (v1.0.0)

**DOI:** https://doi.org/10.5281/zenodo.19451886 (software record)  
Frozen GitHub release tag v1.0.0. Includes all open repository content above.

---

## Restricted — Zenodo dataset record

**DOI:** https://doi.org/10.5281/zenodo.19451886 (dataset record)  
Access via Zenodo access request.

| Content | Reason for restriction |
|---------|----------------------|
| 500-pair benchmark (gold_benchmark.csv, dev_set.csv, test_set.csv) | Contains Scopus-derived keyword strings |
| Annotation round files and adjudication log | Contains Scopus-derived keyword strings |
| Full keyword mapping table (cluster_membership.csv) | Contains Scopus-derived keyword strings |
| Accepted match edges with provenance (accepted_match_edges.csv) | Contains Scopus-derived keyword strings |
| Full error audit JSONL (test_pair_justifications.jsonl) | Contains Scopus-derived keyword strings |
| Downstream LLM logs (51 MB, 27 MB) | Size; contains corpus-derived content |

---

## Not redistributable — raw Scopus exports

Raw Scopus CSV exports are excluded under Elsevier Terms of Use (prohibition on
redistribution of raw database exports). Readers with institutional Scopus access
can reconstruct the corpus using the queries in `configs/scopus_batch_queries.yaml`
and the procedure in `docs/reproducibility.md`.
