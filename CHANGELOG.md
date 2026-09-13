# Changelog

## [2.0.0] — Unreleased

### Strengthened resubmission release
Following an editorial invitation to revise and resubmit, this release replaces the single-domain,
149-pair held-out result with a genuinely prospective, held-out, two-domain benchmark and adds a
second-provider robustness check and several additional diagnostics. The manuscript's primary
reported result is now the prospective benchmark below, not the original 500-pair (351
development + 149 held-out) legacy benchmark, which is preserved as a development-phase result.

### Added
- `strengthening/` — the full strengthened evidence base: candidate-generation, baseline (B1–B8),
  evaluation, paired-bootstrap, selective-prediction, and diagnostic code, plus frozen aggregate
  reports.
- A 900-pair prospective, held-out benchmark (400 circular-economy + 500 diabetes-mellitus pairs;
  gold distribution 264 match / 629 non-match / 7 uncertain), evaluated only after every
  prediction was frozen and hashed.
- A diabetes-mellitus domain benchmark (PMC Open Access, CC BY/CC0), new for this release, with a
  standalone, redistribution-cleared package at `release/zenodo_diabetes_benchmark/`.
- A second-provider robustness check (`gpt-5.4-nano-2026-03-17`) alongside the primary method
  (`claude-haiku-4-5-20251001`).
- Paired bootstrap (N=10,000, seed 42), selective-prediction/AURC analysis, a corrected B8
  retrieval-eligibility diagnostic, and an observed-transitive-contradiction safety check.
- Root-level `REPRODUCIBILITY.md` and `DATA_AVAILABILITY.md` for the strengthened evidence base.
- Several hundred additional tests (`strengthening/tests/`), all offline, no network/API calls; a
  small number are explicitly skipped (not failed) on a plain public checkout that lacks a
  restricted local research fixture or a `.git` directory — see `REPRODUCIBILITY.md` §11.

### Changed
- `README.md`, `CITATION.cff` — updated to the current manuscript title, author list (including
  the confirmed spelling "Abdelkhalak Bahri"), and the strengthened primary result
  (prospective-benchmark pooled precision/recall/F1/coverage: 0.9766 / 0.9579 / 0.9671 / 0.9720);
  no longer present the 149-pair held-out result as primary.
- `LICENSE` — copyright line completed: "Copyright (c) 2026 Abdelilah El Majjaoui and
  contributors".
- `release/zenodo_diabetes_benchmark/` — the compiled benchmark package is now explicitly licensed
  CC BY 4.0 (a new `LICENSE` file in that directory); this covers the compilation only and does
  not relicense the underlying PMC source articles, whose own per-row licence (`source_licence`:
  497 CC BY / 3 CC0) is unchanged.
- `strengthening/scripts_pmc/pmc_common.py` — `NCBIClient` no longer hard-codes a personal
  contact email; it now reads `NCBI_EMAIL` (or `ENTREZ_EMAIL`) from the environment and raises a
  clear error if neither is set. No scientific/retrieval behaviour changed.
- Corresponding-author contact added to `README.md`/`DATA_AVAILABILITY.md`/`CITATION.cff`.
- Release-safety cleanup: removed a small number of personal absolute filesystem paths from
  publication-facing documentation/scripts and excluded one file
  (`results/downstream_qualitative_examples.txt`) from public release pending further review (see
  the private v2.0.0 release-safety audit).

### Notes
- This release's own DOIs (software and, separately, the diabetes benchmark dataset) are not yet
  assigned; an archival DOI will be added after publication of the v2.0.0 release. See
  `release/zenodo_diabetes_benchmark/PROVENANCE.md` and `DATA_AVAILABILITY.md`.
- The circular-economy domain (both the legacy 500-pair benchmark and the 400-pair half of the
  prospective benchmark) remains Scopus-derived and is not redistributed, per Elsevier's Terms of
  Use, unchanged from the v1.0.0 policy below.

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
