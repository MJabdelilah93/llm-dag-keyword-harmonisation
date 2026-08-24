# results/downstream_harmonisation_maps/ — Restricted

**Corrected 2026-08-24 (Phase 0B repair).** This directory previously
contained the same real, Scopus-derived keyword-to-canonical-label mapping
CSVs (`raw_map.csv`, `b3_map.csv`, `full_llm_dag_map.csv`) as
`outputs/harmonisation_maps/` — but unlike that directory, these copies
were never removed from public git tracking during the earlier
public-release cleanup. Both directories were populated in the same
initial commit (`f75bc65`); only `outputs/harmonisation_maps/` was
subsequently redacted. This mirror location was missed. It has now been
removed from tracking, and scrubbed from all reachable git history,
under the same restricted-data policy that already applies to
`outputs/harmonisation_maps/`. This public-history cleanup was performed
on 2026-08-24 — see `docs/provenance/public_history_cleanup_2026-08-24.md`
for the full record of what was rewritten and why.

These files contain Scopus-derived keyword strings and are not publicly
redistributable under Elsevier's Terms of Use.

**Access:** available in the restricted Zenodo dataset record:
https://doi.org/10.5281/zenodo.20923992 (Zenodo-DATA — gated access
request, reason: Scopus-derived content). Note: several other legacy
README stubs in this repository (`data/README.md`,
`data/benchmark/README.md`, `data/derived/README.md`,
`outputs/harmonisation_maps/README.md`, `results/llm_logs/README.md`,
`CHANGELOG.md`, `docs/reproducibility.md`) still cite an earlier, since
superseded DOI (`10.5281/zenodo.19451886`) for this same restricted
content — see `docs/release/v1.0.1_release_plan.md` for the full inventory
and correction plan.

**A corrected version of `full_llm_dag_map.csv` now exists** (Phase 0B
Task 5), fixing the stale-cluster-assignment issue that
`outputs/harmonisation_maps/README.md` already flags as "under
investigation." It is held locally at
`restricted_local/corrected_maps/full_llm_dag_map_v1_corrected.csv`
(git-ignored, not committed here — see
`docs/provenance/corrected_maps_manifest.json` for its SHA-256 hash and
verification numbers) pending inclusion in an updated Zenodo-DATA record.
