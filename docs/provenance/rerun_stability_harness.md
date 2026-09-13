# Phase 1A Task 6 — Primary-Model Rerun-Stability Harness

**Status: harness built, dry-run validated with synthetic data. NO real API
call has been made. `--mode real` is refused unconditionally by the script
itself — a human must remove that guard after explicit Phase 1B
authorisation.**

## What was built

`scripts/current_paper/rerun_stability/`:
- `guard_v1.py` — the verified v1 G1-G4 guard, threshold frozen at 0.50.
- `llm_client.py` — `AnthropicClient` (real, fully implemented, never
  invoked here) and `MockClient` (synthetic, seeded, every record stamped
  `is_synthetic: true` and `model_id_returned_by_api: "MOCK-not-a-real-model"`
  so it can never be mistaken for real evidence even out of context).
- `run_single_rerun.py` — the harness. Loads the frozen 149-pair test set
  and the frozen v1.0.0 prompt files by hash; refuses to run if the loaded
  test set isn't exactly 149 rows; makes one call per pair with no
  caching/resume logic of any kind; refuses to write into an existing
  output directory (immutability); records timestamp, requested and
  API-returned model identifier, full request parameters, token usage,
  estimated cost, prompt hash, pair identifier, raw response, and the
  final guarded decision for every single pair.
- `analyze_rerun_stability.py` — computes every stability outcome defined
  below, given any ≥2 run directories (plus, optionally, the historical
  reference run loaded from `results/test_predictions.csv`).

## Pre-defined stability outcomes (defined before any real rerun, per Task 6)

- Exact label agreement, historical vs. each new run, and pairwise among
  new runs.
- Fleiss' kappa across all runs analyzed together (historical + N new).
- Number and percentage of pairs whose label ever differs across any pair
  of runs.
- A transition-matrix count of every `match↔non_match`, `match↔uncertain`,
  `non_match↔uncertain` crossing observed between any two runs.
- Mean pairwise confidence-score standard deviation per pair (across runs
  that carry confidence — the historical reference does not, since its
  confidence scores live only in the restricted `test_raw_outputs.jsonl`
  and are not needed for label-level stability).
- Precision / recall / F1 / coverage, each as a **range** (min-max) across
  all runs analyzed.

## Dry-run validation (synthetic — no evidential value about the real model)

Two synthetic runs (`dry_run_synthetic_A`, seed 1; `dry_run_synthetic_B`,
seed 2) were generated via `MockClient` and analyzed together with the
historical reference. This validated, end-to-end:

- The immutability guard correctly refuses to overwrite an existing
  run-id directory.
- The `--mode real` guard correctly refuses to execute without a human
  removing it.
- `n_pairs_expected != 149` would correctly abort a run (the frozen test
  set is exactly 149, so this could not be triggered in this dry-run, but
  the check is in place and was code-reviewed).
- The historical reference's own metrics, computed *through* this new
  multi-run analysis tool, reproduced the already-known ground truth
  (P=0.9762, R=0.9535, F1=0.9647, coverage=0.9262) **exactly** — confirming
  the tool's binary-metric logic is correct, not just its plumbing.
- Fleiss' kappa, transition matrix, and confidence-stdev calculations all
  executed and produced sensible, internally-consistent numbers (κ=0.78,
  25/149 pairs — 16.8% — changed label somewhere across the 3 runs
  analyzed, dominated by `non_match↔uncertain` transitions — exactly the
  kind of pattern a noisy synthetic client should produce, and exactly the
  kind of pattern the tool needs to be able to detect in a real rerun).

Full synthetic output: `results/current_paper/rerun_stability/dry_run_synthetic_stability_report.json`.
**This file, and the two `run_dry_run_synthetic_*` directories it derives
from, are synthetic test fixtures for the harness itself — they say
nothing about the real model.**

## Exact planned API-call count for Phase 1B

**5 independent reruns × 149 pairs = 745 API calls.** No caching, no
retries counted separately (retries reuse the same logical call). See
`docs/provenance/phase1a_report.md` §J / Task 10 for the corresponding
cost estimate.

## What Phase 1B must do to activate this harness

1. Set `ANTHROPIC_API_KEY` in the environment.
2. A human removes the `sys.exit("REFUSED: ...")` guard in
   `run_single_rerun.py`'s `--mode real` branch (left in deliberately as a
   one-line, obvious, easy-to-audit stop).
3. Run `run_single_rerun.py --mode real --run-id rerun_01` through
   `rerun_05` (5 separate invocations, 5 separate immutable output
   directories).
4. Run `analyze_rerun_stability.py` over the 5 real run directories plus
   `--include-historical`.
5. Delete or clearly relocate the synthetic `run_dry_run_synthetic_*`
   directories and their stability report before any results are
   reported, so they can never be accidentally cited as real evidence.
