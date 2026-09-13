# V1 Evidence Freeze

**Status: RETROSPECTIVELY RECONSTRUCTED. This document did not exist during the original experiment.**

## What this is

`v1_historical_evidence_manifest.csv` (same directory) is a retrospective
fingerprint of the files that generated the results reported for
"Auditable Concept Harmonisation in Bibliometric Analysis: Benchmarking an
LLM-DAG Workflow" (the "v1" / current-paper study). It was produced during an
internal audit conducted 2026-08-23 to 2026-08-24, roughly four and a half
months after the study's original execution window (2026-04-03 to
2026-04-07).

**No SHA-256 manifest, checksum ledger, or provenance freeze existed at the
time the original experiment ran.** Every hash in the accompanying CSV was
computed in 2026-08 by reading the files as they exist today on the original
author's local machine, not captured live during the 2026-04 execution. This
document and its manifest are a forensic reconstruction, not an original
experimental artefact, and must never be cited or presented as though they
were produced contemporaneously with the study.

## Why it exists

The repository was found, during the 2026-08-23 audit, to contain:

- a stale, pre-correction harmonisation map shipped as if it were current
  (`outputs/harmonisation_maps/full_llm_dag_map.csv`);
- a raw LLM log whose stored guard/decision metadata does not match what the
  same code produces today from the same underlying model responses
  (`results/llm_logs/dev_workflow_raw_outputs.jsonl`);
- five of six pipeline configuration files that were never actually loaded by
  any executed script;
- an entire `src/` package and `tests/` package consisting of docstring-only
  stubs, with all real logic living in `scripts/`.

Before any repair work touches this repository, every file that could
plausibly be primary evidence for a reported number needed to be identified,
hashed, dated, and classified — so that (a) a repair can be verified against
an immutable fingerprint of what it started from, and (b) no well-intentioned
"cleanup" accidentally destroys the only copy of something load-bearing.

## Scope

84 files were fingerprinted, covering: raw and interim Scopus corpus files,
derived keyword-frequency tables, the full benchmark construction trail
(candidate pool, pilot, annotation sheets, adjudication, splits), every LLM
call log, every results/prediction/threshold/ablation/error-analysis file,
all six harmonisation-map copies, both current figures, both appendices, all
six configuration YAMLs, the private project-notes file, and the eight
scripts that actually produced every reported number.

## Classification legend

| Value | Meaning |
|---|---|
| `HISTORICAL` | Primary source evidence; must never be regenerated or altered |
| `CLEAN` | Historical evidence found, on inspection, to be internally consistent and free of the corruption pattern found elsewhere |
| `CORRUPTED_METADATA_VALID_PAYLOAD` | The raw underlying content is intact and usable; derived/parsed fields stored alongside it are wrong |
| `STALE` | Superseded by a later, corrected computation but never regenerated; retained as evidence of the defect, not as a current source |
| `CURRENT_AUTHORITATIVE` | The result/derived file currently treated as the paper's reported value, independently re-verified during this audit |
| `RESTRICTED` (see `contains_scopus_derived_strings` column) | Not a separate classification bucket here — captured instead as a boolean flag alongside the primary classification, since a file can simultaneously be e.g. `HISTORICAL` *and* licensing-restricted |

## Handling rules going forward

1. Every file flagged `never_overwrite = True` is preserved exactly as-is in
   the original local working tree. Nothing in the Phase 0B repair worktree
   ever writes to those paths.
2. Files flagged `contains_scopus_derived_strings = True` are not copied into
   this repair branch. Any derived artefact built from them that itself
   contains real keyword strings is written only to `restricted_local/`
   (git-ignored, local machine only) — see `.gitignore`.
3. Any corrected or re-derived artefact produced from this evidence is
   versioned separately (e.g. `_v1_corrected`, `_reparsed_v1`) and cites the
   SHA-256 of its historical source(s) in its own provenance note.
4. This manifest itself is not a substitute for the original data-access
   documentation (`data/README.md`, `docs/data_access.md`) — it is an
   internal engineering artefact for the repair effort, not a
   publication-facing data-availability statement.
