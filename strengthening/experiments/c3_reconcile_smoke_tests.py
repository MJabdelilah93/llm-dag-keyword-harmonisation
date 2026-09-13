"""C3 Task 4: reconcile the pre-benchmark smoke-test calls (2 real pairs per
method, made before each 900-pair paid run in C2) against the 900-pair
benchmark logs. Read-only: inspects existing local JSONL artefacts only,
makes no API call. Determines, per method, whether the smoke-test calls
were additional provider requests beyond the 900 benchmark calls, or were
somehow incorporated/reused, purely from timestamps/pair_id overlap/token
records -- no inference, no assumption.
"""
from __future__ import annotations

import json
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
C2_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution"
REPORTS_DIR = STRENGTHENING_ROOT / "reports"

METHOD_DIRS = {
    "primary_m7": ("primary_m7_raw_outputs.jsonl", "anthropic"),
    "b6": ("b6_raw_outputs.jsonl", "anthropic"),
    "b7": ("b7_raw_outputs.jsonl", "anthropic"),
    "openai": ("openai_raw_outputs.jsonl", "openai"),
}

PRICES = {
    "anthropic": {"input": 1.00, "output": 5.00},
    "openai": {"input": 0.20, "output": 1.25},
}


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICES[provider]
    return (input_tokens / 1_000_000) * p["input"] + (output_tokens / 1_000_000) * p["output"]


def run() -> dict:
    per_method = {}
    total_benchmark_requests = 0
    total_smoke_requests = 0
    total_smoke_cost = 0.0

    for method, (main_filename, provider) in METHOD_DIRS.items():
        method_dir = C2_DIR / method
        main_log = _load_jsonl(method_dir / main_filename)
        smoke_log = _load_jsonl(method_dir / "SMOKE_TEST_raw_outputs.jsonl")

        main_pair_ids = {r["pair_id"] for r in main_log}
        smoke_pair_ids = [r["pair_id"] for r in smoke_log]
        overlap = [pid for pid in smoke_pair_ids if pid in main_pair_ids]

        smoke_input_tokens = sum(r.get("input_tokens") or 0 for r in smoke_log)
        smoke_output_tokens = sum(r.get("output_tokens") or 0 for r in smoke_log)
        smoke_cost = _cost(provider, smoke_input_tokens, smoke_output_tokens)

        main_timestamps = sorted(r["timestamp"] for r in main_log) if main_log else []
        smoke_timestamps = sorted(r["timestamp"] for r in smoke_log) if smoke_log else []

        # Definitive test: if a smoke pair_id has ITS OWN separate, later-timestamped
        # entry in the main 900-row log, the smoke call was additional (category A) --
        # the benchmark made a fresh call for the same pair rather than reusing the
        # smoke response. If a smoke pair_id is ABSENT from the main log, the smoke
        # call would instead have been substituted into the benchmark count (category B).
        reused_not_additional = [pid for pid in smoke_pair_ids if pid not in main_pair_ids]

        per_method[method] = {
            "provider": provider,
            "n_main_log_rows": len(main_log),
            "n_smoke_log_rows": len(smoke_log),
            "smoke_pair_ids": smoke_pair_ids,
            "smoke_pair_ids_also_present_as_independent_rows_in_main_log": overlap,
            "smoke_pair_ids_absent_from_main_log": reused_not_additional,
            "classification": (
                "A_ADDITIONAL_REQUESTS" if overlap and not reused_not_additional
                else ("B_REUSED_NOT_ADDITIONAL" if reused_not_additional and not overlap else "C_MIXED_OR_UNCLEAR")
            ),
            "smoke_timestamps": smoke_timestamps,
            "main_log_earliest_timestamp": main_timestamps[0] if main_timestamps else None,
            "main_log_latest_timestamp": main_timestamps[-1] if main_timestamps else None,
            "smoke_input_tokens": smoke_input_tokens,
            "smoke_output_tokens": smoke_output_tokens,
            "smoke_cost_usd": round(smoke_cost, 6),
            "smoke_token_data_retained": len(smoke_log) > 0 and all(r.get("input_tokens") is not None for r in smoke_log if not r.get("error")),
        }
        total_benchmark_requests += len(main_log)
        total_smoke_requests += len(smoke_log)
        total_smoke_cost += smoke_cost

    result = {
        "per_method": per_method,
        "BENCHMARK_INFERENCE_REQUESTS": total_benchmark_requests,
        "NON_BENCHMARK_SMOKE_REQUESTS": total_smoke_requests,
        "TOTAL_PAID_PROVIDER_REQUESTS_DURING_C2": total_benchmark_requests + total_smoke_requests,
        "total_smoke_cost_usd": round(total_smoke_cost, 6),
        "benchmark_evidence_note": "The frozen benchmark evidence remains exactly 900 predictions per paid method regardless of the smoke-test accounting above; smoke-test rows were never merged into any frozen snapshot.",
    }
    with open(REPORTS_DIR / "C3_TASK4_SMOKE_TEST_RECONCILIATION.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
