# Phase 1B / Task 1 — OpenAI `gpt-5.4-nano-2026-03-17` Verification

**Verified against official OpenAI API documentation
(`developers.openai.com/api/docs/...`) on 2026-08-24, before any OpenAI API
call of any kind was made. No paid call was used to perform this
verification — it is a documentation check only.**

## 1. Does the exact pinned snapshot exist?

**YES.** `gpt-5.4-nano-2026-03-17` is listed as an available, currently
callable dated snapshot of GPT-5.4 nano on the official model page
(`developers.openai.com/api/docs/models/gpt-5.4-nano`). GPT-5.4 nano was
released 2026-03-17; the dated snapshot identifier matches the release
date, consistent with OpenAI's snapshot-naming convention for other model
families.

**Decision: proceed.** No substitution is required, so the "STOP and
request author approval" branch of Task 1 does not apply.

## 2. Endpoint / API method

- **Responses API** (`POST https://api.openai.com/v1/responses`) is the
  documented, current interface for GPT-5.x models, and is required (not
  merely preferred) for controlling `reasoning.effort` — the older Chat
  Completions endpoint is not the primary documented path for this model
  family's reasoning controls.
- Model id goes in the top-level `"model"` field.
- System/instructions and user text both go in the `"input"` array as
  `{"role": "system"|"user", "content": "..."}` objects — structurally
  analogous to Claude's `system` parameter + `messages` list, and to
  Gemini's `system_instruction` + `contents`.

## 3. Structured output (schema-constrained decoding)

**Supported**, via:
```json
"text": {
  "format": {
    "type": "json_schema",
    "name": "llm_response",
    "strict": true,
    "schema": { ... }
  }
}
```
This is genuinely comparable to Gemini's `response_json_schema` (both are
server-side schema-enforced, unlike the historical Claude call's
prompt-only JSON request). The exact schema from
`schemas/llm_response.schema.json` will be reused verbatim, with
`"additionalProperties": false` added if not already present, since
OpenAI's `strict: true` mode requires it.

## 4. Reasoning effort

Confirmed supported values for this model: `none` (default per some
routes, but GPT-5.x reasoning defaults can be `medium` unless explicitly
set — **this harness will explicitly set the value on every call, never
relying on an implicit default**), `low`, `medium`, `high`, `xhigh`.
Shape: `"reasoning": {"effort": "..."}`.

**Selected value for this experiment: `"none"`.** Rationale (methodological,
not a tuning choice — decided here, before any call, not after seeing
results): Claude Haiku 4.5 has no reasoning/thinking mode at all for the
historical call, so `reasoning.effort = "none"` is the closest available
conceptual equivalent — a direct, extended-thinking-off condition — not an
arbitrary pick from the grid. Using any effort above `none` would introduce
an capability axis (multi-step internal reasoning) that has no analogue in
the historical primary-model condition, confounding "different model" with
"different reasoning depth."

## 5. Temperature support — critical, non-obvious finding

**Temperature is NOT supported unconditionally for this model family.**
Per official documentation and confirmed by independent reports of the
API's 400-error behaviour: GPT-5.x reasoning models accept `temperature`
**only when `reasoning.effort = "none"`**; at any higher effort level,
the API rejects the parameter.

Because this harness has independently selected `reasoning.effort = "none"`
for the reasoning-parity rationale above, **`temperature = 0` is legally
and validly usable in this specific combination** — this is not
"inventing" support that doesn't exist; the two settings happen to be
jointly compatible, and are being used together intentionally, not to
manufacture parity but because both were selected for independent, correct
reasons. If reasoning.effort had been forced to a value above `none` for
any reason, temperature=0 would have been correctly omitted, not simulated.

## 6. Seed parameter — genuine provider difference, disclosed

**NOT supported.** OpenAI's GPT-5 reasoning-model family does not accept a
`seed` parameter (confirmed via official parameter-compatibility guidance
and independent developer reports of explicit rejection). This is a real,
disclosed asymmetry:
- Claude (historical primary model): no seed parameter (API has none).
- Gemini (Phase 1A/1B candidate, not executed): `seed` supported.
- **OpenAI GPT-5.4 nano: `seed` NOT supported.**

No seed will be passed, and none will be fabricated or approximated. This
is recorded here specifically so the manuscript never implies seed-level
reproducibility was attempted for the OpenAI condition.

## 7. Other explicitly unsupported parameters (will not be passed)

`presence_penalty`, `frequency_penalty`, `logprobs`, `top_logprobs`,
`best_of`, `top_p` — avoided entirely for this model family per official
guidance, consistent with the historical Claude call also never passing
`top_p`.

## 8. Token usage metadata

The Responses API returns a `usage` object with `output_tokens_details`,
which contains `reasoning_tokens` as a distinct field from ordinary output
tokens — directly analogous to Gemini's `thinking_tokens` field. With
`reasoning.effort = "none"` this is expected to be ~0, but it will be
recorded per-call regardless, matching the disclosure precedent already
set for Gemini's `thinking_budget = 0`.

## 9. Context window and max output tokens

400,000 input token context window; up to 128,000 output tokens. This
harness will pass `max_output_tokens = 256`, identical to the historical
Claude `max_tokens` value and the (unexecuted) Gemini `max_output_tokens`
value, for cross-condition comparability.

## 10. Current official pricing (verified 2026-08-24)

| | Price |
|---|---|
| Input tokens | $0.20 / 1M tokens |
| Cached input tokens | $0.02 / 1M tokens |
| Output tokens (includes reasoning tokens) | $1.25 / 1M tokens |

At this pricing, the authorised dev (351) + test (149) = 500 pairs, each
with a short prompt (~50-100 input tokens) and a ~256-token JSON response
capped output, is expected to cost well under USD 0.50 total for the
OpenAI portion alone — consistent with the USD 2.00 combined hard-stop
being a safety ceiling, not an expected spend.

## 11. Data retention / API privacy settings

Two independent, genuine controls exist, and neither requires inventing
anything:

1. **Standard API data-usage policy**: OpenAI's developer API platform
   (`platform.openai.com` / `api.openai.com`) operates under API-specific
   terms that do **not** use API-submitted content to train models by
   default, for any paid API account — this is structurally different
   from the consumer ChatGPT product's default settings, and requires no
   special enrolment. Standard abuse-monitoring retention is 30 days.
2. **Per-request opt-out of storage**: the Responses API accepts a
   `"store": false` field on each request, which prevents that
   response from being retained for retrieval via the API's own
   response-storage feature. This harness will set `"store": false` on
   every call as an additional, real, documented data-minimisation step —
   directly analogous in spirit to the Scopus-derived-data caution
   originally raised for Gemini's free-vs-paid tier distinction, applied
   here via the mechanism OpenAI's API actually offers.
3. **Full Zero Data Retention (ZDR)** exists but requires special
   enterprise eligibility approval via OpenAI sales; it is **not**
   available to a standard individual paid account and is **not** claimed
   or required here. This harness relies on (1) and (2) above, not ZDR,
   and this document says so explicitly rather than overclaiming a
   privacy posture that was not actually configured.

## Verdict

`gpt-5.4-nano-2026-03-17` is verified as an existing, callable, dated
snapshot. Task 1 concludes with **PROCEED** — no substitution, no STOP.
Every parameter choice in `docs/provenance/cross_provider_parameter_mapping.md`
(Task 3) traces back to a specific finding in this document; nothing in
the adapter (Task 2) invents a capability not confirmed here.
