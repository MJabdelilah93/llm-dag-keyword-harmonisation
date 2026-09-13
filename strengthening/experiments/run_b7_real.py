"""C2 Task 6: REAL, PAID B7 (direct scholarly semantic-relation comparator)
execution over the 900 prospective pairs. Frozen four-way relation only
(same_as/broader/narrower/other); no confidence, no uncertain, no guard,
no additional context. Uses B7Client.classify(execute_paid=True) --
strengthening/baselines/b7_direct_relation/client.py -- and B7's own
strict parser. Resumable, same pattern as the other C2 real runners.

Binary mapping (applied only for evaluation, after prediction, exactly as
run_manifest.RELATION_TO_M7_BINARY already defines): same_as -> match;
broader/narrower/other -> non-match.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..baselines.b7_direct_relation.client import B7Client
from ..baselines.b7_direct_relation.run_manifest import RELATION_TO_M7_BINARY
from .frozen_inputs import build_and_write
from .paid_execution_common import append_jsonl, call_with_retries, load_completed_pair_ids
from .paid_gate import require_paid_execution_authorised

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution" / "b7"
RAW_LOG_PATH = OUT_DIR / "b7_raw_outputs.jsonl"
PREDICTIONS_CSV_PATH = OUT_DIR / "b7_predictions.csv"


def run_real(*, execute_paid: bool = False, df_override: pd.DataFrame | None = None, raw_log_path_override: Path | None = None) -> dict:
    require_paid_execution_authorised(execute_paid, "ANTHROPIC_API_KEY")

    client = B7Client()

    if df_override is not None:
        df = df_override
    else:
        frozen = build_and_write()
        df = frozen["partitions"]["pooled900"]

    raw_log_path = raw_log_path_override if raw_log_path_override is not None else RAW_LOG_PATH
    already_done = load_completed_pair_ids(raw_log_path)

    for _, row in df.iterrows():
        pair_id = row["pair_id"]
        if pair_id in already_done:
            continue

        def _call():
            return client.classify(row["string_a"], row["string_b"], execute_paid=True)

        response, n_attempts, error = call_with_retries(_call)
        timestamp = datetime.now(timezone.utc).isoformat()

        if error is not None:
            record = {
                "pair_id": pair_id, "domain": row["domain"], "timestamp": timestamp,
                "model_requested": client.model_id, "attempts": n_attempts, "error": error,
            }
        else:
            parsed = response.parsed()
            binary = RELATION_TO_M7_BINARY.get(parsed.relation) if parsed.ok else None
            record = {
                "pair_id": pair_id, "domain": row["domain"], "timestamp": timestamp,
                "model_requested": client.model_id, "model_returned": response.model_id,
                "prompt_version": response.prompt_version,
                "raw_response": response.raw_text,
                "relation": parsed.relation, "parse_ok": parsed.ok, "parse_error_kind": str(parsed.error_kind) if parsed.error_kind else None,
                "binary_label": binary,
                "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
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
            "relation": r.get("relation"), "binary_label": r.get("binary_label"), "error": r.get("error"),
        })
    pd.DataFrame(predictions_rows).to_csv(predictions_csv_path, index=False, encoding="utf-8")

    n_expected = len(pair_ids_expected)
    return {
        "n_expected_pairs": n_expected,
        "n_logged_pairs": len(pair_ids_logged),
        "n_missing_pairs": len(pair_ids_expected - pair_ids_logged),
        "n_successful": len(successful),
        "n_errors": len(errored),
        "n_parse_failures": sum(1 for r in successful.values() if not r.get("parse_ok")),
        "errored_pair_ids": sorted(errored.keys()),
        "total_input_tokens": sum(r.get("input_tokens") or 0 for r in successful.values()),
        "total_output_tokens": sum(r.get("output_tokens") or 0 for r in successful.values()),
        "total_api_attempts": sum(r.get("attempts") or 0 for r in by_pair_id.values()),
        "all_expected_unique_no_missing": (pair_ids_logged == pair_ids_expected and len(pair_ids_logged) == n_expected),
    }


if __name__ == "__main__":
    result = run_real(execute_paid=True)
    print(json.dumps(result, indent=2, default=str))
