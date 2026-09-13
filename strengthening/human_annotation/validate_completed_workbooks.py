"""Validate a completed annotator workbook against its expected source.

Checks: allowed labels only (or blank), no missing rows, no changed
id/string values, no accidental duplicate rows.

DO NOT run against real annotator files until Phase H1/H3 is actually
complete -- see FINAL_HUMAN_ANNOTATION_PROTOCOL.md. Import and call
`validate()` from a driver script when that time comes.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import ALLOWED_CONTEXT_USED, ALLOWED_LABELS, load_workbook_data_tabs


def validate(completed_xlsx: Path, expected_source_csv: Path, id_col: str, string_cols: list[str]) -> dict:
    completed = load_workbook_data_tabs(completed_xlsx)
    expected = pd.read_csv(expected_source_csv, dtype=str)

    issues: list[str] = []

    completed_ids = set(completed[id_col].dropna())
    expected_ids = set(expected[id_col].dropna())
    missing = expected_ids - completed_ids
    extra = completed_ids - expected_ids
    if missing:
        issues.append(f"{len(missing)} expected {id_col} values missing from completed workbook: {sorted(missing)[:10]}...")
    if extra:
        issues.append(f"{len(extra)} unexpected {id_col} values found in completed workbook (renamed/added rows?): {sorted(extra)[:10]}...")

    dup = completed[id_col][completed[id_col].duplicated()]
    if len(dup):
        issues.append(f"{len(dup)} duplicate {id_col} rows found: {sorted(set(dup))[:10]}")

    exp_by_id = expected.set_index(id_col)
    for _, row in completed.iterrows():
        pid = row.get(id_col)
        if pid not in exp_by_id.index:
            continue
        for col in string_cols:
            if row.get(col) != exp_by_id.loc[pid, col]:
                issues.append(f"{id_col}={pid}: {col} changed (expected '{exp_by_id.loc[pid, col]}', got '{row.get(col)}')")

    bad_labels = completed[~completed["label"].isin(ALLOWED_LABELS | {None, "", float("nan")}) & completed["label"].notna() & (completed["label"] != "")]
    if len(bad_labels):
        issues.append(f"{len(bad_labels)} rows have a label outside {ALLOWED_LABELS}: {sorted(set(bad_labels['label']))[:10]}")

    bad_context = completed[~completed["context_used"].isin(ALLOWED_CONTEXT_USED) & completed["context_used"].notna() & (completed["context_used"] != "")]
    if len(bad_context):
        issues.append(f"{len(bad_context)} rows have context_used outside {ALLOWED_CONTEXT_USED}")

    n_complete = int(((completed["label"].notna()) & (completed["label"] != "")).sum())

    return {
        "rows_expected": len(expected),
        "rows_found": len(completed),
        "rows_with_a_label": n_complete,
        "valid": len(issues) == 0,
        "issues": issues,
    }


if __name__ == "__main__":
    raise SystemExit(
        "This script validates REAL completed annotator workbooks and must not be run until annotation is "
        "actually complete. Import validate() from a driver script instead. See "
        "strengthening/tests/test_human_annotation_automation.py for synthetic-data exercises."
    )
