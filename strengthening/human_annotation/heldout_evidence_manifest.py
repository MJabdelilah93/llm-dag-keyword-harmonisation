"""Gold-freeze Step 14: safe held-out evidence manifest. Lists the three
individually-identifiable held-out datasets (never merged into one pooled
metric) plus the legacy development set (tuning-only, kept strictly
separate and never counted toward held-out totals). No model evaluation is
run here -- counts only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = STRENGTHENING_ROOT / "reports" / "HELDOUT_EVIDENCE_MANIFEST.json"
OUT_MD = STRENGTHENING_ROOT / "reports" / "HELDOUT_EVIDENCE_MANIFEST.md"

HELD_OUT_DATASETS = {
    "legacy_ce_test": {"n": 149, "role": "held_out", "note": "Legacy circular-economy test split -- read-only reference material, never altered."},
    "prospective_ce": {"n": 400, "role": "held_out", "note": "New prospective circular-economy benchmark (this project); guaranteed non-overlapping with the legacy 351/149 split."},
    "open_diabetes": {"n": 500, "role": "held_out", "note": "New prospective open (CC BY/CC0) biomedical diabetes-mellitus benchmark."},
}
DEVELOPMENT_SET = {"legacy_ce_development": {"n": 351, "role": "development_tuning_only", "note": "Legacy circular-economy development split -- tuning only, NEVER merged into held-out metrics."}}


def run() -> dict:
    total_held_out = sum(d["n"] for d in HELD_OUT_DATASETS.values())
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "held_out_datasets": HELD_OUT_DATASETS,
        "total_held_out": total_held_out,
        "development_set": DEVELOPMENT_SET,
        "development_kept_separate_from_held_out": True,
        "model_evaluation_run": False,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    _write_markdown(report)
    return report


def _write_markdown(report: dict) -> None:
    lines = [
        "# Held-out evidence manifest",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "Three individually-identifiable held-out datasets (never pooled into one merged metric):",
        "",
    ]
    for name, d in report["held_out_datasets"].items():
        lines.append(f"- {name}: N={d['n']} -- {d['note']}")
    lines += [
        "",
        f"**Total held-out N = {report['total_held_out']}**",
        "",
        "## Development set (kept separate)",
        "",
    ]
    for name, d in report["development_set"].items():
        lines.append(f"- {name}: N={d['n']} -- {d['note']}")
    lines += [
        "",
        f"Development set kept separate from held-out totals: {report['development_kept_separate_from_held_out']}",
        f"Model evaluation run in this task: {report['model_evaluation_run']}",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
