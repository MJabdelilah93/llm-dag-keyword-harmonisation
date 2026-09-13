# Second-Model Selection Record — 2026-08-24

**Status: prospective selection record, committed BEFORE any OpenAI API
execution, so the model-selection chronology is independently auditable.**

## Chronology

1. The original study submitted to Scientometrics used only Anthropic
   Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) — a single-model design,
   confirmed throughout Phase 0A/0B.
2. The Scientometrics editor explicitly requested evaluation with "two or
   more models" as a condition for resubmission.
3. Phase 1A (`docs/provenance/second_model_candidate_analysis.md`)
   researched candidates from independent providers, including Google
   (Gemini) and OpenAI, against official pricing and capability
   documentation retrieved 2026-08-24.
4. **Google `gemini-2.5-flash-lite` was initially recommended** during
   that pre-API planning pass, on methodological grounds (structured
   output enforcement, provider independence, cost).
5. **Before any second-model API result was observed** — no Gemini call
   was ever made; no Gemini output was ever generated or inspected — the
   research team reconsidered the choice and changed the selection to an
   OpenAI model.
6. **Final prospectively selected second model:**
   `gpt-5.4-nano-2026-03-17` (OpenAI), a dated snapshot pin.
7. **Reasons are methodological, not performance-driven** (no second-model
   result of any kind existed at the time of this decision):
   - Independent provider from Anthropic (OpenAI, not Google — either
     choice satisfies provider-independence; this is not a reversal of
     that principle, just a choice between two providers that both
     satisfy it).
   - Independent model family/architecture lineage from Claude.
   - A model class suited to short classification/extraction tasks
     (a "nano"-tier model, comparable in weight class to Claude Haiku).
   - Supports a **dated API snapshot identifier**, allowing the exact
     model version to be pinned for the lifetime of this experiment —
     addressed directly in Task 1's verification below.
   - Sufficiently capable for this task without turning the experiment
     into a frontier-model comparison, which is not the scientific
     question being asked (the question is method robustness across
     model families, not "which model is smartest").
   - Inexpensive enough to run the complete dev (351) + test (149)
     protocol transparently within the authorised USD 2.00 budget.
8. **No Gemini outputs were generated or inspected before this decision.**
   Confirmed: `results/current_paper/second_model/` (the only directory
   any Gemini dry-run or real run would have written to) contained only
   synthetic dry-run fixtures at the time of this decision, which were
   deleted after Phase 1A's harness validation and before this prompt was
   received — no Gemini-specific artefact of any kind exists in this
   repository at any point.
9. **No OpenAI result was inspected before this decision** — this
   document is being written and committed *before* Task 1's model
   verification and before any OpenAI API call of any kind.
10. **The primary model remains Claude Haiku 4.5.** GPT-5.4 nano is a
    mandatory cross-model robustness condition per the editor's
    requirement — it is not being promoted to a co-primary or replacement
    model, and every downstream table/report in this phase must label it
    accordingly (see Task 12's explicit "Primary workflow result" vs.
    "Cross-model robustness result" labelling requirement).

## What changes as a result

- The Gemini harness built in Phase 1B's earlier work
  (`scripts/current_paper/second_model/llm_client.py`'s `GeminiClient`,
  and the `run_dev_evaluation.py`/`run_test_evaluation.py` drivers) is
  **not deleted** — it remains as validated, dry-run-tested code for
  possible future use, but is not executed against a real API in this
  phase. A new, parallel OpenAI adapter is built alongside it (Task 2),
  not by rewriting the existing Gemini/Claude code.
- `docs/provenance/second_model_candidate_analysis.md` (Phase 1A) is
  **not edited** — it remains an accurate historical record of what was
  recommended and why, at the time it was written. This document
  supersedes it for the purpose of *which model is actually used*, without
  erasing the earlier reasoning.
- Every subsequent Phase 1B document, table, and report refers to the
  second model as `gpt-5.4-nano-2026-03-17` (OpenAI), never Gemini.
