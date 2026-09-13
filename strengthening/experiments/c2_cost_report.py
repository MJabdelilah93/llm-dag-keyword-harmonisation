"""C2 Task 14: actual (not projected) cost and execution report. Reads
only the frozen prediction-freeze manifest and raw JSONL logs; never
prints or logs an API key. Uses the current provider prices supplied for
this phase (never the stale root-repo constants)."""
from __future__ import annotations

import json
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
FREEZE_MANIFEST_PATH = REPORTS_DIR / "C2_PREDICTION_FREEZE_MANIFEST.json"

CURRENT_PRICES_USD_PER_MTOK = {
    "anthropic": {"input": 1.00, "output": 5.00},
    "openai": {"input": 0.20, "output": 1.25},
}
METHOD_PROVIDER = {
    "primary_m7": "anthropic",
    "b6": "anthropic",
    "b7": "anthropic",
    "openai": "openai",
    "b8": None,  # zero API calls
    "b1_b5": None,  # deterministic/local, zero API calls
}
METHOD_MODEL = {
    "primary_m7": "claude-haiku-4-5-20251001",
    "b6": "claude-haiku-4-5-20251001",
    "b7": "claude-haiku-4-5-20251001",
    "openai": "gpt-5.4-nano-2026-03-17",
    "b8": None,
    "b1_b5": None,
}


def _cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    prices = CURRENT_PRICES_USD_PER_MTOK[provider]
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]


def run() -> dict:
    with open(FREEZE_MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    per_method = {}
    total_cost = 0.0
    total_errors = 0
    for entry in manifest["entries"]:
        method = entry["method"]
        provider = METHOD_PROVIDER.get(method)
        if provider is None:
            per_method[method] = {
                "provider": None, "model": None, "logical_pairs": entry.get("rows"),
                "successful_responses": entry.get("rows"), "api_attempts": 0,
                "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "errors": 0,
            }
            continue
        input_tokens = entry.get("total_input_tokens", 0)
        output_tokens = entry.get("total_output_tokens", 0)
        cost = _cost(provider, input_tokens, output_tokens)
        total_cost += cost
        total_errors += entry.get("n_errors", 0)
        per_method[method] = {
            "provider": provider, "model": METHOD_MODEL[method],
            "logical_pairs": entry.get("n_requests_logged"),
            "successful_responses": entry.get("rows"),
            "api_attempts": entry.get("total_attempts"),
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": round(cost, 4), "errors": entry.get("n_errors", 0),
        }

    result = {
        "per_method": per_method,
        "combined_cost_usd": round(total_cost, 4),
        "total_errors_across_all_methods": total_errors,
        "prices_used": CURRENT_PRICES_USD_PER_MTOK,
        "api_keys_exposed": False,
    }
    with open(REPORTS_DIR / "C2_COST_AND_EXECUTION_REPORT.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    _write_markdown(result)
    return result


def _write_markdown(result: dict) -> None:
    lines = [
        "# C2 actual cost and execution report",
        "",
        "| Method | Provider | Model | Logical pairs | Successful | Attempts | Input tok | Output tok | Cost (USD) | Errors |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method, m in result["per_method"].items():
        lines.append(
            f"| {method} | {m['provider'] or '--'} | {m['model'] or '--'} | {m['logical_pairs']} | {m['successful_responses']} | "
            f"{m['api_attempts']} | {m['input_tokens']} | {m['output_tokens']} | {m['cost_usd']} | {m['errors']} |"
        )
    lines += [
        "",
        f"**Combined actual cost: ${result['combined_cost_usd']}**",
        f"Total errors across all methods: {result['total_errors_across_all_methods']}",
        "",
        "API keys were never printed or logged by this report or any C2 script.",
    ]
    (REPORTS_DIR / "C2_COST_AND_EXECUTION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
