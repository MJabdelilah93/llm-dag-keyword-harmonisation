"""
llm_client.py — Gemini client for the second-model (robustness) harness.

Mirrors scripts/current_paper/rerun_stability/llm_client.py's structure:
a REAL client (GeminiClient) and a SYNTHETIC MockClient for dry-run
validation only. The MockClient never makes a network call and every
record it produces is stamped is_synthetic=true.

Generation settings (Phase 1B Task 2), verified against official Gemini
API documentation on 2026-08-24:
  - temperature = 0        (minimises stochasticity; Google's own docs
                             state this is "mostly deterministic," not a
                             formal guarantee -- same caveat as Claude)
  - seed = 42               (an official, documented parameter -- NOT
                             available for the historical Claude setup;
                             genuine, disclosed provider difference)
  - thinking_budget = 0     (gemini-2.5-flash-lite has thinking disabled
                             by default; set explicitly here for
                             auditability rather than relying on an
                             implicit default)
  - top_p: NOT set           (left at provider default, matching the
                             historical Claude call which also never
                             passed top_p)
  - response_mime_type = "application/json" + response_json_schema
                             (genuine schema-constrained decoding --
                             stronger than the historical Claude call's
                             prompt-only JSON request; disclosed as a
                             provider difference in
                             docs/provenance/second_model_generation_settings.md)
"""
import hashlib
import random
import time
from datetime import datetime, timezone

MODEL_ID = "gemini-2.5-flash-lite"
TEMPERATURE = 0
SEED = 42
MAX_OUTPUT_TOKENS = 256
THINKING_BUDGET = 0

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


class GeminiClient:
    """Real client. Makes genuine API calls when used."""

    def __init__(self, api_key: str):
        from google import genai  # lazy import -- never imported in dry-run mode
        self._genai = genai
        self._types = __import__("google.genai.types", fromlist=["types"])
        self._client = genai.Client(api_key=api_key)

    def call(self, system_prompt: str, user_prompt: str, pair_id: str = None, max_retries: int = 3) -> dict:
        types = self._types
        ph = prompt_hash(system_prompt, user_prompt)
        ts = datetime.now(timezone.utc).isoformat()
        delays = [1, 2, 4]
        last_exc = None
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=TEMPERATURE,
            seed=SEED,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
            response_mime_type="application/json",
            response_json_schema=RESPONSE_SCHEMA,
        )
        for attempt in range(max_retries):
            try:
                resp = self._client.models.generate_content(
                    model=MODEL_ID,
                    contents=user_prompt,
                    config=config,
                )
                resp_text = resp.text if resp.text else ""
                usage = getattr(resp, "usage_metadata", None)
                input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
                output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
                thinking_tokens = getattr(usage, "thoughts_token_count", None) if usage else 0
                model_version_returned = getattr(resp, "model_version", None)
                finish_reason = None
                try:
                    finish_reason = resp.candidates[0].finish_reason if resp.candidates else None
                    finish_reason = str(finish_reason) if finish_reason is not None else None
                except Exception:
                    pass
                return {
                    "is_synthetic": False,
                    "prompt_hash": ph,
                    "full_response": resp_text,
                    "timestamp": ts,
                    "model_id_requested": MODEL_ID,
                    "model_version_returned_by_api": model_version_returned,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "thinking_tokens": thinking_tokens or 0,
                    "finish_reason": finish_reason,
                    "attempt": attempt + 1,
                    "error": None,
                    "request_params": {"model": MODEL_ID, "temperature": TEMPERATURE, "seed": SEED,
                                        "max_output_tokens": MAX_OUTPUT_TOKENS,
                                        "thinking_budget": THINKING_BUDGET, "top_p_passed": False,
                                        "response_schema_enforced": True},
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
            "request_params": {"model": MODEL_ID, "temperature": TEMPERATURE, "seed": SEED,
                                "max_output_tokens": MAX_OUTPUT_TOKENS,
                                "thinking_budget": THINKING_BUDGET, "top_p_passed": False,
                                "response_schema_enforced": True},
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
            "finish_reason": "STOP",
            "attempt": 1,
            "error": None,
            "request_params": {"model": "MOCK-not-a-real-model", "temperature": TEMPERATURE, "seed": SEED,
                                "max_output_tokens": MAX_OUTPUT_TOKENS,
                                "thinking_budget": THINKING_BUDGET, "top_p_passed": False,
                                "response_schema_enforced": True},
        }
