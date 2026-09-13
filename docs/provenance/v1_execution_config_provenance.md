# V1 Execution Config — Provenance

**Status: RETROSPECTIVELY RECONSTRUCTED, 2026-08 audit (Phase 0A/0B).**

`configs/v1_execution_config.yaml` records what actually ran. This document
records how each value was established, and distinguishes it from the five
"legacy" config files it supersedes for documentation purposes only.

## Method

Every value in `v1_execution_config.yaml` was traced to one of three sources,
in order of authority:

1. **Executed code** — the literal constant, default argument, or hardcoded
   value in the script that produced a reported result (`scripts/*.py`, all
   read in full).
2. **Result/log files** — values persisted by that code at run time
   (`results/tuned_thresholds.json`, `results/llm_logs/*.jsonl` header
   fields, `results/*_summary.txt`).
3. **Independent re-derivation** — for the guard threshold specifically, the
   2026-08 audit re-parsed `results/llm_logs/dev_workflow_raw_outputs.jsonl`
   from scratch using the exact `apply_guard()` logic copied verbatim from
   `scripts/run_full_workflow.py`, and reproduced threshold=0.50,
   dev F1=0.9700, dev coverage=0.9003 to four decimal places — an
   independent confirmation, not just a code read.

No value in `v1_execution_config.yaml` was taken from `configs/candidate_gen_config.yaml`,
`configs/canonical_rules.yaml`, `configs/dag_config.yaml`,
`configs/eval_config.yaml`, or `configs/guard_thresholds.yaml` — those five
files were confirmed, by exhaustive repository-wide grep for their filenames,
to never be opened (`open()`, `yaml.safe_load()`, or equivalent) by any
script that produced a reported result. They are retained, each now marked
`LEGACY / NOT USED IN V1 EXECUTION` in a header comment, as historical
documentation of an earlier intended design.

## Notable divergences between "legacy" configs and what ran

| Config file | Documents | What actually ran |
|---|---|---|
| `candidate_gen_config.yaml` | Single JW threshold 0.85; embedding model `"PLACEHOLDER"`; top_k 20 | JW blocking window [0.85, 0.95); model `all-MiniLM-L6-v2`; top_k 5 (standard) / 3 (short) |
| `canonical_rules.yaml` | 4-tier rule (vocab &gt; frequency &gt; shortest &gt; alphabetical) | Frequency-only |
| `dag_config.yaml` | Guard threshold 0.80, explicitly marked "Placeholder — update before first run" (never updated) | Guard threshold 0.50 |
| `eval_config.yaml` | `dev_path`/`test_path`/`label_column` — these values on `origin/main` happen to be *correct* (they were edited at some point after the original 2026-04 run, per the public-release cleanup commits), but the file is still never read by any script | Paths/columns hardcoded independently inside each script |
| `guard_thresholds.yaml` | Asymmetric confidence thresholds (match 0.80 / non-match 0.70) + a contradiction-check (G5) design | Symmetric 0.50; G5 never implemented |

One file is **not** legacy: `configs/model_config.yaml` is loaded by every
script that calls the LLM, and its `model_id`/`temperature`/`max_tokens`
values were confirmed identical to what is recorded in every JSONL log's
per-call metadata.

## What this document is not

This is an engineering provenance note for the repair effort. It is not a
manuscript-ready methods description — see
`CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md` for the specific
Replace:/With:-ready evidence for each manuscript claim this file corrects.
