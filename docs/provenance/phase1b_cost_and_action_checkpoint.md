# Phase 1A Task 10 — Cost and User-Action Checkpoint

**Status: cost plan only. No paid call has been made anywhere in Phase 1A.**

## A. Primary Claude rerun-stability (Task 6)

Using the **actual historical per-call rate** from
`results/test_results_summary.txt` ("Test LLM cost: $0.0329" for 149
pairs → $0.0002208/call), not a synthetic estimate:

| Item | Value |
|---|---|
| Calls | 5 × 149 = **745** |
| Estimated cost | 745 × $0.0002208 ≈ **$0.1645** |
| Basis | Historical actual per-call rate, same model, same prompt, same token profile expected |

This is the single most precisely-costed line item in this document,
since it is based on real historical spend for the identical prompt and
model rather than a projection.

## B. Second model (recommended: `gemini-2.5-flash-lite`)

Using the historical benchmark's mean token profile (413 input / 94
output tokens/call) as a planning proxy, since no second-model tokens
have been measured yet:

| Item | Calls | Estimated cost |
|---|---|---|
| Dev-set threshold tuning (Task 8, Option B) | 351 | ≈ $0.028 |
| Test set (final, single pass) | 149 | ≈ $0.012 |
| Combined dev+test | 500 | ≈ $0.039 |
| Optional: 5× test reruns (if second-model rerun-stability is later wanted) | 745 | ≈ $0.059 |

If OpenAI `gpt-5.6-luna` is used instead (Task 7's documented
alternative): combined dev+test ≈ $0.098; 5 test reruns ≈ $0.146.

## Combined total (A + B, most likely scope: rerun-stability + single-pass second model, no second-model reruns)

**≈ $0.1645 + $0.039 ≈ $0.20 USD** (≈ €0.19 at a representative EUR/USD
rate — convert at the actual rate on the day of execution, not estimated
here). If second-model reruns are also wanted: **≈ $0.26 USD**.

These figures are all trivially small relative to the $13.78 already
spent on the original v1 study. Cost is not, and should not be, the
deciding factor for whether or how to proceed with Phase 1B.

## C. Exact manual actions required from the author (Claude Code cannot perform these)

| # | Action | Required for |
|---|---|---|
| 1 | Confirm the existing Anthropic account/billing has sufficient credit for ≈$0.16 of additional spend | Task 6 rerun |
| 2 | Create a Google AI Studio / Google Cloud account if one does not already exist, and enable billing | Task 8/9 (Gemini) |
| 3 | Generate a Gemini API key from Google AI Studio (or a Vertex AI service account key, if using Vertex instead of the direct Gemini API) | Task 8/9 |
| 4 | Set `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` (or `GOOGLE_API_KEY`, per the chosen SDK's convention) as local environment variables on the machine that will run the harness — **never paste either key into any chat interface, including this one** | Tasks 6, 8 |
| 5 | If OpenAI is chosen instead of/in addition to Gemini: create an OpenAI platform account, add billing, generate an API key, set `OPENAI_API_KEY` locally | Task 8/9 (alternative) |
| 6 | Explicitly authorise (a written go-ahead in this conversation, or equivalent) before a human removes the `--mode real` guard in `run_single_rerun.py` and before the second-model harness (once built) makes its first real call | Tasks 6, 8 |
| 7 | After execution, verify actual billed cost against this estimate in the provider's own billing dashboard, and note any material discrepancy | Tasks 6, 8 |

**No API key should ever be pasted into this or any other chat interface.**
Environment variables, set locally in the machine's own shell/OS
configuration, are the only mechanism this harness expects or uses.
