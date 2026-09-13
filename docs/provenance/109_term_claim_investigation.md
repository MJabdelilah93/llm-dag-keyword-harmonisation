# The "109-Term" Claim — Forensic Investigation

**Status: investigation complete, 2026-08-24. Manuscript not edited.**

## The claim under test

The current manuscript states: *"Under B3, the largest single
connected-components merge group collapsed 109 raw keyword strings into one
canonical node..."*

Phase 0A searched `results/downstream_qualitative_examples.txt` and found no
occurrence of "109" anywhere in the workspace. Phase 0B re-tested the claim
directly against the newly-regenerated, verified B3 map
(`restricted_local/corrected_maps/b3_map_v1_verified.csv`, hash
`3463696744396528350ed47be1a65e8a133a08e4fe785e0a78194f5ba5d15b27`) under
every definition that is grounded in existing code or manuscript language.
No definition was invented solely to reach 109.

## Definitions tested

| # | Definition | Basis | Result (top match) | = 109? |
|---|---|---|---|---|
| 1 | Raw B3 connected-component size, unfiltered | The literal reading of "connected-components merge group" | Largest = 374 ("Sustainability") | No |
| 2 | "sustain\*" substring subset, freq ≥ 2 | `family_clusters()` in `scripts/rebuild_downstream.py` | Largest sub-group = 277 | No |
| 3 | Cluster filtered to members with individual raw frequency ≥ 5 | The network's own active-vocabulary threshold | Largest = **115** ("Sustainability") | No — closest of all four |
| 4 | VOSviewer top-100 canonical-keyword export | `TOP_N=100` in `scripts/export_vosviewer.py` | Not applicable — this caps *canonical concepts* across the whole network, not raw-string membership within one cluster | N/A |
| — | Largest cluster excluding the Sustainability and Circular Economy families | Tests whether "109" refers to some other, non-headline cluster | Largest = 86 ("Recycling") | No |

## Verdict

**CANNOT REPRODUCE.**

No objectively-defined grouping in the verified B3 map — under any filter
that is actually grounded in this repository's code or the manuscript's own
language — produces exactly 109 raw keyword strings in a single canonical
cluster. The closest result under any tested definition is 115 (Definition
3, frequency ≥ 5 filter on the "Sustainability" cluster), which is close
enough that a transcription or off-by-a-different-filter error is plausible,
but not close enough to assert as the source without further information.

This claim most likely originates in the current (Overleaf-only) manuscript
draft from a computation or filter this workspace does not contain evidence
of. It should not be retained in its current form without either (a)
locating the actual source computation, or (b) replacing it with one of the
values verified in this report (e.g. "115 keyword strings with corpus
frequency ≥ 5" or the unfiltered "374 keyword strings", whichever the
authors intend to illustrate).

Full machine-readable results: `docs/provenance/109_term_claim_investigation_results.json`.
See `CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md` for the corresponding
Replace:/With:-ready entry.
