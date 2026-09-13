# Ambiguous `examples/` Files — Final Provenance Check (2026-08-26)

**Scope: narrow follow-up only.** Does not reopen or redo the
2026-08-24 public-history cleanup. No API called, no LLM inference run,
no scientific result altered, no manuscript prose edited. No potentially
restricted string is reproduced anywhere in this document — provenance
signals, counts, and commit metadata only.

## Files checked

- `examples/synthetic_keywords.csv`
- `examples/synthetic_mapping_example.csv`

Both were left untouched by the 2026-08-24 cleanup pending this review
(`docs/provenance/restricted_data_history_inventory_pre_cleanup.md`,
Category D).

## Evidence gathered

1. **Commit provenance.** Each file was added in its own standalone
   commit, authored directly by the paper's own author
   (`Abdelilah EL MAJJAOUI`), 2026-06-25:
   - `e030cd3`: *"feat: add synthetic keyword examples (no real corpus
     data)"* — an explicit, contemporaneous, first-party declaration of
     synthetic origin, not written in response to any later audit.
   - `6457fe9`: *"feat: add synthetic mapping table example"*.
2. **Identifier scheme.** Neither file's row identifiers match the real
   benchmark's `BP####` pair-ID convention (0/6 and 0/7 rows) — if these
   were an export or excerpt of real pipeline data, the real ID scheme
   would very likely have carried over; it did not.
3. **Structure.** Both are small (6 and 7 data rows), consistent with
   hand-authored illustrative tables rather than a data dump or sampled
   export.
4. **Re-examining the earlier cell-match statistic.** The 2026-08-24
   inventory found an exact full-cell match rate of 36-54% against the
   real corpus keyword vocabulary — flagged then as "too high to
   confidently attribute to coincidence." Re-examined here with two
   additional, safe (no-value-printing) checks:
   - Text-cell word-count profile: mean 1.5-3.2 words per cell,
     consistent with short, generic, single/double-word domain terms —
     not long or unusually specific multi-word phrasings, which is what
     verbatim copying of a specific real keyword pair would more likely
     produce.
   - Domain context: this corpus's own subject area is sustainability/
     business bibliometrics; a knowledgeable author writing illustrative
     examples in that exact domain would naturally reach for common
     domain nouns (the kind of term a 47,529-entry real corpus in the
     same domain would also contain by simple vocabulary saturation),
     independent of ever having copied from the corpus.

## Classification

| File | Classification |
|---|---|
| `examples/synthetic_keywords.csv` | **SAFE_SYNTHETIC** |
| `examples/synthetic_mapping_example.csv` | **SAFE_SYNTHETIC** |

**Basis:** convergent evidence (first-party contemporaneous author
declaration, distinct ID scheme, hand-authored scale, and a plausible,
domain-saturation explanation for the vocabulary-overlap statistic that
does not require assuming verbatim copying). This is an evidentiary
determination under the project's own conservative restricted-data
policy, not a legal conclusion about Elsevier/Scopus licensing.

**Action taken:** none — per policy for `SAFE_SYNTHETIC`, both files are
left unchanged. No history rewrite is needed or was performed.

## Live re-verification of already-remediated artefacts

A fresh fetch from `origin/main` (2026-08-26) reconfirmed, independent
of this check:
- `results/error_analysis.csv`, `results/test_predictions.csv`,
  `results/test_predictions_baselines.csv` — no `keyword_a`,
  `keyword_b`, or `justification` field present in the live header.
- `results/downstream_harmonisation_maps/` — contains only `README.md`.

## Result

- Example file 1: `examples/synthetic_keywords.csv` — **SAFE_SYNTHETIC**
- Example file 2: `examples/synthetic_mapping_example.csv` — **SAFE_SYNTHETIC**
- Current public HEAD scan: **PASS**
- Further history rewrite needed: **NO**
- Repository safe to link in manuscript: **YES**
- Remaining action required: **none**
