"""Real Anthropic transport for B7 -- C1 Task 6.

This module is imported ONLY from inside ``B7Client.classify(...,
execute_paid=True)``, itself only reached after that method's own
``execute_paid`` check has already passed. It is never imported by
default and never imported by any existing (execute_paid=False, i.e.
every pre-existing) call site.

Defence in depth: this module independently re-checks for
``ANTHROPIC_API_KEY`` and raises -- WITHOUT importing ``anthropic`` --
if it is absent, so a caller cannot reach a real network call merely by
setting ``execute_paid=True`` without also holding a key. ``anthropic``
itself is imported lazily, after that check, so a key-less environment
never even loads the SDK.

Uses exactly the already-frozen B7 prompt/schema/parser (no uncertain
label, no confidence field, no guard layer, no context, no new examples,
no threshold -- the four-way relation classification is deterministic in
its label set by construction).
"""
from __future__ import annotations

import os

from . import prompt_builder

API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"
B7_MAX_TOKENS = 256


class B7PaidExecutionError(Exception):
    pass


def call_real_b7_api(model_id: str, temperature: float, keyword_a: str, keyword_b: str):
    """Performs one real Anthropic Messages API call and returns a
    B7Response. Never called except from B7Client.classify(...,
    execute_paid=True); raises before any import if the API key is
    absent."""
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        raise B7PaidExecutionError(
            f"{API_KEY_ENV_VAR} is not set -- refusing to attempt a real API call without a key present."
        )

    import anthropic  # only ever reached here, after the key check above

    from .client import B7Response, MODE_REAL  # local import: client.py is the caller, already fully loaded

    prompt = prompt_builder.build_b7_prompt(keyword_a, keyword_b)
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model_id,
        max_tokens=B7_MAX_TOKENS,
        temperature=temperature,
        system=prompt.system,
        messages=[{"role": "user", "content": prompt.user}],
    )
    raw_text = msg.content[0].text if getattr(msg, "content", None) else ""
    usage = getattr(msg, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) if usage is not None else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage is not None else 0

    return B7Response(
        keyword_a=keyword_a,
        keyword_b=keyword_b,
        raw_text=raw_text,
        model_id=model_id,
        mode=MODE_REAL,
        prompt_version=prompt.prompt_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
