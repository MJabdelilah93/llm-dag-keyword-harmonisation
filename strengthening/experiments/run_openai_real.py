"""C2 Task 8: REAL, PAID OpenAI second-provider robustness execution over
the 900 prospective pairs. Frozen model (gpt-5.4-nano-2026-03-17),
reasoning.effort="none", frozen threshold 0.80 (hash-verified against its
source freeze manifest). No dev run, no recalibration, no prompt change.
Resumable, same pattern as the other C2 real runners.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .frozen_inputs import build_and_write
from .openai_second_provider_runner import build_request, load_frozen_config
from .paid_execution_common import append_jsonl, apply_guard, call_with_retries, load_completed_pair_ids
from .paid_gate import require_paid_execution_authorised
from .primary_m7_runner import SYSTEM_PROMPT_PATH, USER_PROMPT_TEMPLATE_PATH

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution" / "openai"
RAW_LOG_PATH = OUT_DIR / "openai_raw_outputs.jsonl"
PREDICTIONS_CSV_PATH = OUT_DIR / "openai_predictions.csv"


def _extract_output_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    # Fallback: walk the Responses API's structured output list.
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            candidate = getattr(content, "text", None)
            if candidate:
                return candidate
    return ""


def run_real(*, execute_paid: bool = False, df_override: pd.DataFrame | None = None, raw_log_path_override: Path | None = None) -> dict:
    require_paid_execution_authorised(execute_paid, "OPENAI_API_KEY")
    import openai  # local import: only ever reached past the gate above

    config = load_frozen_config()
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    user_prompt_template = USER_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    if df_override is not None:
        df = df_override
    else:
        frozen = build_and_write()
        df = frozen["partitions"]["pooled900"]

    raw_log_path = raw_log_path_override if raw_log_path_override is not None else RAW_LOG_PATH
    client = openai.OpenAI()
    already_done = load_completed_pair_ids(raw_log_path)

    for _, row in df.iterrows():
        pair_id = row["pair_id"]
        if pair_id in already_done:
            continue

        request = build_request(config, row["string_a"], row["string_b"], system_prompt, user_prompt_template)
        api_kwargs = {k: v for k, v in request.items() if not k.startswith("_")}

        def _call():
            return client.responses.create(**api_kwargs)

        response, n_attempts, error = call_with_retries(_call)
        timestamp = datetime.now(timezone.utc).isoformat()

        if error is not None:
            record = {
                "pair_id": pair_id, "domain": row["domain"], "timestamp": timestamp,
                "model_requested": config.model_id, "attempts": n_attempts, "error": error,
            }
        else:
            raw_text = _extract_output_text(response)
            usage = getattr(response, "usage", None)
            guard_result = apply_guard(raw_text, config.frozen_threshold)
            record = {
                "pair_id": pair_id, "domain": row["domain"], "timestamp": timestamp,
                "model_requested": config.model_id,
                "model_returned": getattr(response, "model", None),
                "raw_response": raw_text,
                "guard_decision": guard_result["decision"],
                "guard_confidence": guard_result["confidence"],
                "guard_justification": guard_result["justification"],
                "guard_applied": guard_result["guard_applied"],
                "guard_reason": guard_result["guard_reason"],
                "confidence_threshold": config.frozen_threshold,
                "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
                "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
                "attempts": n_attempts, "error": None,
            }
        append_jsonl(raw_log_path, record)

    predictions_csv_path = PREDICTIONS_CSV_PATH if raw_log_path_override is None else raw_log_path.parent / (raw_log_path.stem + "_predictions.csv")
    return _validate_and_summarise(df, raw_log_path, predictions_csv_path)


def _validate_and_summarise(df: pd.DataFrame, raw_log_path: Path, predictions_csv_path: Path) -> dict:
    rows = []
    if raw_log_path.exists():
        with open(raw_log_path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]

    by_pair_id = {r["pair_id"]: r for r in rows}
    pair_ids_expected = set(df["pair_id"])
    pair_ids_logged = set(by_pair_id.keys())
    successful = {pid: r for pid, r in by_pair_id.items() if not r.get("error")}
    errored = {pid: r for pid, r in by_pair_id.items() if r.get("error")}

    predictions_rows = []
    for _, row in df.iterrows():
        pid = row["pair_id"]
        r = by_pair_id.get(pid, {})
        predictions_rows.append({
            "pair_id": pid, "domain": row["domain"],
            "guard_decision": r.get("guard_decision"),
            "guard_confidence": r.get("guard_confidence"),
            "error": r.get("error"),
        })
    pd.DataFrame(predictions_rows).to_csv(predictions_csv_path, index=False, encoding="utf-8")

    n_expected = len(pair_ids_expected)
    return {
        "n_expected_pairs": n_expected,
        "n_logged_pairs": len(pair_ids_logged),
        "n_missing_pairs": len(pair_ids_expected - pair_ids_logged),
        "n_successful": len(successful),
        "n_errors": len(errored),
        "errored_pair_ids": sorted(errored.keys()),
        "total_input_tokens": sum(r.get("input_tokens") or 0 for r in successful.values()),
        "total_output_tokens": sum(r.get("output_tokens") or 0 for r in successful.values()),
        "total_api_attempts": sum(r.get("attempts") or 0 for r in by_pair_id.values()),
        "all_expected_unique_no_missing": (pair_ids_logged == pair_ids_expected and len(pair_ids_logged) == n_expected),
    }


if __name__ == "__main__":
    result = run_real(execute_paid=True)
    print(json.dumps(result, indent=2, default=str))
