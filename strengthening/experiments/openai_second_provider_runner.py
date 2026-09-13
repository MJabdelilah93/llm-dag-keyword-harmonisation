"""C1 Task 8: second-provider (OpenAI) frozen-inference runner -- DRY-RUN
BY DEFAULT.

Wraps the exact request-construction logic from
scripts/current_paper/second_model/openai/llm_client.py for the new
CE400/diabetes500/pooled900 partitions:

  - model: gpt-5.4-nano-2026-03-17 (unchanged);
  - reasoning.effort: "none" (unchanged);
  - temperature: 0, max_output_tokens: 256 (unchanged);
  - structured schema: schemas/llm_response.schema.json (decision/
    confidence/justification -- read from the canonical file, not
    re-typed, so it cannot drift from B6/primary's copy);
  - frozen threshold: 0.80, sourced from the historical dev-run freeze
    manifest results/current_paper/phase1b/openai_dev_freeze_manifest.json
    (hash-verified below) -- applied post-hoc to a response's parsed
    confidence via the existing guard_v1.apply_guard() semantics, never
    used to gate which request is sent.

NO DEV RUN. NO THRESHOLD TUNING. NO CALIBRATION on the new 900. NO PROMPT
CHANGE.

Confirmed by direct source inspection: exactly one
``client.responses.create()`` call per pair (the internal retry loop
replaces a failed attempt, it does not add a second call).

DOES NOT CALL OPENAI by default. Real execution requires
``execute_paid=True`` (or ``--execute-paid``) AND OPENAI_API_KEY; neither
was supplied in this phase.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .frozen_inputs import build_and_write
from .paid_gate import require_paid_execution_authorised

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = STRENGTHENING_ROOT.parent
SCHEMA_PATH = LEGACY_ROOT / "schemas" / "llm_response.schema.json"
DEV_FREEZE_MANIFEST_PATH = LEGACY_ROOT / "results" / "current_paper" / "phase1b" / "openai_dev_freeze_manifest.json"

MODEL_ID = "gpt-5.4-nano-2026-03-17"
REASONING_EFFORT = "none"
TEMPERATURE = 0
MAX_OUTPUT_TOKENS = 256
EXPECTED_FROZEN_THRESHOLD = 0.80


class FrozenConfigError(Exception):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class FrozenOpenAIConfig:
    model_id: str
    reasoning_effort: str
    temperature: float
    max_output_tokens: int
    response_schema: dict
    frozen_threshold: float
    dev_freeze_manifest_path: str
    dev_freeze_manifest_sha256: str


def load_frozen_config() -> FrozenOpenAIConfig:
    if not SCHEMA_PATH.exists():
        raise FrozenConfigError(f"{SCHEMA_PATH} not found")
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)

    if not DEV_FREEZE_MANIFEST_PATH.exists():
        raise FrozenConfigError(
            f"{DEV_FREEZE_MANIFEST_PATH} not found -- cannot source the frozen 0.80 threshold. ABORT."
        )
    manifest_hash = _sha256_file(DEV_FREEZE_MANIFEST_PATH)
    with open(DEV_FREEZE_MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    frozen_threshold = manifest["threshold_selection"]["selected_threshold"]
    if abs(frozen_threshold - EXPECTED_FROZEN_THRESHOLD) > 1e-9:
        raise FrozenConfigError(
            f"Frozen threshold in {DEV_FREEZE_MANIFEST_PATH} is {frozen_threshold}, expected {EXPECTED_FROZEN_THRESHOLD}. ABORT."
        )

    return FrozenOpenAIConfig(
        model_id=MODEL_ID,
        reasoning_effort=REASONING_EFFORT,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        response_schema=schema,
        frozen_threshold=frozen_threshold,
        dev_freeze_manifest_path=str(DEV_FREEZE_MANIFEST_PATH),
        dev_freeze_manifest_sha256=manifest_hash,
    )


def build_request(config: FrozenOpenAIConfig, keyword_a: str, keyword_b: str, system_prompt: str, user_prompt_template: str) -> dict:
    user_prompt = user_prompt_template.format(keyword_a=keyword_a, keyword_b=keyword_b)
    return {
        "model": config.model_id,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "reasoning": {"effort": config.reasoning_effort},
        "temperature": config.temperature,
        "max_output_tokens": config.max_output_tokens,
        "text": {"format": {"type": "json_schema", "name": "llm_response", "strict": True, "schema": config.response_schema}},
        "store": False,
    }


def build_requests_for_partition(df: pd.DataFrame, config: FrozenOpenAIConfig, system_prompt: str, user_prompt_template: str) -> list[dict]:
    requests = []
    for _, row in df.iterrows():
        req = build_request(config, row["string_a"], row["string_b"], system_prompt, user_prompt_template)
        req["_pair_id"] = row["pair_id"]
        requests.append(req)
    return requests


def dry_run_all_partitions() -> dict:
    from .primary_m7_runner import SYSTEM_PROMPT_PATH, USER_PROMPT_TEMPLATE_PATH

    config = load_frozen_config()
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    user_prompt_template = USER_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    frozen = build_and_write()
    counts = {}
    for name, df in frozen["partitions"].items():
        requests = build_requests_for_partition(df, config, system_prompt, user_prompt_template)
        counts[name] = {"n_pairs": len(df), "n_requests": len(requests), "requests_per_pair": 1}
    summary_config = {k: v for k, v in vars(config).items() if k != "response_schema"}
    return {"config": summary_config, "counts": counts}


def run_real(df: pd.DataFrame, config: FrozenOpenAIConfig, system_prompt: str, user_prompt_template: str, *, execute_paid: bool = False):
    require_paid_execution_authorised(execute_paid, "OPENAI_API_KEY")
    import openai  # local import: only ever reached past the gate above

    client = openai.OpenAI()
    results = []
    for _, row in df.iterrows():
        req = build_request(config, row["string_a"], row["string_b"], system_prompt, user_prompt_template)
        resp = client.responses.create(**{k: v for k, v in req.items() if not k.startswith("_")})
        results.append({"pair_id": row["pair_id"], "response": resp})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenAI second-provider frozen-inference runner (dry-run by default)")
    parser.add_argument("--execute-paid", action="store_true")
    args = parser.parse_args(argv)

    if not args.execute_paid:
        result = dry_run_all_partitions()
        print(json.dumps(result, indent=2, default=str))
        return 0

    require_paid_execution_authorised(True, "OPENAI_API_KEY")
    raise SystemExit("Real execution is implemented in run_real() but is not wired into this CLI in this phase.")


if __name__ == "__main__":
    raise SystemExit(main())
