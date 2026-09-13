# outputs/harmonisation_maps/ — Restricted

This directory previously contained the full keyword-to-canonical-label
mapping tables for all three experimental conditions (raw, B3, LLM-DAG).
These files contain Scopus-derived keyword strings and are not publicly
redistributable.

**Access:** Available in the restricted Zenodo dataset record:
https://doi.org/10.5281/zenodo.20923992 (Zenodo-DATA — corrected 2026-08-24;
this file previously cited a superseded DOI, 10.5281/zenodo.19451886 — see
`docs/release/v1.0.1_release_plan.md`)

**Files archived on Zenodo (mapping/ folder):**
- `cluster_membership.csv` — raw keyword → canonical label → cluster ID
- `accepted_match_edges.csv` — pairwise decisions with provenance
- `canonical_label_registry.csv` — cluster labels and selection trace

**Update 2026-08-24 (Phase 0B repair):** the data-quality issue this note
previously flagged as "under investigation" has been root-caused and
fixed. The stale `full_llm_dag_map.csv` this directory once held clustered
keywords almost identically to the B3 baseline it is meant to outperform
(e.g. its "Circular economy" cluster showed 214 members, matching B3,
against a true value of 57). A corrected version, regenerated directly from
the frozen historical decision logs, is verified in
`docs/provenance/corrected_maps_manifest.json` and held locally at
`restricted_local/corrected_maps/full_llm_dag_map_v1_corrected.csv`
pending inclusion in an updated Zenodo-DATA record. The original stale file
is preserved as historical evidence of the defect, not deleted.

**Also see:** `results/downstream_harmonisation_maps/README.md` — a
byte-identical copy of these same restricted files was found, during this
same repair, to have been missed by the original public-release cleanup
and was still publicly tracked in git. That has now been corrected in this
branch; see `docs/release/v1.0.1_release_plan.md` for the required public
git-history remediation.
