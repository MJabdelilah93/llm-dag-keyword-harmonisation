# outputs/harmonisation_maps/ — Restricted

This directory previously contained the full keyword-to-canonical-label
mapping tables for all three experimental conditions (raw, B3, LLM-DAG).
These files contain Scopus-derived keyword strings and are not publicly
redistributable.

**Access:** Available in the restricted Zenodo dataset record:
https://doi.org/10.5281/zenodo.19451886

**Files archived on Zenodo (mapping/ folder):**
- `cluster_membership.csv` — raw keyword → canonical label → cluster ID
- `accepted_match_edges.csv` — pairwise decisions with provenance
- `canonical_label_registry.csv` — cluster labels and selection trace

**Note:** The current `full_llm_dag_map.csv` has a known data quality issue
(incorrect cluster assignments for a subset of keywords) that is under
investigation. The corrected version will replace it in the Zenodo record
after validation.
