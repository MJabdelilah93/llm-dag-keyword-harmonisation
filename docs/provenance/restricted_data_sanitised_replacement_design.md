# Phase C — Sanitised Current-HEAD Replacement Design

**Scope note:** only files currently present at a HEAD in scope
(`origin/main`) need a replacement design — the 26 historical-only files
found in Phase B are already absent from every current HEAD and need
only the Phase D history scrub (no HEAD-level change). The 2 ambiguous
`examples/` files are excluded pending author verification (Phase B,
Category D) and are not addressed here.

## `results/error_analysis.csv` — Option C: aggregate/ID-only derivative

Original columns: `pair_id, keyword_a, keyword_b, stratum, gold_label,
pred_full_dag, pred_b6, error_category, b6_error_category,
justification, confidence, guard_applied`.

**Replacement columns:** `pair_id, stratum, gold_label, pred_full_dag,
pred_b6, error_category, b6_error_category, confidence, guard_applied`.
Dropped: `keyword_a`, `keyword_b` (raw restricted content),
`justification` (quotes raw restricted content verbatim). This preserves
every scientifically meaningful field the paper's error analysis
depends on (which pairs erred, in which stratum, by which method,
guard behaviour, confidence) while removing the two restricted
components. Row count and row order preserved exactly (149 rows,
`pair_id`-keyed) so the derivative remains a faithful drop-in for any
analysis keyed on `pair_id`.

## `results/test_predictions.csv` / `results/test_predictions_baselines.csv` — Option C

Original: `pair_id, keyword_a, keyword_b, gold_label, [predictions...]`.
**Replacement:** `pair_id, gold_label, [predictions...]` — drop
`keyword_a`/`keyword_b` only; every prediction column (the actual
scientific content these files exist to carry) is preserved unchanged.

## `results/downstream_harmonisation_maps/{raw,b3,full_llm_dag}_map.csv` — Option B: restricted-data stub

These files' entire content **is** the keyword→canonical mapping —
there is no meaningful aggregate-only derivative that isn't simply the
restricted data with a different label. **This exact situation was
already resolved in the repair branch during Phase 0B**, which replaced
these three files with a single `README.md` stub pointing to the gated
Zenodo record and explaining the restriction
(`results/downstream_harmonisation_maps/README.md`, already committed on
`repair/current-paper-v1.0.1`, never applied to `origin/main`). **Phase
D reuses that exact, already-reviewed stub content** rather than
authoring a new one — this is the established project pattern, not a
new decision.

## Reconstruction / access-limitation statement (applies to all of the above)

After this cleanup, the removed keyword-level content (raw keywords,
canonical mappings, and free-text justifications quoting them) is not
reconstructable from the public repository. Consistent with the
project's existing restricted-data policy for `restricted_local/` and
`outputs/harmonisation_maps/`, this content remains available only via
the gated Zenodo record for readers with a legitimate need (e.g. peer
reviewers), and every aggregate metric derived from it (precision,
recall, F1, coverage, per-stratum counts, confusion matrices) remains
fully available in the sanitised files and the many aggregate-only
result artefacts already in this repository.

## Files NOT redesigned here

- The 26 historical-only broad-sweep files: no HEAD-level replacement
  needed (already absent from `origin/main` and repair-branch HEAD);
  Phase D removes them from history only.
- The 2 local-only Phase 1B documentation files: already redacted at
  current content (prior session); Phase D scrubs the 3 leak-matching
  historical blobs only, no further HEAD-level change needed.
- `examples/synthetic_keywords.csv`, `examples/synthetic_mapping_example.csv`:
  excluded pending author verification (Phase B, Category D).
