# Cost preflight and paid-request matrix (no paid call made)

## Current prices used (as supplied for this task, 2026-09-09)

| Model | Input $/MTok | Output $/MTok |
|---|---:|---:|
| claude-haiku-4-5-20251001 | 1.0 | 5.0 |
| gpt-5.4-nano-2026-03-17 | 0.2 | 1.25 |

## Historical per-pair rates (real, recorded; per-call percentiles NOT available locally)

- anthropic_5_reruns_149pairs: 5 runs, 745 total pairs, mean 422.7 input / 94.7 output tokens per pair
- openai_dev_test: 2 runs, 500 total pairs, mean 442.9 input / 57.7 output tokens per pair

## Cost projection for 900 new pairs (expected / conservative 1.5x / worst-case 2x heuristic bounds)

| Method | Expected | Conservative (1.5x) | Worst-case (2x) |
|---|---:|---:|---:|
| primary_m7 | 0.8066 | 1.2099 | 1.6132 |
| b6_naive_llm_proxy_from_primary_rate | 0.8066 | 1.2099 | 1.6132 |
| b7_direct_relation_proxy_from_primary_rate | 0.8066 | 1.2099 | 1.6132 |
| openai_second_provider | 0.1446 | 0.217 | 0.2893 |
| b8_hybrid | 0.0000 | 0.0000 | 0.0000 |

**Combined expected cost, all four paid methods, 900 new pairs: $2.5644**

## Paid-request matrix (verified from code, not assumed)

| Method | New requests | Provider |
|---|---:|---|
| primary_m7 | 900 | Anthropic |
| b6_naive_llm | 900 | Anthropic |
| b7_direct_relation | 900 | Anthropic |
| b8_hybrid | 0 | Anthropic (via B7, reused) |
| openai_second_provider | 900 | OpenAI |

Total Anthropic requests: 2700 (primary + B6 + B7, 900 each)
Total OpenAI requests: 900

pooled900 is the UNION of ce400 and diabetes500 (900 pairs total), not an ADDITIONAL 900 pairs -- each LLM-based method needs exactly 900 new requests total (run once, then evaluated three ways: CE-only, diabetes-only, pooled), not 400+500+900=1800.