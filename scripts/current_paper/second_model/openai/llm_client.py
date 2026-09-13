"""
llm_client.py -- OpenAI client for the second-model (cross-model
robustness) harness. Built as a DEDICATED adapter, alongside (not by
rewriting) the historical Anthropic implementation
(scripts/current_paper/rerun_stability/llm_client.py) and the unexecuted
Gemini implementation (scripts/current_paper/second_model/llm_client.py).

A REAL client (OpenAIClient) and a SYNTHETIC MockClient for dry-run /
leakage-test validation only. The MockClient never makes a network call
and every record it produces is stamped is_synthetic=true.

Generation settings (Phase 1B Task 2/3), verified against official OpenAI
API documentation on 2026-08-24 -- see
docs/provenance/openai_gpt54_nano_verification_2026-08-24.md for the full
verification trail and docs/provenance/cross_provider_parameter_mapping.md
for the cross-provider comparison. Nothing below is invented:

  - model            = gpt-5.4-nano-2026-03-17  (hard-pinned dated snapshot)
  - endpoint          = Responses API (POST /v1/responses)
  - reasoning.effort  = "none"   (closest conceptual equivalent to the
                                   historical Claude call, which has no
                                   reasoning/thinking mode at all -- chosen
                                   for reasoning-parity, not tuned)
  - temperature       = 0        (valid ONLY because reasoning.effort is
                                   "none" -- at any higher effort this
                                   model family rejects temperature; this
                                   harness never sets a combination the
                                   API would refuse)
  - seed              : NOT SET  (GPT-5 reasoning models do not support a
                                   seed parameter -- genuine, disclosed
                                   provider difference from Gemini, which
                                   does; no seed is fabricated)
  - top_p             : NOT SET  (matches the historical Claude call,
                                   which also never passed top_p)
  - max_output_tokens = 256      (matches the historical Claude max_tokens)
  - text.format       = json_schema, strict=True, name="llm_response",
                         schema = schemas/llm_response.schema.json verbatim
                         (genuine schema-constrained decoding, comparable
                         to the unexecuted Gemini condition, stronger than
                         the historical prompt-only Claude JSON request)
  - store             = False    (per-call data-minimisation opt-out of
                                   OpenAI's response-storage feature; see
                                   verification doc Section 11 -- this is
                                   NOT full Zero Data Retention, which is
                                   not claimed)
"""
import hashlib
import random
import time
from datetime import datetime, timezone

MODEL_ID = "gpt-5.4-nano-2026-03-17"
REASONING_EFFORT = "none"
TEMPERATURE = 0
MAX_OUTPUT_TOKENS = 256

RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["decision", "confidence", "justification"],
    "properties": {
        "decision": {"type": "string", "enum": ["match", "non_match", "uncertain"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "justification": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}


def prompt_hash(system_prompt: str, user_prompt: str) -> str:
    combined = system_prompt + "\n" + user_prompt
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]


def _request_params():
    return {"model": MODEL_ID, "reasoning_effort": REASONING_EFFORT, "temperature": TEMPERATURE,
            "seed_passed": False, "top_p_passed": False, "max_output_tokens": MAX_OUTPUT_TOKENS,
            "response_schema_enforced": True, "store": False}


class OpenAIClient:
    """Real client. Makes genuine API calls when used."""

    def __init__(self, api_key: str):
        from openai import OpenAI  # lazy import -- never imported in dry-run mode
        self._client = OpenAI(api_key=api_key)

    def call(self, system_prompt: str, user_prompt: str, pair_id: str = None, max_retries: int = 3) -> dict:
        ph = prompt_hash(system_prompt, user_prompt)
        ts = datetime.now(timezone.utc).isoformat()
        delays = [1, 2, 4]
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = self._client.responses.create(
                    model=MODEL_ID,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    reasoning={"effort": REASONING_EFFORT},
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    text={"format": {"type": "json_schema", "name": "llm_response",
                                      "strict": True, "schema": RESPONSE_SCHEMA}},
                    store=False,
                )
                resp_text = resp.output_text if resp.output_text else ""
                usage = getattr(resp, "usage", None)
                input_tokens = getattr(usage, "input_tokens", None) if usage else None
                output_tokens = getattr(usage, "output_tokens", None) if usage else None
                otd = getattr(usage, "output_tokens_details", None) if usage else None
                reasoning_tokens = getattr(otd, "reasoning_tokens", 0) if otd else 0
                model_version_returned = getattr(resp, "model", None)
                finish_reason = getattr(resp, "status", None)
                return {
                    "is_synthetic": False,
                    "prompt_hash": ph,
                    "full_response": resp_text,
                    "timestamp": ts,
                    "model_id_requested": MODEL_ID,
                    "model_version_returned_by_api": model_version_returned,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "thinking_tokens": reasoning_tokens or 0,
                    "finish_reason": finish_reason,
                    "attempt": attempt + 1,
                    "error": None,
                    "request_params": _request_params(),
                }
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    time.sleep(delays[attempt])
        return {
            "is_synthetic": False, "prompt_hash": ph, "full_response": "", "timestamp": ts,
            "model_id_requested": MODEL_ID, "model_version_returned_by_api": None,
            "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "finish_reason": "error",
            "attempt": max_retries, "error": str(last_exc),
            "request_params": _request_params(),
        }


class MockClient:
    """Synthetic client for harness validation only. NEVER a real API call."""

    def __init__(self, seed: int, gold_lookup: dict, noise_rate: float = 0.03):
        self._rng = random.Random(seed)
        self._gold_lookup = gold_lookup
        self._noise_rate = noise_rate

    def call(self, system_prompt: str, user_prompt: str, pair_id: str = None, max_retries: int = 3):
        ph = prompt_hash(system_prompt, user_prompt)
        ts = datetime.now(timezone.utc).isoformat()
        gold = self._gold_lookup.get(pair_id, "uncertain")
        if self._rng.random() < self._noise_rate:
            decision = self._rng.choice(["match", "non_match", "uncertain"])
        else:
            decision = gold if gold in ("match", "non_match") else self._rng.choice(["uncertain", "uncertain", "non_match"])
        confidence = round(self._rng.uniform(0.55, 0.99), 2)
        response_text = (f'{{"decision": "{decision}", "confidence": {confidence}, '
                          f'"justification": "SYNTHETIC MOCK RESPONSE -- not a real model output."}}')
        return {
            "is_synthetic": True,
            "prompt_hash": ph,
            "full_response": response_text,
            "timestamp": ts,
            "model_id_requested": MODEL_ID,
            "model_version_returned_by_api": "MOCK-not-a-real-model",
            "input_tokens": len(user_prompt.split()),
            "output_tokens": len(response_text.split()),
            "thinking_tokens": 0,
            "finish_reason": "completed",
            "attempt": 1,
            "error": None,
            "request_params": _request_params(),
        }
