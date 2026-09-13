# Dev-Log Provenance Repair — Summary

**Status: RETROSPECTIVELY RECONSTRUCTED, derived metadata only. No new API
call was made. The historical log was not modified.**

## What was wrong

`results/llm_logs/dev_workflow_raw_outputs.jsonl` (historical evidence,
never modified, SHA-256 `52eb5d9e1560909c5f4b3c474307d95fbea0210d6088c87d2b3376963cd5a62b`)
stores, for all 351 valid JSON log lines, `guard_applied="G1"`,
`guard_reason="malformed_parse_failure"`, `raw_decision="uncertain"`,
`guard_decision="uncertain"` — a uniform 100% failure signature. Read at
face value, the file implies the guard rejected every single dev-set
response.

## What was actually true

The stored `full_response` text (the raw model output) is intact: 350 of 351
entries (99.7%) parse as valid JSON with all three required fields when
re-parsed today. The corruption is confined entirely to the log's own
*stored* derived-metadata columns, not the underlying evidence.

## The repair

`scripts/current_paper/reparse_dev_log_v1.py` reads the historical log
read-only and re-applies the verified v1 G1-G4 guard logic (copied verbatim
from `scripts/run_full_workflow.py`) to each entry's unchanged
`full_response` field. It writes a new, separately-named derived artefact —
`dev_workflow_reparsed_v1.jsonl` — that is **not** a replacement for the
original log.

Because the derived artefact still contains real Scopus-derived keyword
strings and raw model text, it is written only to `restricted_local/`
(git-ignored, local machine only), consistent with this repository's
existing data-restriction policy. Only this aggregate summary is committed.

| | |
|---|---|
| Source file | `results/llm_logs/dev_workflow_raw_outputs.jsonl` |
| Source SHA-256 | `52eb5d9e1560909c5f4b3c474307d95fbea0210d6088c87d2b3376963cd5a62b` |
| Derived artefact | `restricted_local/dev_log_repair/dev_workflow_reparsed_v1.jsonl` (local only, not committed) |
| Derived artefact SHA-256 | `b86a97a5dac1ac4c88b6c5fc9f42f555b485d8de90d6f3c02f13b86e02ac141d` |
| Row count | 351 (matches source exactly) |
| Parser version | `v1_verified_guard_reparse_1.0.0` |
| New API calls made | **None** |
| Repair date (UTC) | 2026-08-24T07:48:29Z |

## Verification

Independently re-derived, from the unchanged raw text alone:

| Metric | Reparsed (this repair) | Previously reported (`results/tuned_thresholds.json`, `results/dev_results_full_workflow.csv`) | Match |
|---|---|---|---|
| Precision | 0.9798 | 0.9798 | ✅ |
| Recall | 0.9604 | 0.9604 | ✅ |
| F1 | 0.9700 | 0.97 | ✅ |
| Coverage | 0.9003 | 0.9003 | ✅ |
| Selected threshold | 0.50 | 0.50 | ✅ |

All four values match to four decimal places. This confirms the guard
threshold (0.50) and dev-set tuning numbers already reported for the
current-paper study are authentic and were not affected by the log's
metadata corruption — that corruption only ever affected the file's own
"no-guard" comparison row (`results/dev_results_full_workflow.csv`,
`Full_LLM_DAG_no_guard,dev`), which read the corrupted stored field
directly rather than re-parsing `full_response`.

## What this repair does not do

- It does not call the Anthropic API.
- It does not change `results/llm_logs/dev_workflow_raw_outputs.jsonl`.
- It does not change any benchmark label, dev/test membership, or frozen
  test prediction.
- It does not assert that the original log's corruption is now "fixed" —
  the original remains as historical evidence of the defect. Only a
  separately-named, clearly-provenanced derived copy exists with corrected
  metadata.
