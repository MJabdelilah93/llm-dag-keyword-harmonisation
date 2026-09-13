"""C1 Task 5: B6 naive-LLM baseline frozen-inference runner -- DRY-RUN BY
DEFAULT.

Reuses the exact executed B6 prompt/parsing behaviour from
scripts/run_baselines.py's ``run_b6``/``parse_b6_response`` (quoted
verbatim below as constants, not re-derived): an unconstrained free-text
prompt, no schema, no guard, parsed by substring heuristic. Same pinned
model as the primary workflow (configs/model_config.yaml). No redesign,
no schema addition, no guard added to "improve" B6 -- that would no
longer be B6.

DOES NOT CALL THE API by default. Real execution requires
``execute_paid=True`` (or ``--execute-paid``) AND ANTHROPIC_API_KEY;
neither was supplied in this phase.
"""
from __future__ import annotations

import argparse
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

# Exact executed B6 prompt template (scripts/run_baselines.py:run_b6):
#   f"Are these two keywords the same concept?\n"
#   f"Keyword A: {row['keyword_a']}\n"
#   f"Keyword B: {row['keyword_b']}\n"
#   f"Answer: match, non-match, or uncertain."
B6_PROMPT_TEMPLATE = (
    "Are these two keywords the same concept?\n"
    "Keyword A: {keyword_a}\n"
    "Keyword B: {keyword_b}\n"
    "Answer: match, non-match, or uncertain."
)


def parse_b6_response(text: str) -> str:
    """Exact executed parsing heuristic (scripts/run_baselines.py:parse_b6_response)."""
    t = text.lower().strip()
    if "non-match" in t or "not the same" in t or "non_match" in t or "not match" in t:
        return "non_match"
    if "match" in t:
        return "match"
    return "uncertain"


@dataclass
class FrozenB6Config:
    model_id: str
    temperature: float
    max_tokens: int


def load_frozen_config() -> FrozenB6Config:
    with open(MODEL_CONFIG_PATH, encoding="utf-8") as f:
        model_cfg = yaml.safe_load(f)
    return FrozenB6Config(
        model_id=model_cfg["model"]["model_id"],
        temperature=model_cfg["model"]["temperature"],
        max_tokens=model_cfg["model"]["max_tokens"],
    )


def build_request(config: FrozenB6Config, keyword_a: str, keyword_b: str) -> dict:
    prompt = B6_PROMPT_TEMPLATE.format(keyword_a=keyword_a, keyword_b=keyword_b)
    return {
        "model": config.model_id,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "messages": [{"role": "user", "content": prompt}],
    }


def build_requests_for_partition(df: pd.DataFrame, config: FrozenB6Config) -> list[dict]:
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
    return {"config": vars(config), "counts": counts}


def run_real(df: pd.DataFrame, config: FrozenB6Config, *, execute_paid: bool = False):
    require_paid_execution_authorised(execute_paid, "ANTHROPIC_API_KEY")
    import anthropic  # local import: only ever reached past the gate above

    client = anthropic.Anthropic()
    results = []
    for _, row in df.iterrows():
        req = build_request(config, row["string_a"], row["string_b"])
        msg = client.messages.create(**{k: v for k, v in req.items() if not k.startswith("_")})
        text = msg.content[0].text if msg.content else ""
        results.append({"pair_id": row["pair_id"], "raw_response": text, "parsed": parse_b6_response(text)})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B6 naive-LLM frozen-inference runner (dry-run by default)")
    parser.add_argument("--execute-paid", action="store_true")
    args = parser.parse_args(argv)

    if not args.execute_paid:
        result = dry_run_all_partitions()
        print(json.dumps(result, indent=2, default=str))
        return 0

    require_paid_execution_authorised(True, "ANTHROPIC_API_KEY")
    raise SystemExit("Real execution is implemented in run_real() but is not wired into this CLI in this phase.")


if __name__ == "__main__":
    raise SystemExit(main())
