# Phase 1B Task 2 — Gemini Generation Settings

**Verified against official Gemini API documentation (`ai.google.dev`,
Google Cloud docs) and the installed `google-genai` 2.19.0 SDK's own type
definitions, 2026-08-24. No parameter below was invented — every field
used is a genuine, documented `GenerateContentConfig`/`ThinkingConfig`
field, confirmed by direct introspection of the installed SDK.**

| Setting | Value | Basis |
|---|---|---|
| `temperature` | 0 | Minimises stochasticity. Google's own documentation states temperature=0 is "mostly deterministic" but not a formal bitwise guarantee — the same caveat already documented for Claude. |
| `seed` | 42 | A genuine, documented `GenerateContentConfig` field. **Not available for the historical Claude call** (Anthropic's API has no equivalent parameter) — a real, disclosed provider difference, not an inconsistency to paper over. Community reports (2025-2026) note occasional non-determinism even with temperature=0 and a fixed seed on some Gemini model tiers; noted here as a known limitation, not assumed away. |
| `thinking_budget` | 0 | `gemini-2.5-flash-lite` has thinking disabled by default; set explicitly here for auditability rather than relying on an implicit default that could change. Keeps the second model "lightweight" and conceptually comparable to the historical primary model, which has no reasoning/thinking mode at all. |
| `top_p` | not set (provider default) | Matches the historical Claude call, which also never passed `top_p` — chosen for comparability, not because Gemini lacks the parameter (it has one). |
| `max_output_tokens` | 256 | Matches the historical Claude `max_tokens` value exactly. |
| `response_mime_type` / `response_json_schema` | `"application/json"` / the exact schema from `schemas/llm_response.schema.json` | **Genuine schema-constrained decoding** — a real, disclosed improvement over the historical Claude call, which only requested JSON via prompt instruction with no server-side enforcement (Phase 0A finding). This is a deliberate, documented asymmetry: it makes the Gemini condition *more* format-reliable than history's Claude condition, which is scientifically honest to disclose rather than hide. |

## Deliberate exclusions

- **No auxiliary title/abstract context** — matches the historical
  primary-model condition exactly (Phase 0A confirmed context was never
  used for any of the 500 benchmark pairs).
- **Same prompt text** — `prompts/v1.0.0/system_prompt.txt` and
  `user_prompt_standard.txt`, byte-identical to what the primary model
  received (delivered via Gemini's `system_instruction` config field and
  a plain user `contents` string respectively), so any difference in
  results reflects the model, not the prompt.

## Unavoidable provider-specific differences (disclosed, not hidden)

1. Gemini supports a `seed` parameter; Claude's API does not.
2. Gemini's structured output is schema-enforced at the decoding level;
   the historical Claude call's JSON request was prompt-only, parsed with
   a regex fence-strip + `json.loads()`.
3. Gemini exposes a `thinking_tokens` usage field (relevant for models
   with reasoning enabled); explicitly zeroed out here via
   `thinking_budget=0`, but recorded per-call regardless for transparency.
4. Token counting methodology differs between the two providers'
   tokenizers — token counts are not directly comparable 1:1 across
   models even for the same rendered prompt text; only the resulting
   cost and classification decisions are compared, not raw token counts.

These differences are recorded here so that, if the manuscript later
attributes any behavioural difference between the two models, it is clear
which differences are genuine model-family effects and which are
artefacts of unavoidable API surface differences.
