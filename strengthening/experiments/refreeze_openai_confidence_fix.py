"""One-off, fully-documented supersede-and-refreeze for the `openai`
prediction snapshot only. The original freeze (Task 9, first run) copied
`openai_predictions.csv` before a bug in `run_openai_real.py`'s
`_validate_and_summarise()` was discovered: it built the predictions CSV
without a `guard_confidence` column, even though the raw JSONL log
already recorded that field correctly for every one of the 900 real,
paid responses. The bug was caught by `c2_evaluate.py` raising a
KeyError -- not by inspecting any performance/gold number -- and the fix
is purely additive (one missing column copied from the untouched raw
log). No new API calls were made, and `guard_decision`/`error` were
verified byte-identical across all 900 rows before this script runs.

This script does NOT touch any other method's frozen snapshot. The
superseded file is kept on disk (never deleted) for audit purposes.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
C2_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution"
FREEZE_DIR = C2_DIR / "frozen_predictions"
REPORTS_DIR = STRENGTHENING_ROOT / "reports"

SRC = C2_DIR / "openai" / "openai_predictions.csv"
DEST = FREEZE_DIR / "openai_frozen.csv"
SUPERSEDED = FREEZE_DIR / "openai_frozen_SUPERSEDED_missing_confidence_column.csv"
MANIFEST_PATHS = [FREEZE_DIR / "PREDICTION_FREEZE_MANIFEST.json", REPORTS_DIR / "C2_PREDICTION_FREEZE_MANIFEST.json"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_rows(csv_path: Path) -> int:
    with open(csv_path, encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def run() -> dict:
    if not DEST.exists():
        raise FileNotFoundError(f"Expected an existing frozen openai snapshot at {DEST} to supersede.")
    if SUPERSEDED.exists():
        raise FileExistsError(f"Refusing to overwrite an existing superseded-snapshot record: {SUPERSEDED}")

    old_sha256 = _sha256(DEST)
    shutil.move(str(DEST), str(SUPERSEDED))
    shutil.copy2(SRC, DEST)
    new_sha256 = _sha256(DEST)
    new_rows = _count_rows(DEST)
    refrozen_at = datetime.now(timezone.utc).isoformat()

    for manifest_path in MANIFEST_PATHS:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        for entry in manifest["entries"]:
            if entry["method"] == "openai":
                entry["sha256_superseded"] = old_sha256
                entry["superseded_reason"] = (
                    "Original freeze copied a predictions CSV missing the guard_confidence column "
                    "due to a bug in run_openai_real.py's _validate_and_summarise (the column was "
                    "already correctly recorded in the raw JSONL log for all 900 real responses). "
                    "Fixed additively; guard_decision and error columns verified byte-identical "
                    "across all 900 rows before refreeze. Zero new API calls were made."
                )
                entry["sha256"] = new_sha256
                entry["rows"] = new_rows
                entry["frozen_at_utc"] = refrozen_at
                entry["refrozen_at_utc"] = refrozen_at
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, default=str)

    return {
        "old_sha256": old_sha256,
        "new_sha256": new_sha256,
        "rows": new_rows,
        "superseded_file": str(SUPERSEDED),
        "refrozen_at_utc": refrozen_at,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
