# Strengthening-phase provenance: category map

This directory documents the provenance of every artefact touched or
produced during the M7 strengthening pre-annotation implementation phase
(worktree `concept_harmonisation-strengthening-2026`, branch
`strengthen/m7-2026`). Six categories, each with a different mutability
and distribution rule:

## A. Immutable legacy evidence

Everything under the sibling worktrees `concept_harmonisation/` (branch
`main`) and `concept_harmonisation-repair-v1.0.1/` (branch
`repair/current-paper-v1.0.1`). Read-only for this entire phase. SHA-256
hashes of every legacy file this phase actually read are recorded in
`implementation_manifest.json` and were also captured *before* any new
work began; any mismatch on re-check is a hard stop, not something to
silently resolve.

## B. Restricted new circular-economy artefacts

Anything under `strengthening/restricted_local/ce/` (gitignored). Contains
real Scopus-derived keyword strings (author keywords from the legacy CE
corpus) in newly generated, still-UNLABELLED candidate/retrieval-audit
files. Same Elsevier-licensing restriction as the legacy
`restricted_local/` in the repair worktree. Never committed to git, never
copied outside this worktree, never exposed in a public-safe manifest.

## C. Redistributable PMC-derived artefacts

Anything under `strengthening/data_release/pmc_<topic>/` (only populated
once per-article CC BY/CC0 licence verification has actually passed for
that record) and the biomedical benchmark/retrieval-audit files under
`strengthening/benchmark/` and `strengthening/retrieval_audit/` when
sourced entirely from CC BY/CC0 PMC content. Unlike category B, these MAY
be committed and redistributed, because open licences explicitly permit
it -- but only after the per-record licence check, never by default.

**`strengthening/data_pmc/` is explicitly NOT in this category.** It is
the raw acquisition/extraction *inventory* -- article metadata and keyword
text for **every** retrieved PMC article regardless of licence outcome,
mixing CC BY/CC0-eligible and ineligible (e.g. CC BY-NC-ND) records in the
same files. It is gitignored (`.gitignore`: `strengthening/data_pmc/`) and
must never be committed as-is. A release derivative may only be built by
explicitly filtering `data_pmc/` down to rows where (1) article-level
licence is verified CC BY or CC0, (2) the specific keyword group is
classified `confidently_author` (never `ambiguous` or
`clearly_not_author`), and (3) writing the result fresh under
`strengthening/data_release/pmc_<topic>/` with its own manifest -- never
by copying `data_pmc/` wholesale.

## D. Code / configuration

`strengthening/candidate_gen/`, `strengthening/baselines/`,
`strengthening/metrics/`, `strengthening/config/protocol_v1.yaml`,
`strengthening/tests/`, and this `strengthening/provenance/` directory
itself. Safe to commit. Contains no restricted strings, no API keys, no
gold labels.

## E. Future human gold labels

Not yet created anywhere. Will eventually populate the blank
`annotator_1_label` / `annotator_2_label` / `adjudicated_label` columns in
the templates under `strengthening/restricted_local/ce/*_annotation_
template.csv` and `strengthening/benchmark/*_annotation_template.csv`
(and the retrieval-audit `human_label` columns). This phase deliberately
produces zero rows of this category -- see
`strengthening/reports/annotation_handoff.md` for the handoff plan.

## F. Future model outputs

Not yet created. Reserved for B7/B8 real-mode outputs and any eventual
authorised paid-API run against the new benchmarks. No paid LLM/API call
was made anywhere during this phase; B7/B8 real-mode clients raise
`NotImplementedError` by design until such a run is explicitly authorised.
