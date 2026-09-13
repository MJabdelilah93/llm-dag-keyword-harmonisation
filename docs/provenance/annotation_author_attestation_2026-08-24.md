# Annotation Author Attestation — 2026-08-24

**Status: RETROSPECTIVE AUTHOR ATTESTATION. Recorded 2026-08-24, after the
2026-08-23/24 internal audit (Phase 0A) that first raised the annotation-
timeline question. This is not contemporaneous evidence and does not
change, supersede, or reinterpret any timestamp, hash, or file recorded in
`docs/provenance/v1_historical_evidence_manifest.csv`.**

## What Phase 0A found

Phase 0A (Task 7) observed that every file in `data/benchmark/` carries a
modification timestamp within an 11h41m window on 2026-04-03, with the
full-round annotation sheets' blank-template mtime preceding the pilot
round's completion mtime, and asked five specific questions of the authors
and annotators rather than drawing a conclusion from timestamps alone.

## Author attestation (as reported, 2026-08-24)

The corresponding author has confirmed the following, in response to those
questions:

1. The two independent annotators and the adjudicator were members of the
   manuscript author team, including the corresponding author among those
   involved.
2. Annotation was performed using Excel files sent separately to the
   people involved (i.e. not via any in-repository tool that would leave
   its own independent timestamp trail).
3. The actual annotation sequence occurred as described in the submitted
   manuscript: pilot → rule clarification/calibration → independent full
   annotation → adjudication.
4. The manuscript's "approximately 39 annotator-hours" is confirmed by the
   author as the intended approximate total for the annotation effort.
5. The actual pilot contained 52 pairs. The "50 pairs" references found in
   planning/internal documentation (`appendix_b_annotation_guide.md` §6,
   `INTERNAL_PROJECT_STATE.md`) are obsolete planning targets; the executed
   pilot and the manuscript's stated value are both 52.

## What this attestation does and does not establish

- **It resolves the open provenance question** from Phase 0A regarding who
  performed the annotation, how (Excel files, out-of-band), and in what
  sequence — as reported by the corresponding author.
- **It does not create contemporaneous timestamp evidence.** The
  Excel-file exchange described was external to this repository; no
  independent, dated record of individual annotation sessions was ever
  captured inside the repository's own filesystem history. The `mtime`
  values on the files in `data/benchmark/` therefore reflect only when
  those files were last written to the repository's local disk (most
  plausibly, when someone collected/consolidated the external Excel
  results into these CSVs) — **not** the duration or timing of the
  underlying human annotation work itself. Phase 0A's original caution
  stands: **the spreadsheet filesystem mtimes should not be interpreted as
  a direct measure of human annotation duration**, in either direction —
  neither as proof of a compressed timeline, nor as proof of a normal one.
- **39 hours is an approximate, author-reported total**, not a measured or
  automatically logged duration (e.g. from a time-tracking tool). It is
  recorded in the manuscript and confirmed here as the author's own
  best-effort estimate of total annotation effort, not a precise or
  independently verifiable figure.
- **The pilot size correction (50 → 52) is now resolved**: 52 is both the
  actual executed value and the manuscript's stated value; the "50"
  figures in `appendix_b_annotation_guide.md` and
  `INTERNAL_PROJECT_STATE.md` are acknowledged obsolete planning targets,
  not a discrepancy requiring further investigation.

## Naming convention

Individual annotators are not named in this note. Because the exact
mapping of specific named individuals to the roles of "Annotator 1",
"Annotator 2", and "adjudicator" cannot be established from any existing
project documentation (the annotation files themselves refer only to roles,
never names), this document uses **"author-annotators"** and
**"author-adjudicator"** throughout, consistent with the attestation that
all three roles were filled by members of the author team.

## Effect on Phase 0A/0B findings

- Phase 0A Task 7's classification of the 39-hour figure changes from
  **UNSOURCED ESTIMATE** to **DOCUMENTED ESTIMATE (author-attested, not
  independently measured)** — see the manuscript correction matrix
  (`CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md`) for the corresponding
  update.
- Phase 0A's "Questions for the authors/annotators" are considered
  answered by this attestation. No further annotation-provenance action is
  required before Phase 1A proceeds.
- The pilot-size item in the manuscript correction matrix is updated from
  "minor-numerical, self-disclosed" to **resolved — 52 is correct and
  intended**; the internal planning documents' "50" is noted as obsolete,
  not corrected (they are historical planning artefacts, not reported
  results).
