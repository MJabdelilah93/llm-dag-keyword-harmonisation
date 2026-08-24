# Restricted keyword-level content removed — 2026-08-24

As part of a public-history cleanup implementing this project's
conservative restricted-data policy (Scopus-derived content), the
following files in this directory were rewritten to remove raw keyword
strings and, where present, LLM justification text quoting them:

- `error_analysis.csv` — original columns `pair_id, keyword_a, keyword_b,
  stratum, gold_label, pred_full_dag, pred_b6, error_category,
  b6_error_category, justification, confidence, guard_applied`. The
  `keyword_a`, `keyword_b`, and `justification` columns have been
  removed; every other column is unchanged, in the same row order
  (149 rows, keyed by `pair_id`).
- `test_predictions.csv`, `test_predictions_baselines.csv` — the
  `keyword_a` and `keyword_b` columns have been removed; every
  prediction column is unchanged.

This is a data-governance action implementing the repository's own
restricted-data policy, not a legal determination about Elsevier/Scopus
licensing terms. Full detail, including why this was necessary, what
history was rewritten, and where the pre-cleanup content is archived:
`docs/provenance/public_history_cleanup_2026-08-24.md`.

The full, unredacted files (with keyword strings) remain available, for
readers with a legitimate need, via the gated Zenodo record referenced
in `results/downstream_harmonisation_maps/README.md` and
`docs/data_access.md`.
