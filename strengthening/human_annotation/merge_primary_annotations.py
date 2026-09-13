"""Merge Annotator 1 + Annotator 2 completed PRIMARY workbooks by
pair_id (aligning independently-randomised row orders), producing one
dataframe with both annotators' label/justification/context_used
side by side. Never overwrites the original completed files.

DO NOT run against real annotator files until Phase H1 is complete.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import load_workbook_data_tabs


def merge(ann1_xlsx: Path, ann2_xlsx: Path) -> pd.DataFrame:
    a1 = load_workbook_data_tabs(ann1_xlsx)
    a2 = load_workbook_data_tabs(ann2_xlsx)

    a1_ids, a2_ids = set(a1["pair_id"]), set(a2["pair_id"])
    if a1_ids != a2_ids:
        raise ValueError(
            f"Annotator pair_id sets differ (missing from ann2: {sorted(a1_ids - a2_ids)[:5]}, "
            f"missing from ann1: {sorted(a2_ids - a1_ids)[:5]}) -- run validate_completed_workbooks first"
        )

    a1r = a1.rename(columns={"label": "annotator_1_label", "justification": "annotator_1_justification", "context_used": "annotator_1_context_used"})
    a2r = a2.rename(columns={"label": "annotator_2_label", "justification": "annotator_2_justification", "context_used": "annotator_2_context_used"})

    merged = a1r[["pair_id", "domain", "string_a", "string_b", "annotator_1_label", "annotator_1_justification", "annotator_1_context_used"]].merge(
        a2r[["pair_id", "annotator_2_label", "annotator_2_justification", "annotator_2_context_used"]],
        on="pair_id",
        how="inner",
        validate="one_to_one",
    )
    merged["agree"] = merged["annotator_1_label"] == merged["annotator_2_label"]
    return merged.sort_values("pair_id").reset_index(drop=True)


if __name__ == "__main__":
    raise SystemExit(
        "This script merges REAL completed annotator workbooks and must not be run until Phase H1 is complete. "
        "Import merge() from a driver script instead."
    )
