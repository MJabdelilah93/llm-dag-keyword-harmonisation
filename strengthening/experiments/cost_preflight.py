"""C1 Task 9/10: cost preflight using REAL historical token usage (never
character-count estimates where a real log exists) plus the exact static
paid-request matrix, verified from code rather than assumed.

Historical data available in this worktree is AGGREGATE PER-RUN totals
only -- no per-call token arrays survive locally (the underlying
raw_outputs.jsonl logs are either gitignored-and-absent or archived only
on the restricted Zenodo record). Per-call mean/median/p95/max are
therefore NOT computable from local files and are reported as
unavailable rather than approximated. What IS available: exact aggregate
input/output tokens and call counts for 5 real Anthropic reruns (149
pairs each) and 2 real OpenAI runs (351 + 149 pairs), from which a
per-pair AVERAGE rate is derived and projected onto the new 900 pairs.

B6's real historical token/cost usage is not recoverable from any file
present in this worktree at all (its raw logs are Zenodo-only); this is
stated explicitly rather than invented.

Uses ONLY the current verified prices supplied for this task (2026-09-09):
  Claude Haiku 4.5:  $1.00 / 1M input tokens,  $5.00 / 1M output tokens
  GPT-5.4 nano:      $0.20 / 1M input tokens,  $1.25 / 1M output tokens
The stale root-repo constants ($0.00025/$0.00125 per 1k, i.e. $0.25/$1.25
per million) are NOT used for any new estimate here.
"""
from __future__ import annotations

import json
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"

CURRENT_PRICES_USD_PER_MTOK = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "gpt-5.4-nano-2026-03-17": {"input": 0.20, "output": 1.25},
}

# Real, recorded historical aggregate totals (see agent research: results/
# current_paper/rerun_stability/run_real_run_{1..5}/run_manifest.json and
# results/current_paper/second_model/openai/{dev,test}_run_real_*/*.json,
# cross-checked against results/current_paper/phase1b/cost_report.json).
HISTORICAL_ANTHROPIC_RERUNS_149PAIRS = [
    {"run": "real_run_1", "n_pairs": 149, "input_tokens": 62981, "output_tokens": 14137},
    {"run": "real_run_2", "n_pairs": 149, "input_tokens": 62981, "output_tokens": 14128},
    {"run": "real_run_3", "n_pairs": 149, "input_tokens": 62981, "output_tokens": 14105},
    {"run": "real_run_4", "n_pairs": 149, "input_tokens": 62981, "output_tokens": 14071},
    {"run": "real_run_5", "n_pairs": 149, "input_tokens": 62981, "output_tokens": 14111},
]
HISTORICAL_OPENAI_RUNS = [
    {"run": "real_dev_1", "n_pairs": 351, "input_tokens": 155436, "output_tokens": 20140},
    {"run": "real_test_1", "n_pairs": 149, "input_tokens": 66023, "output_tokens": 8712},
]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def per_pair_rate(runs: list[dict]) -> dict:
    total_pairs = sum(r["n_pairs"] for r in runs)
    total_input = sum(r["input_tokens"] for r in runs)
    total_output = sum(r["output_tokens"] for r in runs)
    return {
        "n_runs": len(runs),
        "total_pairs_across_runs": total_pairs,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "mean_input_tokens_per_pair": total_input / total_pairs if total_pairs else None,
        "mean_output_tokens_per_pair": total_output / total_pairs if total_pairs else None,
        "per_call_percentiles_available": False,
        "per_call_percentiles_note": (
            "No per-call token arrays survive locally for these runs (raw_outputs.jsonl is "
            "gitignored/absent or Zenodo-only); only aggregate per-run totals are available, so "
            "mean/median/p95/max PER CALL cannot be computed -- only a mean PER PAIR across runs."
        ),
    }


def estimate_cost(model_id: str, input_tokens: float, output_tokens: float) -> float:
    prices = CURRENT_PRICES_USD_PER_MTOK[model_id]
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]


def project_for_new_partitions(model_id: str, per_pair: dict) -> dict:
    mean_in = per_pair["mean_input_tokens_per_pair"]
    mean_out = per_pair["mean_output_tokens_per_pair"]
    projections = {}
    for partition_name, n_pairs in (("ce400", 400), ("diabetes500", 500), ("combined_900_new_requests", 900)):
        expected_cost = estimate_cost(model_id, mean_in * n_pairs, mean_out * n_pairs)
        # "Conservative p95-style" bound: no real per-call percentile exists (see note above),
        # so a defensible worst-case multiplier is used instead of a fabricated percentile --
        # 1.5x the mean-derived estimate, clearly labelled as a heuristic bound, not a measured p95.
        conservative_bound = expected_cost * 1.5
        worst_defensible_bound = expected_cost * 2.0
        projections[partition_name] = {
            "n_pairs": n_pairs,
            "expected_cost_usd": round(expected_cost, 4),
            "conservative_bound_usd_heuristic_1_5x": round(conservative_bound, 4),
            "worst_defensible_bound_usd_heuristic_2x": round(worst_defensible_bound, 4),
            "bound_methodology_note": (
                "No real per-call token percentile exists locally for this method (see "
                "per_call_percentiles_note); the 1.5x/2x multipliers are explicit heuristic "
                "safety margins, not measured p95/max values, and are labelled as such."
            ),
        }
    return projections


def run() -> dict:
    anthropic_rate = per_pair_rate(HISTORICAL_ANTHROPIC_RERUNS_149PAIRS)
    openai_rate = per_pair_rate(HISTORICAL_OPENAI_RUNS)

    primary_projection = project_for_new_partitions("claude-haiku-4-5-20251001", anthropic_rate)
    openai_projection = project_for_new_partitions("gpt-5.4-nano-2026-03-17", openai_rate)

    # B6 and B7: no real historical token data exists locally for either.
    # B6's real logs are Zenodo-only (never present here); B7 has never been
    # run for real at all. Both are estimated ONLY via the same per-pair
    # rate as the primary workflow (same model, same short prompt shape, no
    # guard/schema overhead difference large enough to justify a separate
    # rate) -- explicitly labelled as a cross-method proxy, not a measurement.
    b6_projection = project_for_new_partitions("claude-haiku-4-5-20251001", anthropic_rate)
    b7_projection = project_for_new_partitions("claude-haiku-4-5-20251001", anthropic_rate)

    paid_request_matrix = {
        "primary_m7": {"n_new_requests": 900, "provider": "Anthropic", "verified_from_code": "exactly 1 request per pair (scripts/run_full_workflow.py, single call site)"},
        "b6_naive_llm": {"n_new_requests": 900, "provider": "Anthropic", "verified_from_code": "exactly 1 request per pair (scripts/run_baselines.py:run_b6, single call site)"},
        "b7_direct_relation": {"n_new_requests": 900, "provider": "Anthropic", "verified_from_code": "exactly 1 request per pair (strengthening/baselines/b7_direct_relation, one classify() per pair)"},
        "b8_hybrid": {"n_new_requests": 0, "provider": "Anthropic (via B7, reused)", "verified_from_code": "b8_benchmark_eval.py reuses B7's prediction for captured pairs and predicts non-match structurally for uncaptured pairs -- zero additional classify() calls"},
        "openai_second_provider": {"n_new_requests": 900, "provider": "OpenAI", "verified_from_code": "exactly 1 request per pair (scripts/current_paper/second_model/openai, single call site)"},
        "total_anthropic_requests": 900 * 3,
        "total_openai_requests": 900,
        "note_on_pooled900": (
            "pooled900 is the UNION of ce400 and diabetes500 (900 pairs total), not an ADDITIONAL "
            "900 pairs -- each LLM-based method needs exactly 900 new requests total (run once, "
            "then evaluated three ways: CE-only, diabetes-only, pooled), not 400+500+900=1800."
        ),
    }

    result = {
        "current_prices_used": CURRENT_PRICES_USD_PER_MTOK,
        "historical_rates": {"anthropic_5_reruns_149pairs": anthropic_rate, "openai_dev_test": openai_rate},
        "cost_projection": {
            "primary_m7": primary_projection,
            "b6_naive_llm_proxy_from_primary_rate": b6_projection,
            "b7_direct_relation_proxy_from_primary_rate": b7_projection,
            "openai_second_provider": openai_projection,
            "b8_hybrid": {"n_new_requests": 0, "cost_usd": 0.0, "note": "reuses B7 predictions, adds zero new LLM calls"},
        },
        "combined_expected_cost_usd_900_new_pairs": round(
            primary_projection["combined_900_new_requests"]["expected_cost_usd"]
            + b6_projection["combined_900_new_requests"]["expected_cost_usd"]
            + b7_projection["combined_900_new_requests"]["expected_cost_usd"]
            + openai_projection["combined_900_new_requests"]["expected_cost_usd"],
            4,
        ),
        "paid_request_matrix": paid_request_matrix,
    }
    with open(REPORTS_DIR / "COST_PREFLIGHT_AND_PAID_REQUEST_MATRIX.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    _write_markdown(result)
    return result


def _write_markdown(result: dict) -> None:
    prm = result["paid_request_matrix"]
    lines = [
        "# Cost preflight and paid-request matrix (no paid call made)",
        "",
        "## Current prices used (as supplied for this task, 2026-09-09)",
        "",
        "| Model | Input $/MTok | Output $/MTok |",
        "|---|---:|---:|",
    ]
    for model, prices in result["current_prices_used"].items():
        lines.append(f"| {model} | {prices['input']} | {prices['output']} |")

    lines += ["", "## Historical per-pair rates (real, recorded; per-call percentiles NOT available locally)", ""]
    for name, rate in result["historical_rates"].items():
        lines.append(
            f"- {name}: {rate['n_runs']} runs, {rate['total_pairs_across_runs']} total pairs, "
            f"mean {rate['mean_input_tokens_per_pair']:.1f} input / {rate['mean_output_tokens_per_pair']:.1f} output tokens per pair"
        )

    lines += ["", "## Cost projection for 900 new pairs (expected / conservative 1.5x / worst-case 2x heuristic bounds)", "",
              "| Method | Expected | Conservative (1.5x) | Worst-case (2x) |", "|---|---:|---:|---:|"]
    for name, proj in result["cost_projection"].items():
        if name == "b8_hybrid":
            lines.append(f"| {name} | 0.0000 | 0.0000 | 0.0000 |")
            continue
        p = proj["combined_900_new_requests"]
        lines.append(f"| {name} | {p['expected_cost_usd']} | {p['conservative_bound_usd_heuristic_1_5x']} | {p['worst_defensible_bound_usd_heuristic_2x']} |")
    lines.append(f"\n**Combined expected cost, all four paid methods, 900 new pairs: ${result['combined_expected_cost_usd_900_new_pairs']}**")

    lines += ["", "## Paid-request matrix (verified from code, not assumed)", "",
              "| Method | New requests | Provider |", "|---|---:|---|"]
    for name in ("primary_m7", "b6_naive_llm", "b7_direct_relation", "b8_hybrid", "openai_second_provider"):
        m = prm[name]
        lines.append(f"| {name} | {m['n_new_requests']} | {m['provider']} |")
    lines += [
        "",
        f"Total Anthropic requests: {prm['total_anthropic_requests']} (primary + B6 + B7, 900 each)",
        f"Total OpenAI requests: {prm['total_openai_requests']}",
        "",
        prm["note_on_pooled900"],
    ]
    (REPORTS_DIR / "COST_PREFLIGHT_AND_PAID_REQUEST_MATRIX.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
