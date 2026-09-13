"""C2: shared infrastructure for the four real, paid-execution runners
(primary M7, B6, B7, OpenAI robustness). Handles incremental JSONL
provenance logging (so an interrupted run never re-executes an already-
successful pair), the shared transport-retry pattern, and a faithful
reimplementation of the primary workflow's guard logic (the guard itself
cannot be imported from scripts/run_full_workflow.py -- that module
executes unconditionally at import time, including reading legacy
dev_set.csv/test_set.csv files that do not exist in this worktree).

Guard logic (G1-G4) reproduced exactly per the documented legacy
behaviour: G1 malformed JSON, G2 missing required fields, G3 invalid
decision enum, G4 confidence below threshold overrides decision to
"uncertain". G5 (contradiction check) was never implemented in the
legacy code either and is not reproduced here.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

VALID_DECISIONS = {"match", "non_match", "uncertain"}
REQUIRED_GUARD_FIELDS = {"decision", "confidence", "justification"}

RETRY_DELAYS_SECONDS = (1, 2, 4)


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
        f.flush()


def load_completed_pair_ids(path: Path) -> set[str]:
    """pair_ids with a successful (non-error) record already logged --
    used so a resumed/rerun invocation never re-executes them."""
    if not path.exists():
        return set()
    completed = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("pair_id") and not record.get("error"):
                completed.add(record["pair_id"])
    return completed


def call_with_retries(fn, *, max_retries: int = 3, delays=RETRY_DELAYS_SECONDS) -> tuple[object | None, int, str | None]:
    """Calls fn() with the legacy retry pattern (delays=[1,2,4], up to
    max_retries attempts). Returns (result, n_attempts, error_message).
    A retry is a genuine transport re-attempt of the SAME logical
    inference, never an additional logical prediction."""
    last_error = None
    for attempt in range(max_retries):
        try:
            result = fn()
            return result, attempt + 1, None
        except Exception as exc:  # noqa: BLE001 -- must capture provider/network errors generically
            last_error = str(exc)
            if attempt < max_retries - 1:
                time.sleep(delays[attempt])
    return None, max_retries, last_error


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def apply_guard(raw_response: str, confidence_threshold: float) -> dict:
    """Faithful reimplementation of the legacy apply_guard(): G1 (JSON
    parse failure), G2 (missing required fields), G3 (invalid decision
    enum), G4 (confidence below threshold -> forced "uncertain")."""
    cleaned = _strip_markdown_fence(raw_response)
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return {
            "decision": "uncertain", "confidence": None, "justification": None,
            "guard_applied": True, "guard_reason": "G1_json_parse_failure",
        }
    if not isinstance(parsed, dict) or not REQUIRED_GUARD_FIELDS.issubset(parsed.keys()):
        return {
            "decision": "uncertain", "confidence": parsed.get("confidence") if isinstance(parsed, dict) else None,
            "justification": parsed.get("justification") if isinstance(parsed, dict) else None,
            "guard_applied": True, "guard_reason": "G2_missing_required_fields",
        }
    decision = parsed["decision"]
    confidence = parsed["confidence"]
    justification = parsed["justification"]
    if decision not in VALID_DECISIONS:
        return {
            "decision": "uncertain", "confidence": confidence, "justification": justification,
            "guard_applied": True, "guard_reason": "G3_invalid_decision_enum",
        }
    try:
        conf_value = float(confidence)
    except (TypeError, ValueError):
        return {
            "decision": "uncertain", "confidence": confidence, "justification": justification,
            "guard_applied": True, "guard_reason": "G2_missing_required_fields",
        }
    if decision != "uncertain" and conf_value < confidence_threshold:
        return {
            "decision": "uncertain", "confidence": conf_value, "justification": justification,
            "guard_applied": True, "guard_reason": "G4_confidence_below_threshold",
        }
    return {
        "decision": decision, "confidence": conf_value, "justification": justification,
        "guard_applied": False, "guard_reason": None,
    }
