# Changelog

## [1.0.0] — 2026-06-25

### Paper submission release
Frozen release accompanying submission to Scientometrics LLM4SCIM special collection.

### Added
- `prompts/v1.0.0/` — versioned prompt templates (system, standard user, context user, registry)
- `schemas/llm_response.schema.json` — JSON schema for LLM output validation
- `configs/scopus_batch_queries.yaml` — Scopus batch query documentation
- `configs/normalisation_config.yaml` — Node 2 normalisation chain config
- `configs/candidate_generation.yaml` — Node 3 candidate generation config (replaces candidate_gen_config.yaml)
- `configs/ablation_config.yaml` — ablation study definitions
- `docs/` — full documentation folder:
  - `annotation_guide.md` — annotation protocol (machine-readable version of Online Resource 1 S1)
  - `label_policy.md` — scope-policy quick reference table
  - `workflow_description.md` — nine-node DAG description
  - `retrieval_manifest.md` — candidate generation pool sizes
  - `reproducibility.md` — step-by-step reconstruction guide
  - `data_access.md` — what is available where
- `results/paper_v1/` — clean summary CSVs for all main tables (Tables 7–10)
- `examples/` — synthetic keyword and mapping examples (no real Scopus data)
- `CITATION.cff` — software citation metadata

### Changed
- `README.md` — corrected target journal (Scientometrics), corrected node count (9), added citation section
- `configs/eval_config.yaml` — updated with correct benchmark paths and metric definitions
- `configs/candidate_generation.yaml` — replaced placeholder embedding model with all-MiniLM-L6-v2

### Removed
- `appendices/` — content migrated: Appendix A → `configs/` + `prompts/` + `schemas/`; Appendix B → `docs/annotation_guide.md`

### Notes
- Raw Scopus data not included (Elsevier Terms of Use); see `docs/reproducibility.md`
- Benchmark files (500 pairs) and full audit logs archived on Zenodo (restricted access): https://doi.org/10.5281/zenodo.19451886
