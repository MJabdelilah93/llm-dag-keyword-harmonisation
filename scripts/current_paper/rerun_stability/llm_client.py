"""
llm_client.py — two client implementations for the rerun-stability harness.

AnthropicClient: the REAL client. Makes a genuine API call. Requires
ANTHROPIC_API_KEY. NOT invoked anywhere in Phase 1A -- Task 6 explicitly
stops before any real API call. Included here so the harness is complete
and ready for Phase 1B, not so it can be run now.

MockClient: a SYNTHETIC client for --mode dry-run ONLY. It never makes a
network call. It returns a deterministic, seeded, clearly-labelled
synthetic response so the harness's plumbing (provenance fields, guard
application, output-directory structure, multi-run analysis) can be
validated end-to-end without spending any money or touching the real
model. Every record it produces is stamped is_synthetic=true and
model_id="MOCK-not-a-real-model" so it can never be confused with a real
run's output, even if directories are later inspected out of context.
"""
import hashlib
import random
import time
from datetime import datetime, timezone

MODEL_ID = "claude-haiku-4-5-20251001"
TEMPERATURE = 0
MAX_TOKENS = 256
# top_p is deliberately NOT passed anywhere in this module -- the historical
# v1 code never passed it either (confirmed, docs/provenance/
# v1_execution_config_provenance.md), despite configs/model_config.yaml
# documenting a value of 1.0.


def prompt_hash(system_prompt: str, user_prompt: str) -> str:
    combined = system_prompt + "\n" + user_prompt
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]


class AnthropicClient:
    """Real client. Not invoked in Phase 1A."""

    def __init__(self, api_key: str):
        import anthropic  # lazy import -- never imported in dry-run mode
        self._client = anthropic.Anthropic(api_key=api_key)

    def call(self, system_prompt: str, user_prompt: str, pair_id: str = None, max_retries: int = 3) -> dict:
        ph = prompt_hash(system_prompt, user_prompt)
        ts = datetime.now(timezone.utc).isoformat()
        delays = [1, 2, 4]
        last_exc = None
        for attempt in range(max_retries):
            try:
                msg = self._client.messages.create(
                    model=MODEL_ID,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    # top_p intentionally omitted -- matches v1 execution exactly
                )
                resp_text = msg.content[0].text if msg.content else ""
                return {
                    "is_synthetic": False,
                    "prompt_hash": ph,
                    "full_response": resp_text,
                    "timestamp": ts,
                    "model_id_requested": MODEL_ID,
                    "model_id_returned_by_api": getattr(msg, "model", None),
                    "input_tokens": msg.usage.input_tokens,
                    "output_tokens": msg.usage.output_tokens,
                    "stop_reason": msg.stop_reason,
                    "attempt": attempt + 1,
                    "error": None,
                    "request_params": {"model": MODEL_ID, "max_tokens": MAX_TOKENS,
                                        "temperature": TEMPERATURE, "top_p_passed": False},
                }
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    time.sleep(delays[attempt])
        return {
            "is_synthetic": False, "prompt_hash": ph, "full_response": "", "timestamp": ts,
            "model_id_requested": MODEL_ID, "model_id_returned_by_api": None,
            "input_tokens": 0, "output_tokens": 0, "stop_reason": "error",
            "attempt": max_retries, "error": str(last_exc),
            "request_params": {"model": MODEL_ID, "max_tokens": MAX_TOKENS,
                                "temperature": TEMPERATURE, "top_p_passed": False},
        }


class MockClient:
    """Synthetic client for harness validation only. NEVER a real API call."""

    def __init__(self, seed: int, gold_lookup: dict, noise_rate: float = 0.03):
        self._rng = random.Random(seed)
        self._gold_lookup = gold_lookup  # pair_id -> gold_label, used only to make
                                          # synthetic responses realistic-shaped, NOT
                                          # to claim any evidential value
        self._noise_rate = noise_rate

    def call(self, system_prompt: str, user_prompt: str, pair_id: str = None, max_retries: int = 3):
        ph = prompt_hash(system_prompt, user_prompt)
        ts = datetime.now(timezone.utc).isoformat()
        gold = self._gold_lookup.get(pair_id, "uncertain")
        # Synthetic decision: mostly mirrors gold (to produce a plausible-shaped
        # confusion matrix for testing the analysis code), with a small
        # injected random flip rate so that stability analysis has something
        # non-trivial to measure across mock runs. This has NO evidential
        # value about the real model's behaviour.
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
            "model_id_returned_by_api": "MOCK-not-a-real-model",
            "input_tokens": len(user_prompt.split()),
            "output_tokens": len(response_text.split()),
            "stop_reason": "end_turn",
            "attempt": 1,
            "error": None,
            "request_params": {"model": "MOCK-not-a-real-model", "max_tokens": MAX_TOKENS,
                                "temperature": TEMPERATURE, "top_p_passed": False},
        }
