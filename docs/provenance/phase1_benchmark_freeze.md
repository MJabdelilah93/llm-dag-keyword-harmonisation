# Phase 1 Benchmark Input Freeze

**Status: FROZEN as of 2026-08-24. No label, split membership, prompt, or
guard-threshold value may change during Phase 1A/1B.**

Full artefact hashes: `docs/provenance/phase1_benchmark_freeze_manifest.csv`.

## Confirmed confusion matrix (Full LLM-DAG, held-out test set)

Independently re-derived a third time (Phase 0A, Phase 0B, and again here)
from `results/test_predictions.csv`, unchanged since first computed:

| Quantity | Value |
|---|---|
| Test set total | 149 |
| Gold uncertain | 25 |
| Primary binary denominator (decided pairs) | 124 |
| Gold match | 43 |
| Gold non-match | 81 |
| TP | 41 |
| FP | 1 |
| FN | 2 |
| TN | 80 |
| Precision | 0.9762 |
| Recall | 0.9535 |
| F1 | 0.9647 |

These match the values supplied in the Phase 1A task specification exactly
and are treated as frozen ground truth for every Phase 1A analysis below.

## Freeze rules for Phase 1A/1B

1. No pair may move between dev/test, and no gold label may change, for
   the remainder of Phase 1 (current-paper track). Any future benchmark
   expansion belongs to the separate enhanced-study track.
2. The prompt (`prompts/v1.0.0/system_prompt.txt` +
   `user_prompt_standard.txt`) and guard threshold (0.50) used for any
   Phase 1B rerun must be byte-identical to the frozen v1 artefacts above —
   verified by hash before any API call, not just by file path.
3. `configs/v1_execution_config.yaml` is the single source of truth for
   every other pipeline parameter a rerun must reproduce (temperature,
   max_tokens, retry behaviour, absence of auxiliary context).
