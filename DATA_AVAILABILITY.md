# Data availability

| Resource | Location | Access | Reason |
|---|---|---|---|
| Pipeline, baseline, evaluation, and diagnostic source code (both the original and strengthened codebases) | This repository | Open | — |
| Prompts, schemas, configuration files | This repository | Open | — |
| Aggregate/statistical evaluation outputs (metrics, bootstrap CIs, cost/execution reports, audit reports) | `strengthening/reports/`, `results/` | Open | Contain no raw keyword strings, only pair IDs, counts, and statistics. |
| Diabetes-mellitus prospective benchmark (500 pairs: keyword strings, frequencies, gold label, PMC provenance, licence) | `release/zenodo_diabetes_benchmark/`. Dataset DOI: `10.5281/zenodo.22736625` | Open | PMC Open Access, CC BY/CC0 per source article (see `PROVENANCE.md`); compiled benchmark licensed CC BY 4.0. |
| Circular-economy benchmark (legacy 500-pair and the 400-pair circular-economy half of the 900-pair prospective benchmark): raw keyword strings, gold labels, frozen predictions | Authors' restricted working copy (`strengthening/restricted_local/`, gitignored) | Restricted | Scopus-derived; Elsevier Terms of Use do not permit redistribution of raw exports or bulk keyword-string collections. Reconstructible (not redistributable) by researchers with their own Scopus access — see `REPRODUCIBILITY.md` §2 and `configs/scopus_batch_queries.yaml`. |
| Per-annotator labels, free-text justifications, title/abstract "context used" text, adjudicator notes (both domains) | Authors' restricted working copy | Restricted | Withheld as restricted working material, independent of the underlying keyword strings' licence status. Only the single, final, adjudicated gold label is ever released. |
| Frozen LLM prediction snapshots (primary method, B6, B7, second-provider check) for the circular-economy domain | Authors' restricted working copy | Restricted | Inherit the circular-economy domain's Scopus-licensing restriction (predictions embed the restricted keyword strings). |
| Frozen LLM prediction snapshots for the diabetes-mellitus domain | Not yet separately released | To be decided | The keyword strings themselves are redistributable (see above); whether to release the raw model completions/justifications for this domain specifically has not yet been decided by the authors. |
| Raw PMC acquisition data (article metadata + keyword text, mixed licence-eligible/ineligible) | `strengthening/data_pmc/` (gitignored, local only) | Not released | Intermediate, mixed-licence research material; only the licence-filtered, confidently-author-keyword derivative (`strengthening/data_release/pmc_diabetes_mellitus/`) is release-cleared. |
| **Software (this v2.0.0 release)** | Software archive DOI: `10.5281/zenodo.22736473` | Open | The strengthened evidence base described in this repository revision. |
| **Public benchmark dataset** | Diabetes benchmark dataset DOI: `10.5281/zenodo.22736625` | Open | See the row above; repeated here for the software/dataset DOI summary. |
| Historical: software DOI, prior pre-strengthening submission | `10.5281/zenodo.20931435` | Open (historical) | Describes an earlier, different version of this software; not the strengthened evidence base in this repository revision. Do not cite for v2.0.0. |
| Historical/restricted: corrected legacy-data record (benchmark, annotation, and audit files from the original v1 submission) | `10.5281/zenodo.20923992` | Restricted (access request) | Corrected 2026-08-24 from an earlier, superseded DOI; unrelated to the diabetes-mellitus dataset above, which is a new, separately-licensed public release. |
| No manuscript/article DOI has been assigned | — | — | Do not cite a DOI for the manuscript itself until one is issued. |

## Requesting access to restricted material

Researchers with a legitimate research need for the restricted circular-economy benchmark
material (gold labels, annotation justifications, or frozen predictions) should contact the
corresponding author, Abdelilah El Majjaoui (abdelilah.elmajjaoui@etu.uae.ac.ma; see also
`README.md` §14), to discuss what can be shared under what terms; this repository does not itself
grant or manage such access.

## Summary statement (short form, for manuscript use)

Pipeline code, prompts, configuration, and all aggregate/statistical evaluation outputs reported
in the manuscript are openly available in this GitHub repository. The 500-pair diabetes-mellitus
benchmark (keyword pairs, gold labels, and PMC provenance) is separately released on Zenodo. The
circular-economy benchmark's underlying keyword corpus is derived from Scopus and cannot be
redistributed under Elsevier's Terms of Use; researchers with their own Scopus access can
reconstruct it using the documented query and code. Individual annotator justifications and
adjudication notes are withheld for both domains as restricted working material.
