# Phase 1A Task 7 — Second-Model Candidate Analysis

**Status: research and recommendation only. No second-provider API call
has been made. Pricing verified against official provider documentation
(OpenAI: `developers.openai.com/api/docs/pricing`, `.../docs/models`;
Google: `ai.google.dev/gemini-api/docs/pricing`), retrieved 2026-08-24.
Provider pricing and model availability change frequently — these figures
should be re-verified immediately before any Phase 1B execution.**

## Candidates considered

| Candidate | Provider | Model ID | Input $/1M | Output $/1M | Structured output | Temp=0 | Context |
|---|---|---|---|---|---|---|---|
| A | OpenAI | `gpt-5.6-luna` | $0.20 | $1.20 | Yes — JSON-schema constrained decoding via Structured Outputs | Yes | 1.05M tokens |
| B | OpenAI | `gpt-5-nano` | $0.05 | $0.40 | Yes — same mechanism as A | Yes | Not confirmed; OpenAI's smallest current-gen tier |
| C | Google | `gemini-2.5-flash-lite` | $0.10 | $0.40 | Yes — `response_schema`/`response_mime_type`, constrained decoding | Yes | 1M tokens |
| D | Google | `gemini-3.5-flash-lite` | $0.30 | $2.50 | Yes — same mechanism as C | Yes | Not confirmed; newer generation |

All four are current, generally-available API models as of 2026-08-24
capable of executing the pairwise task with exact-JSON structured output
and temperature=0, and all are dramatically cheaper than the historical
primary-model spend ($13.78 total project cost) regardless of which is
chosen — cost is not the deciding factor for any of them.

## Per-candidate detail

### A. OpenAI `gpt-5.6-luna`
- **Structured-output capability:** OpenAI's Structured Outputs feature
  (JSON-schema-constrained decoding, not just prompt-requested JSON) is
  supported for this model family.
- **Temperature 0 / equivalent:** supported as a standard API parameter.
- **Exact version pinning:** `gpt-5.6-luna` is a named tier within the
  current GPT-5.6 family (released alongside `gpt-5.6-sol`/`gpt-5.6-terra`
  after a July 2026 pricing revision). OpenAI does not appear to expose a
  further dated snapshot alias for this specific tier at time of writing —
  a real reproducibility caveat: unlike Anthropic's dated
  `claude-haiku-4-5-20251001`, this identifier could plausibly be
  repointed to a later model without a version-date suffix. This should
  be re-checked immediately before Phase 1B and the exact response
  metadata's model field logged for every call (the harness already does
  this — see Task 6).
- **Context window:** 1.05M tokens — far more than needed for two short
  keyword strings.
- **Estimated cost** (using the historical benchmark's mean 413 input /
  94 output tokens per call as a planning proxy — actual token counts per
  model may differ slightly due to different tokenizers): dev (351) ≈
  $0.069; test (149) ≈ $0.029; combined (500) ≈ $0.098; 5 test reruns
  (745 calls) ≈ $0.146.
- **Implementation effort:** low — OpenAI's Chat Completions/Responses API
  is a well-documented, widely-used pattern; a Python client library
  (`openai`) exists and is trivial to add as a project dependency.
- **Reproducibility caveat:** see pinning note above; otherwise strong
  (deterministic decoding at temperature 0, though OpenAI — like
  Anthropic — does not formally guarantee bit-identical output across
  calls even at temperature 0).

### B. OpenAI `gpt-5-nano`
- Same structured-output/temperature support as A, at roughly 3.4× lower
  cost. Positioned as OpenAI's cheapest current-generation model. Likely
  somewhat less capable than `gpt-5.6-luna` on nuanced judgement calls
  (e.g. the polysemous-acronym stratum), which is a genuine
  scientific-validity concern for a robustness test specifically meant to
  probe whether the *method* generalises — an unreasonably weak second
  model could manufacture an artificially large gap that says more about
  model capability than about the harmonisation approach.
- **Recommendation:** keep as a documented fallback if budget were ever
  the binding constraint (it is not, here) rather than the primary choice.

### C. Google `gemini-2.5-flash-lite`
- **Structured-output capability:** Google's `response_schema` mechanism
  constrains the decoder directly to the provided JSON schema — at least
  as strong a guarantee as OpenAI's Structured Outputs, and notably
  stronger than the *historical* v1 Anthropic implementation, which used
  prompt-only JSON requests with no schema enforcement at all (Phase 0A
  finding). Using a model with genuine schema enforcement for the second
  model is arguably a *fairer*, more standardised comparison than
  replicating v1's un-enforced approach a second time.
- **Temperature 0:** supported as a standard `GenerateContentConfig`
  parameter.
- **Exact version pinning:** the `2.5` generation has been generally
  available for longer than Google's newer `3.x` line, and Google
  typically publishes dated/stable aliases for its generally-available
  tiers — this should be confirmed and the most specific available
  identifier used and logged at execution time.
- **Context window:** 1M tokens.
- **Estimated cost:** dev (351) ≈ $0.028; test (149) ≈ $0.012; combined
  (500) ≈ $0.039; 5 test reruns (745 calls) ≈ $0.059. The cheapest capable
  option among the four.
- **Implementation effort:** low — Google's `google-genai` Python SDK is
  actively maintained and well documented.

### D. Google `gemini-3.5-flash-lite`
- Newer generation than C, ~3× the cost, otherwise comparable
  capabilities. A reasonable alternative if the 2.5 line is found to be
  scheduled for deprecation before Phase 1B execution, or if the newer
  generation's judgement quality is judged materially better on a small
  pilot check.

## Recommendation

**Google `gemini-2.5-flash-lite`**, with OpenAI `gpt-5.6-luna` recorded as
the strongest alternative if institutional/billing reasons favour OpenAI.

Rationale, not price-driven:
1. **Maximal independence from Anthropic** — different pretraining
   corpus, different alignment methodology, different company — exactly
   what a model-family robustness test needs, and equally true of the
   OpenAI alternative.
2. **Genuine schema-constrained structured output**, which removes one
   confounding variable (JSON-compliance failures) that the *historical*
   Anthropic implementation never controlled for, making the second-model
   comparison methodologically cleaner than a second run of the
   historical approach would be.
3. **Longer track record** at the `2.5` generation than the very recently
   revised `gpt-5.6` tier or the newer `gemini-3.x` line, reducing the
   risk of the exact model being deprecated or silently changed between
   Phase 1B execution and any later replication attempt.
4. **Cost is genuinely immaterial** at this benchmark's scale ($0.04–0.06
   total for the full dev+test evaluation) — the choice was not made on
   this basis, consistent with the task's explicit instruction not to
   choose on price alone.

This recommendation should be re-validated immediately before Phase 1B
execution (pricing, deprecation notices, and exact available model IDs
can change), not treated as permanently fixed by this document.
