"""From merged primary annotations, build a disagreement-only adjudication
file (blank adjudicated_label/adjudicator_notes). Never overwrites the
original completed annotator files or the merged file itself -- writes a
new file alongside them.

DO NOT run against real annotator files until Phase H1/merge is complete.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def build(merged: pd.DataFrame) -> pd.DataFrame:
    disagreements = merged[~merged["agree"]].copy()
    disagreements["adjudicated_label"] = ""
    disagreements["adjudicator_notes"] = ""
    cols = [
        "pair_id", "domain", "string_a", "string_b",
        "annotator_1_label", "annotator_1_justification",
        "annotator_2_label", "annotator_2_justification",
        "adjudicated_label", "adjudicator_notes",
    ]
    return disagreements[cols].reset_index(drop=True)


def write(merged: pd.DataFrame, out_path: Path) -> Path:
    if out_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing adjudication package: {out_path}")
    pkg = build(merged)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pkg.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    raise SystemExit(
        "This script builds an adjudication package from REAL merged annotations and must not be run until "
        "Phase H1 merge is complete. Import build()/write() from a driver script instead."
    )
