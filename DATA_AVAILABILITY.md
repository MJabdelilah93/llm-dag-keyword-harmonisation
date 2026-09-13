# Data availability

| Resource | Location | Access | Reason |
|---|---|---|---|
| Pipeline, baseline, evaluation, and diagnostic source code (both the original and strengthened codebases) | This repository | Open | — |
| Prompts, schemas, configuration files | This repository | Open | — |
| Aggregate/statistical evaluation outputs (metrics, bootstrap CIs, cost/execution reports, audit reports) | `strengthening/reports/`, `results/` | Open | Contain no raw keyword strings, only pair IDs, counts, and statistics. |
| Diabetes-mellitus prospective benchmark (500 pairs: keyword strings, frequencies, gold label, PMC provenance, licence) | `release/zenodo_diabetes_benchmark/` (Zenodo record: not yet published) | Open once published | PMC Open Access, CC BY/CC0, licence-verified per pair. |
| Circular-economy benchmark (legacy 500-pair and the 400-pair circular-economy half of the 900-pair prospective benchmark): raw keyword strings, gold labels, frozen predictions | Authors' restricted working copy (`strengthening/restricted_local/`, gitignored) | Restricted | Scopus-derived; Elsevier Terms of Use do not permit redistribution of raw exports or bulk keyword-string collections. Reconstructible (not redistributable) by researchers with their own Scopus access — see `REPRODUCIBILITY.md` §2 and `configs/scopus_batch_queries.yaml`. |
| Per-annotator labels, free-text justifications, title/abstract "context used" text, adjudicator notes (both domains) | Authors' restricted working copy | Restricted | Withheld as restricted working material, independent of the underlying keyword strings' licence status. Only the single, final, adjudicated gold label is ever released. |
| Frozen LLM prediction snapshots (primary method, B6, B7, second-provider check) for the circular-economy domain | Authors' restricted working copy | Restricted | Inherit the circular-economy domain's Scopus-licensing restriction (predictions embed the restricted keyword strings). |
| Frozen LLM prediction snapshots for the diabetes-mellitus domain | Not yet separately released | To be decided | The keyword strings themselves are redistributable (see above); whether to release the raw model completions/justifications for this domain specifically has not yet been decided by the authors. |
| Raw PMC acquisition data (article metadata + keyword text, mixed licence-eligible/ineligible) | `strengthening/data_pmc/` (gitignored, local only) | Not released | Intermediate, mixed-licence research material; only the licence-filtered, confidently-author-keyword derivative (`strengthening/data_release/pmc_diabetes_mellitus/`) is release-cleared. |
| Software DOI (prior, pre-strengthening submission) | `10.5281/zenodo.20931435` | Open | Describes an earlier, different version of this software; not the strengthened evidence base in this repository revision. |
| Software/data DOI for this strengthened release | Not yet issued | — | Will be assigned when this release is actually published; do not cite a DOI for this version until then. |

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
