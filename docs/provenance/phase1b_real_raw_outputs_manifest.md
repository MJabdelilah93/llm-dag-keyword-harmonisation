# Phase 1B — Real Raw-Output Data-Handling Note

**Finding, flagged and resolved before proceeding to the OpenAI held-out
test run (the next paid, one-shot stage), per the standing instruction to
stop and report any leakage concern before continuing.**

## What was found

While preparing to commit the outputs of the five real Claude Haiku
reruns and the real OpenAI development run, inspection of
`raw_outputs.jsonl` showed that the model's own `justification` field
routinely quotes the actual keyword-pair text verbatim — for example,
justifications for geographic-entity pairs, methodology/broader-concept
pairs, and singular/plural variant pairs all named the actual keyword
strings being compared, in the pattern "[keyword A] and [keyword B]
are/represent [relationship description]..."

**[2026-08-24 correction, see `docs/provenance/phase1b_final_reconciliation_audit.md`
item 10]: three verbatim example quotes originally shown here — which
themselves reproduced real Scopus-derived keyword pairs — have been
redacted from this file's current content.** They remain embedded in
this branch's git history (commit `60c753a`, not pushed anywhere) pending
an author decision on history remediation; see the reconciliation audit
for exact detail and recommended next steps. This paragraph now describes
the *pattern* observed, not verbatim examples, so this document itself no
longer needs to be treated as restricted.

These keyword strings are Scopus-derived content. Per this repository's
existing `.gitignore` policy (`# Data (cannot redistribute raw Scopus
data — Elsevier licensing)`) and the established `restricted_local/`
convention from Phase 0B (see `results/downstream_harmonisation_maps/README.md`
for the precedent), this content must not be committed to git or pushed
to a public repository. Committing these files verbatim would have
recreated the same category of exposure Phase 0B's access-policy task
(Task 16) found and fixed for the harmonisation-map CSVs.

## Resolution

Rather than moving already-written files (which would have broken the
relative paths recorded in `results/current_paper/phase1b/openai_dev_freeze_manifest.json`
and the run manifests), `.gitignore` was extended with a path pattern
matching this repair's real-run naming convention
(`*_real_*` directories under `results/current_paper/rerun_stability/`
and `results/current_paper/second_model/`), so real-mode
`raw_outputs.jsonl` files stay on local disk — immutable, never
overwritten (the existing run-id collision guard already enforces this)
— but are excluded from git. Synthetic dry-run outputs
(`run_dry_run_synthetic_A`, `run_dry_run_synthetic_B`) are unaffected and
remain tracked, since `MockClient` never emits real keyword content.

Every manifest (`run_manifest.json`, `dev_manifest.json`,
`test_manifest.json`) and the dev-freeze manifest **are** committed, since
they contain only aggregate statistics, hashes, and pair IDs — no
keyword text. Full provenance over the excluded raw content is preserved
via the SHA-256 hashes below (computed 2026-08-24, before any file was
excluded from tracking).

| File | SHA-256 | Lines (=pairs) |
|---|---|---|
| `results/current_paper/rerun_stability/run_real_run_1/raw_outputs.jsonl` | `9ca8921ec76b6adb158ce4710bc0f41cae2cc4d4794fb07fc5d0fd86fa9dc613` | 149 |
| `results/current_paper/rerun_stability/run_real_run_2/raw_outputs.jsonl` | `c579dede36891251bb05e736b4e048d3d976469db39d80573767b5e373c132a7` | 149 |
| `results/current_paper/rerun_stability/run_real_run_3/raw_outputs.jsonl` | `e73598d461364263d171b9cd9a9871c004594b27e47f95bf2e9c465387ee63df` | 149 |
| `results/current_paper/rerun_stability/run_real_run_4/raw_outputs.jsonl` | `9a010eb27a8c25e7b7307a255b00769af2905ef6caa2804c78e21387cac38727` | 149 |
| `results/current_paper/rerun_stability/run_real_run_5/raw_outputs.jsonl` | `d7bed7d49c4b6536614648f0a0e21f8f3c0e1ddc0079d1872065b62838593271` | 149 |
| `results/current_paper/second_model/openai/dev_run_real_dev_1/raw_outputs.jsonl` | `1660dd01668ec4c3a207e30274bc59dfa9eeb689c8a1b4e65cca8e3b586dc766` | 351 |
| `results/current_paper/second_model/openai/test_run_real_test_1/raw_outputs.jsonl` | `2ffca7b8af01b9861c0ed1dcfa51483e5169ed6003a76c67ec772a271811d72c` | 149 |

This same `.gitignore` pattern applied automatically to the OpenAI
held-out test run (`test_run_real_test_1`) with no further action needed.

## What this does NOT affect

- **Gold-label leakage into prompts** — a separate, already-tested concern
  (`tests/test_openai_harness.py`), unaffected by this finding.
- **Statistical results** — every aggregate metric (precision, recall, F1,
  coverage, Fleiss' kappa, decisions, confidence scores) is already
  captured in the committed manifests and stability report; only the raw
  free-text completions are excluded.
- **Reproducibility** — a reader with legitimate access to the frozen
  benchmark (via the gated Zenodo record, like all other restricted
  artefacts in this project) could reproduce byte-identical raw outputs
  given the same model, prompts, and parameters (all fully disclosed),
  and could verify the excluded files against the hashes above.

## Follow-up left for the author

Per `docs/release/v1.0.1_release_plan.md`'s existing pattern for other
restricted artefacts, whether to archive the real raw-output files in a
gated Zenodo record (as was done for the corrected harmonisation maps) is
an author/publication decision, not made here.
