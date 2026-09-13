"""Merge Annotator 1 (all Scenario-E rows) + Annotator 2 (outside-pool +
30%/40% audit sample) completed RETRIEVAL workbooks by retrieval_pair_id.
Unlike the primary merge, Annotator 2's id set is a SUBSET of Annotator
1's -- rows Annotator 2 never saw are kept as singly-coded (annotator_2_*
columns left null), not dropped.

DO NOT run against real annotator files until Phase H3 is complete.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import load_workbook_data_tabs


def merge(ann1_xlsx: Path, ann2_xlsx: Path) -> pd.DataFrame:
    a1 = load_workbook_data_tabs(ann1_xlsx)
    a2 = load_workbook_data_tabs(ann2_xlsx)

    if not set(a2["retrieval_pair_id"]).issubset(set(a1["retrieval_pair_id"])):
        extra = set(a2["retrieval_pair_id"]) - set(a1["retrieval_pair_id"])
        raise ValueError(f"Annotator 2 has {len(extra)} retrieval_pair_id values not present in Annotator 1's set: {sorted(extra)[:5]}")

    a1r = a1.rename(columns={"label": "annotator_1_label", "justification": "annotator_1_justification", "context_used": "annotator_1_context_used"})
    a2r = a2.rename(columns={"label": "annotator_2_label", "justification": "annotator_2_justification", "context_used": "annotator_2_context_used"})

    merged = a1r[["retrieval_pair_id", "domain", "seed_string", "candidate_string", "annotator_1_label", "annotator_1_justification", "annotator_1_context_used"]].merge(
        a2r[["retrieval_pair_id", "annotator_2_label", "annotator_2_justification", "annotator_2_context_used"]],
        on="retrieval_pair_id",
        how="left",
        validate="one_to_one",
    )
    merged["double_coded"] = merged["annotator_2_label"].notna() & (merged["annotator_2_label"] != "")
    merged["agree"] = merged["double_coded"] & (merged["annotator_1_label"] == merged["annotator_2_label"])
    return merged.sort_values("retrieval_pair_id").reset_index(drop=True)


if __name__ == "__main__":
    raise SystemExit(
        "This script merges REAL completed annotator workbooks and must not be run until Phase H3 is complete. "
        "Import merge() from a driver script instead."
    )
