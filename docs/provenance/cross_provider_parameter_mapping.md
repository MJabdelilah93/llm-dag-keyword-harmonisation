# Phase 1B / Task 3 — Cross-Provider Parameter Mapping

**Principle: conceptual protocol equivalence is required; artificial
API-parameter equality is not.** Every row below either (a) uses the same
value across providers because that value is genuinely comparable, or (b)
uses a provider-appropriate value chosen for a stated methodological
reason, or (c) is disclosed as unavailable/not attempted for a given
provider. Nothing here was tuned against any evaluation result — every
choice was fixed before any OpenAI API call (see
`docs/provenance/openai_gpt54_nano_verification_2026-08-24.md`), and
provider-specific settings are never optimised using the held-out test
set.

| Setting | Claude Haiku 4.5 (historical, primary) | Gemini 2.5 Flash-Lite (Phase 1A/1B candidate — **not executed**) | GPT-5.4 nano `2026-03-17` (Phase 1B, this document) |
|---|---|---|---|
| Model pinning | `claude-haiku-4-5-20251001`, dated snapshot | `gemini-2.5-flash-lite` (no dated snapshot used in the unexecuted design) | `gpt-5.4-nano-2026-03-17`, dated snapshot — hard-coded constant, no CLI override (tested) |
| Endpoint | Anthropic Messages API | Gemini `generate_content` | OpenAI **Responses API** (`/v1/responses`) — the documented current interface for this model family |
| Temperature | `0` | `0` | `0` — **valid only because `reasoning.effort="none"`**; at any higher reasoning effort this model family rejects the parameter outright (verified, not assumed) |
| Reasoning / thinking effort | N/A — no reasoning mode exists for this model | `thinking_budget=0` (explicit, since default could change) | `reasoning.effort="none"` — chosen as the closest conceptual equivalent to "no reasoning mode," not picked from the grid for performance |
| Structured outputs | **Not available** — JSON requested via prompt instruction only, parsed with regex fence-strip + `json.loads()` (Phase 0A finding) | `response_mime_type="application/json"` + `response_json_schema` (schema-enforced) | `text.format={"type":"json_schema","strict":true,"schema":...}` (schema-enforced) — same schema file (`schemas/llm_response.schema.json`) as Gemini's design, `additionalProperties:false` already present so `strict:true` is satisfied without alteration |
| Max output tokens | `max_tokens=256` | `max_output_tokens=256` | `max_output_tokens=256` — identical across all three for direct comparability |
| Seed | **Not supported** — Anthropic's API has no seed parameter | `seed=42` (documented, genuine Gemini feature) | **Not supported** — GPT-5 reasoning models reject a seed parameter (verified). A genuine three-way asymmetry: Claude has no seed, Gemini has one, GPT-5.4 nano has none. None of the three conditions can claim seed-level reproducibility except the (unexecuted) Gemini design. |
| `top_p` | Not passed | Not passed (matched to Claude for comparability, despite being available) | Not passed |
| Other sampling params (`presence_penalty`, `frequency_penalty`, `logprobs`, `best_of`) | Not applicable / not passed | Not passed | Not passed — explicitly unsupported for this model family per official guidance |
| Confidence output | Requested in prompt/schema as a `confidence` field (0-1), same G1-G4 guard applied downstream | Same schema field, same guard | Same schema field, same guard (`scripts/current_paper/second_model/openai/guard_v1.py`, byte-identical logic to the historical guard) |
| Prompt structure | `system` parameter + single user `message` | `system_instruction` config + `contents` string | `input=[{"role":"system",...},{"role":"user",...}]` — structurally analogous role-split, same byte-identical prompt text (`prompts/v1.0.0/*.txt`) |
| Retries | 3 attempts, exponential backoff (1s/2s/4s) | 3 attempts, exponential backoff (1s/2s/4s) | 3 attempts, exponential backoff (1s/2s/4s) — identical policy, verified by test (`tests/test_openai_harness.py::test_openai_client_retries_on_transient_error`) |
| Token usage metadata | input/output token counts from Anthropic usage object | `prompt_token_count` / `candidates_token_count` / `thoughts_token_count` | `usage.input_tokens` / `usage.output_tokens` / `usage.output_tokens_details.reasoning_tokens` — recorded per call regardless of expected near-zero value under `reasoning.effort="none"`, matching the disclosure precedent set for Gemini's `thinking_tokens` |
| Data retention / privacy | Standard Anthropic API terms (no training on API content by default) | Would have required a **paid** Gemini project, not Google's free tier, because the benchmark contains Scopus-derived keyword strings (Phase 1A requirement) | Standard OpenAI API terms (no training on API content by default) **plus** per-call `"store": false` to opt out of response retrieval storage. Full Zero Data Retention was checked and found to require special enterprise sales approval — **not claimed here**, since it was not actually configured (see verification doc §11) |
| Context window / max output ceiling | Not the binding constraint for this task (short prompts, short JSON responses) | Not the binding constraint | 400K input / 128K output ceiling — far in excess of what this task needs; noted for completeness only |
| Pricing (verified 2026-08-24) | N/A (already spent historically) | $0.10 / $0.40 per 1M in/out tokens (Phase 1A research, unexecuted) | $0.20 input / $0.02 cached input / $1.25 output per 1M tokens |

## What was deliberately NOT forced to match

- **Seed.** Inventing a seed for providers that do not support one would
  misrepresent the reproducibility guarantees actually available. Each
  provider's true capability is reported as-is.
- **Temperature-reasoning interaction.** GPT-5.4 nano's temperature=0 is
  usable only in combination with `reasoning.effort="none"`; this
  document does not claim temperature behaves identically across
  providers in general, only that the specific combination used here is
  valid and was chosen for a stated methodological reason (reasoning
  parity with Claude), not to force superficial parameter equality.
- **Structured-output enforcement strength.** Claude's condition is
  genuinely weaker (prompt-only JSON, no server-side schema enforcement)
  than either Gemini's or GPT-5.4 nano's. This is disclosed, not
  papered over — any behavioural difference favouring the second model
  on format-validity grounds should be attributed partly to this real
  capability asymmetry, not solely to "model quality."
- **Token accounting.** Tokenizers differ across all three providers;
  raw token counts are recorded for cost purposes only and are not used
  as a comparison metric between models.

## Cross-reference

This table operationalises the settings verified in
`docs/provenance/openai_gpt54_nano_verification_2026-08-24.md` and mirrors
the disclosure style already used in
`docs/provenance/second_model_generation_settings.md` (the unexecuted
Gemini design). The adapter implementing this table is
`scripts/current_paper/second_model/openai/llm_client.py`.
