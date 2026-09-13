"""C2 Task 9: freeze all paid prediction outputs (immutable snapshots +
SHA-256 hashes) BEFORE any performance analysis touches them. Also
freezes the B1-B5 (free, local) predictions from C1B for a complete,
single evaluation-ready snapshot set.
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

SOURCES = {
    "primary_m7": C2_DIR / "primary_m7" / "primary_m7_predictions.csv",
    "b6": C2_DIR / "b6" / "b6_predictions.csv",
    "b7": C2_DIR / "b7" / "b7_predictions.csv",
    "b8": C2_DIR / "b8" / "b8_predictions.csv",
    "openai": C2_DIR / "openai" / "openai_predictions.csv",
    "b1_b5": STRENGTHENING_ROOT / "restricted_local" / "experiments" / "b1_b5_predictions" / "pooled900_b1_b5_predictions.csv",
}

SUMMARY_SOURCES = {
    "primary_m7": C2_DIR / "primary_m7" / "primary_m7_raw_outputs.jsonl",
    "b6": C2_DIR / "b6" / "b6_raw_outputs.jsonl",
    "b7": C2_DIR / "b7" / "b7_raw_outputs.jsonl",
    "openai": C2_DIR / "openai" / "openai_raw_outputs.jsonl",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_rows(csv_path: Path) -> int:
    with open(csv_path, encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # minus header


def _actuals_from_jsonl(jsonl_path: Path) -> dict:
    if not jsonl_path.exists():
        return {"n_requests_logged": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_attempts": 0, "n_errors": 0}
    n_requests, total_in, total_out, total_attempts, n_errors = 0, 0, 0, 0, 0
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n_requests += 1
            total_attempts += r.get("attempts") or 0
            if r.get("error"):
                n_errors += 1
            else:
                total_in += r.get("input_tokens") or 0
                total_out += r.get("output_tokens") or 0
    return {"n_requests_logged": n_requests, "total_input_tokens": total_in, "total_output_tokens": total_out, "total_attempts": total_attempts, "n_errors": n_errors}


def run() -> dict:
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    manifest_entries = []

    for method, src in SOURCES.items():
        if not src.exists():
            manifest_entries.append({"method": method, "status": "MISSING", "source_path": str(src)})
            continue
        dest = FREEZE_DIR / f"{method}_frozen.csv"
        if dest.exists():
            raise FileExistsError(f"Refusing to overwrite an already-frozen prediction snapshot: {dest}")
        shutil.copy2(src, dest)
        entry = {
            "method": method,
            "status": "FROZEN",
            "file": str(dest),
            "rows": _count_rows(dest),
            "sha256": _sha256(dest),
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        if method in SUMMARY_SOURCES:
            entry.update(_actuals_from_jsonl(SUMMARY_SOURCES[method]))
        manifest_entries.append(entry)

    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "entries": manifest_entries}
    with open(FREEZE_DIR / "PREDICTION_FREEZE_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    with open(REPORTS_DIR / "C2_PREDICTION_FREEZE_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    _write_markdown(manifest)
    return manifest


def _write_markdown(manifest: dict) -> None:
    lines = ["# C2 prediction-freeze manifest", "", "| Method | Status | Rows | SHA-256 | Requests | Input tok | Output tok | Attempts | Errors |", "|---|---|---:|---|---:|---:|---:|---:|---:|"]
    for e in manifest["entries"]:
        if e["status"] != "FROZEN":
            lines.append(f"| {e['method']} | {e['status']} | -- | -- | -- | -- | -- | -- | -- |")
            continue
        lines.append(
            f"| {e['method']} | FROZEN | {e['rows']} | `{e['sha256'][:16]}...` | "
            f"{e.get('n_requests_logged', '--')} | {e.get('total_input_tokens', '--')} | {e.get('total_output_tokens', '--')} | "
            f"{e.get('total_attempts', '--')} | {e.get('n_errors', '--')} |"
        )
    (REPORTS_DIR / "C2_PREDICTION_FREEZE_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
