"""C1 Task 4: primary M7 frozen-inference runner -- DRY-RUN BY DEFAULT.

Wraps the exact request-construction logic from scripts/run_full_workflow.py
for the new CE400/diabetes500/pooled900 partitions:

  - model config: configs/model_config.yaml (claude-haiku-4-5-20251001,
    temperature 0, max_tokens 256) -- read and hash-checked, never altered;
  - frozen prompts: prompts/v1.0.0/system_prompt.txt + user_prompt_standard.txt
    (read verbatim from the canonical files, not re-typed);
  - frozen guard confidence threshold: 0.50, from results/tuned_thresholds.json
    (hash-verified) -- applied post-hoc to a response's parsed confidence,
    never used to gate which request is sent.

Confirmed by direct source inspection of scripts/run_full_workflow.py:
exactly ONE Anthropic ``client.messages.create()`` call site exists, and
it is invoked exactly once per pair (the internal retry loop on
transient failure REPLACES a failed attempt; it does not add a second,
additional call). Therefore N pairs -> exactly N intended requests
(barring retries on error, which are not additional decisions, just
re-attempts of the same one).

NO DEV TUNING. NO THRESHOLD SWEEP. NO PROMPT MODIFICATION. NO GOLD ACCESS
during request construction -- ``build_requests_for_partition`` only ever
sees pair_id/domain/string_a/string_b (see frozen_inputs.py).

DOES NOT CALL THE API by default. ``run_real()`` requires
``execute_paid=True`` (or ``--execute-paid`` on the CLI) AND
ANTHROPIC_API_KEY set; neither was supplied during this phase -- this
module has never made a real request.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from .frozen_inputs import build_and_write
from .paid_gate import require_paid_execution_authorised

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = STRENGTHENING_ROOT.parent
MODEL_CONFIG_PATH = LEGACY_ROOT / "configs" / "model_config.yaml"
TUNED_THRESHOLDS_PATH = LEGACY_ROOT / "results" / "tuned_thresholds.json"
SYSTEM_PROMPT_PATH = LEGACY_ROOT / "prompts" / "v1.0.0" / "system_prompt.txt"
USER_PROMPT_TEMPLATE_PATH = LEGACY_ROOT / "prompts" / "v1.0.0" / "user_prompt_standard.txt"

EXPECTED_TUNED_THRESHOLDS_SHA256 = "87715a443597ffa697551968d3a5784d4c4978fb539087cc94bdce7230849836"

OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "experiments" / "primary_m7_requests"


class FrozenConfigError(Exception):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class FrozenPrimaryConfig:
    model_id: str
    temperature: float
    max_tokens: int
    guard_confidence_threshold: float
    system_prompt: str
    user_prompt_template: str
    tuned_thresholds_sha256: str


def load_frozen_config() -> FrozenPrimaryConfig:
    if not MODEL_CONFIG_PATH.exists():
        raise FrozenConfigError(f"{MODEL_CONFIG_PATH} not found")
    with open(MODEL_CONFIG_PATH, encoding="utf-8") as f:
        model_cfg = yaml.safe_load(f)

    actual_hash = _sha256_file(TUNED_THRESHOLDS_PATH)
    if actual_hash != EXPECTED_TUNED_THRESHOLDS_SHA256:
        raise FrozenConfigError(
            f"tuned_thresholds.json hash mismatch -- expected {EXPECTED_TUNED_THRESHOLDS_SHA256}, got {actual_hash}. ABORT."
        )
    with open(TUNED_THRESHOLDS_PATH, encoding="utf-8") as f:
        thresholds = json.load(f)

    return FrozenPrimaryConfig(
        model_id=model_cfg["model"]["model_id"],
        temperature=model_cfg["model"]["temperature"],
        max_tokens=model_cfg["model"]["max_tokens"],
        guard_confidence_threshold=thresholds["guard_confidence_threshold"]["threshold"],
        system_prompt=SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"),
        user_prompt_template=USER_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8"),
        tuned_thresholds_sha256=actual_hash,
    )


def build_request(config: FrozenPrimaryConfig, keyword_a: str, keyword_b: str) -> dict:
    """Exact request payload shape used by scripts/run_full_workflow.py's
    single call site: model/max_tokens/temperature/system/messages. Built
    but never sent in this phase."""
    user_prompt = config.user_prompt_template.format(keyword_a=keyword_a, keyword_b=keyword_b)
    return {
        "model": config.model_id,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "system": config.system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }


def build_requests_for_partition(df: pd.DataFrame, config: FrozenPrimaryConfig) -> list[dict]:
    """df must come from frozen_inputs.py -- pair_id/domain/string_a/
    string_b only. Never touches any gold label."""
    requests = []
    for _, row in df.iterrows():
        req = build_request(config, row["string_a"], row["string_b"])
        req["_pair_id"] = row["pair_id"]
        requests.append(req)
    return requests


def dry_run_all_partitions() -> dict:
    config = load_frozen_config()
    frozen = build_and_write()
    counts = {}
    for name, df in frozen["partitions"].items():
        requests = build_requests_for_partition(df, config)
        counts[name] = {"n_pairs": len(df), "n_requests": len(requests), "requests_per_pair": 1}
    return {"config": {k: v for k, v in vars(config).items() if k not in ("system_prompt", "user_prompt_template")}, "counts": counts}


def run_real(df: pd.DataFrame, config: FrozenPrimaryConfig, *, execute_paid: bool = False) -> None:
    """Would perform real Anthropic calls if authorised. NOT invoked
    during this phase -- calling this without execute_paid=True and
    ANTHROPIC_API_KEY set always raises before any import/call."""
    require_paid_execution_authorised(execute_paid, "ANTHROPIC_API_KEY")
    import anthropic  # local import: only ever reached past the gate above

    client = anthropic.Anthropic()
    results = []
    for _, row in df.iterrows():
        req = build_request(config, row["string_a"], row["string_b"])
        msg = client.messages.create(**{k: v for k, v in req.items() if not k.startswith("_")})
        results.append({"pair_id": row["pair_id"], "response": msg})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Primary M7 frozen-inference runner (dry-run by default)")
    parser.add_argument("--execute-paid", action="store_true", help="Actually call the Anthropic API. Requires ANTHROPIC_API_KEY.")
    args = parser.parse_args(argv)

    if not args.execute_paid:
        result = dry_run_all_partitions()
        print(json.dumps(result, indent=2, default=str))
        return 0

    require_paid_execution_authorised(True, "ANTHROPIC_API_KEY")
    raise SystemExit("Real execution is implemented in run_real() but is not wired into this CLI in this phase.")


if __name__ == "__main__":
    raise SystemExit(main())
