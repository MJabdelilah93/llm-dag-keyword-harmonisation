# Phase 0B Final Report

Repair & Strengthening Programme — Workstream A (current paper). Produced
2026-08-24. All 19 tasks complete. No historical evidence overwritten. No
API calls made. No GitHub/Zenodo remote changes.

## A. Repair branch/worktree state

- Worktree: `concept_harmonisation-repair-v1.0.1/` (sibling to the
  untouched original working tree)
- Branch: `repair/current-paper-v1.0.1`, forked from `origin/main` at
  `5957c9e745b135d9104dda4442dc34141622ea0c`
- 8 commits added on top of `origin/main`, none pushed anywhere
- Original local working tree (`concept_harmonisation/`, branch `main`,
  HEAD `d09970a`) confirmed unchanged throughout — verified before and
  after this repair

## B. Evidence manifest created

`docs/provenance/v1_historical_evidence_manifest.csv` — SHA-256, size,
mtime, classification, and never-overwrite flag for 84 primary-evidence
files, explicitly labelled retrospective (`v1_evidence_freeze.md`).

## C. True v1 config created

`configs/v1_execution_config.yaml` + `docs/provenance/v1_execution_config_provenance.md`
— every value traced to executable code or independent re-derivation, not
documentation. The five configs that never ran are marked
`LEGACY / NOT USED IN V1 EXECUTION` in place, unmodified otherwise.

## D. Dev-log derived repair result

`scripts/current_paper/reparse_dev_log_v1.py` re-derives correct guard
metadata from the unchanged `full_response` text, no new API call. Exact
match confirmed: precision 0.9798, recall 0.9604, F1 0.9700, coverage
0.9003, threshold 0.50. Full detail: `docs/provenance/dev_log_repair_summary.md`.

## E. Corrected-map hashes and validation

`scripts/current_paper/regenerate_corrected_maps.py` — all 7 headline
verification checks passed exactly: 55,425 keyword universe; active vocab
3,646/2,880/3,464 (raw/B3/LLM-DAG); Circular economy cluster 214/57;
sustainability family 56/216; 194 B3 clusters fragmented. Manifest with
input/output hashes: `docs/provenance/corrected_maps_manifest.json`.
Corrected maps held in `restricted_local/corrected_maps/` (git-ignored).

## F. 109-term claim verdict

**CANNOT REPRODUCE.** Four code-grounded definitions tested against the
verified B3 map; none yields exactly 109. Closest: 115 (frequency ≥5
filter on the Sustainability cluster). Full detail:
`docs/provenance/109_term_claim_investigation.md`.

## G. Downstream reproducibility root cause

Unsorted Python set iteration feeding graph node insertion order
(`G.add_nodes_from(nodes)` where `nodes` was a set) — hash-seed-dependent.
Fixed by sorting before insertion
(`scripts/current_paper/downstream_deterministic.py`). Full diagnosis:
`docs/provenance/downstream_determinism_repair.md`.

## H. Hash-seed reproducibility results

20/20 `PYTHONHASHSEED` values (0-19) produced bit-identical results for
every metric (vocab, edges, density, Q, communities, ARI, AMI) in all three
conditions. `ALL_CONDITIONS_FULLY_REPRODUCIBLE = true`.
(`results/current_paper/hashseed_reproducibility_test.csv`/`summary.json`)

## I. Louvain seed-sensitivity results

50 Louvain seeds, deterministic graphs held fixed. Modularity Q ranking
(LLM-DAG &gt; B3) robust in 100% of seeds (zero range overlap). AMI ranking
robust in 84% of seeds. **ARI ranking robust in only 56% of seeds —
statistically indistinguishable from chance; recommend removing this
specific directional claim.** (`results/current_paper/downstream_seed_sensitivity*.csv/json`)

## J. Corrected downstream results

`results/current_paper/downstream_results_corrected.csv` and
`downstream_reproducibility_summary.txt` — distinguish deterministic exact
quantities from Louvain-dependent medians/IQRs. Original
`results/downstream_results.csv` preserved unmodified.

## K. Figure/VOSviewer regenerated-input status

Data inputs regenerated from the corrected map
(`scripts/current_paper/export_vosviewer_v1_corrected.py`); outputs in
`restricted_local/vosviewer_exports_v1_corrected/`. VOSviewer's own
manual import/screenshot step is documented but **not executed**
(`docs/provenance/figure2_vosviewer_rebuild.md`), including the exact
settings to use and an explicit **ORIGINAL VERSION UNKNOWN** flag for
VOSviewer itself (no version was ever recorded).

## L. Canonical-label diagnostic

Frequency-only (executed) vs. tiers-2-4 of the documented 4-tier rule
(tier 1, controlled vocabulary, has no data source anywhere in the
repository and was not tested): 17.71% of LLM-DAG and 20.29% of B3
multi-member cluster labels would change. Cluster membership unaffected by
construction. Recommend describing what actually ran.
(`docs/provenance/canonical_label_rule_check.md`)

## M. Test-suite status

33 real tests across 5 files, all passing, replacing the previous
docstring-only stubs. Covers normalisation, G1-G4 guard, threshold
handling, JSON parsing, union-find clustering, frequency-only
canonicalisation, baseline/benchmark metrics, deterministic graph
insertion (regression test for the Task 7 fix), and end-to-end small-fixture
reconstruction/reproducibility tests.

## N. Path/environment reproducibility status

All 17 original scripts with hardcoded personal paths patched to use
`V1_EVIDENCE_ROOT` env var / auto-discovery; verified via syntax check and
one genuine end-to-end run. `requirements-current-paper.txt` +
`docs/environment/current_paper_environment.md` distinguish
ORIGINAL VERSION UNKNOWN from the current reproducible pin.

## O. GitHub/Zenodo cleanup plan

**Live finding: the exact restricted content already redacted at
`outputs/harmonisation_maps/` is still publicly tracked at
`results/downstream_harmonisation_maps/` on the actual public GitHub repo**
(confirmed via direct tree inspection; added once at `f75bc65`, never
removed). Fixed in this branch (untracked, README stub added). Full,
prepared-but-not-executed remediation plan (git-filter-repo/BFG procedures,
8-file stale-DOI inventory, Zenodo-SW exposure check flagged
CANNOT-VERIFY, recommendation to cut v1.0.1 rather than move v1.0.0):
`docs/release/v1.0.1_release_plan.md`.

## P. Documentation corrections made

`docs/workflow_description.md`, `README.md`, `CITATION.cff`, and 7 README
stubs corrected in place (status, guard behaviour, canonicalisation,
auxiliary context, run manifests, stale DOIs). Full list in the Task 16/17
commit messages.

## Q. Manuscript correction matrix

`CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md` — 17 items, each with
manuscript section, current claim, evidence, classification, corrected
content, and whether it changes the conclusion. **Two items change a
conclusion**: the ARI-based directional claim (not supported) and the A3
ablation framing (not an independent condition).

## R. Remaining human-only dependencies

1. Resolve the annotation-provenance questions with the actual annotators
   (Phase 0A Task 7) — cannot be automated.
2. Decide the GitHub history remediation path (§O) — requires explicit
   authorisation for a force-push, or an explicit accept-and-document
   decision.
3. Confirm whether the Zenodo-SW archive also contains the leaked files —
   requires downloading and inspecting it manually.
4. Locate the source of the 109-term claim, or approve its replacement/removal.
5. Decide how to present the ARI finding in the manuscript (remove vs. heavily caveat).
6. Draft final manuscript Replace:/With: text from the correction matrix —
   an authorial/editorial task.
7. VOSviewer's manual import/screenshot step (§K).
8. Determine and record the actual VOSviewer version used originally, if recoverable.

## S. Recommendation

**READY WITH MINOR CONDITIONS.**

The technical/scientific evidence base is now solid: every reported
pairwise benchmark number has been independently re-verified twice; the
downstream determinism bug is root-caused, fixed, and verified 20/20; the
stale-map bug is fixed with full provenance; a real test suite exists and
passes; hardcoded paths are gone; documentation now matches verified
execution rather than aspirational design. None of this blocks beginning
Phase 1 (enhanced Scientometrics study) work in parallel.

The conditions before the **current paper** is resubmitted, specifically:
(1) the annotation-provenance question must be answered by the actual
annotators — this is the one item with genuine, unresolved integrity
implications; (2) the public GitHub exposure needs an explicit human
decision, not left as a prepared-but-unexecuted plan indefinitely; (3) the
109-term and ARI claims need an authorial decision reflected in the
manuscript text. None of these require further Claude Code engineering
work to *identify* — they require human judgement to *resolve*.
