# Figure 2 / VOSviewer Input Rebuild (Task 11)

**Status: data inputs regenerated from the corrected map. A manual GUI step
remains and is described, not executed, below.**

## What was wrong

`scripts/export_vosviewer.py` and `scripts/figure2_thematic_comparison.py`
both read from `results/downstream_harmonisation_maps/full_llm_dag_map.csv`
— the stale, pre-fix-run map (see Phase 0A). Both the existing PNG/PDF
Figure 2 and the existing VOSviewer export files (co-occurrence matrix,
edge list, keyword frequencies) for the LLM-DAG condition were therefore
built on the wrong clustering.

## What was regenerated

`scripts/current_paper/export_vosviewer_v1_corrected.py` reproduces the
exact same algorithm (TOP_N=100 highest-frequency canonical keywords per
condition, FREQ_THRESH=5 co-occurrence network) but reads from
`restricted_local/corrected_maps/` (Task 5's verified, corrected maps)
instead. Outputs — real keyword strings — are written to
`restricted_local/vosviewer_exports_v1_corrected/`, never committed.
Per-condition hashes and row/edge counts are recorded in
`docs/provenance/figure2_vosviewer_rebuild_manifest.json` (public, numbers
only).

| Condition | Source map | Top-N keywords | Edges |
|---|---|---|---|
| Raw | `raw_map_v1_verified.csv` | (see manifest) | (see manifest) |
| B3 Jaro-Winkler | `b3_map_v1_verified.csv` | (see manifest) | (see manifest) |
| Full LLM-DAG | `full_llm_dag_map_v1_corrected.csv` | (see manifest) | (see manifest) |

The Raw and B3 exports are expected to be very close to (or identical to)
the existing ones, since those two conditions are unaffected by the
stale-LLM-log bug. The LLM-DAG export differs materially, since it is now
built from the map that shows the true 57-member "Circular economy"
cluster rather than the stale map's 214-member one.

## VOSviewer version — established facts only

**ORIGINAL VERSION UNKNOWN.** No VOSviewer version number is recorded
anywhere in this repository, in any config, log, or documentation file. The
only reference is a generic download link
(`https://www.vosviewer.com/`) in `scripts/export_vosviewer.py` and
`outputs/figures/vosviewer_exports/vosviewer_instructions.txt`. Per Task 11,
no version is invented here. If the original author has VOSviewer already
installed, check **Help → About VOSviewer** for the version actually used
to produce the current (stale-map-based) Figure 2, and record it before
regenerating — otherwise, use the current stable VOSviewer release and
record that version explicitly as `CURRENT REPRODUCIBLE ENVIRONMENT PIN`,
not as a claim about what was originally used.

## Manual step required (human action, not automatable)

The following must be done by a person in the VOSviewer desktop
application — this cannot be scripted:

1. Launch VOSviewer (version as determined above).
2. **Create → Create a map based on network data → Tab-delimited file with
   network data.**
3. Browse to `restricted_local/vosviewer_exports_v1_corrected/` and select,
   in turn: `raw_edge_list_v1_corrected_vos.txt`,
   `b3_edge_list_v1_corrected_vos.txt`,
   `llm_dag_edge_list_v1_corrected_vos.txt`.
4. In the import dialog: **Minimum number of occurrences → 0** (frequency
   filtering is already applied — every exported keyword already has
   corpus frequency ≥ 5). Click **Next → Finish**.
5. Apply **identical settings to all three maps**:
   - Layout tab: Attraction = 2, Repulsion = −1, Max iterations = 1000
   - Clustering tab: Resolution = 1.0, Min cluster size = 5
   - Visualization tab: Scale = 1.0, Node size by "Total link strength" or
     "Occurrences", show all labels
6. Optionally import the corresponding `*_keyword_frequencies_v1_corrected.csv`
   under the **Items** tab to set node sizes explicitly by corpus frequency.
7. **File → Screenshot (PNG)** or **File → Save as image (SVG/PDF)** for
   each of the three maps.
8. Arrange the three exported images as one 3-panel figure: **(A) Raw, (B)
   B3 Jaro-Winkler, (C) Full LLM-DAG (corrected)**, using the corrected
   headline numbers below each panel:
   - (A) Vocab 3,646, Q = 0.413 (median across 50 Louvain seeds; see
     `docs/provenance/downstream_determinism_repair.md`)
   - (B) Vocab 2,880, Q = 0.217
   - (C) Vocab 3,464, Q = 0.236

This repair stops here, before the manual GUI step, exactly as Task 11
requires. It does not replace the existing `outputs/figures/figure_2_*`
files.
