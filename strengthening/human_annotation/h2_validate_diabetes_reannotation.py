"""H2-corrected Step 2: independent validation of the COMPLETED diabetes-only
re-annotation workbook against the canonical 500-pair diabetes benchmark
source (never against the original/superseded Annotator-2 diabetes labels,
and never against Annotator 1's labels). Fails loudly rather than silently
repairing anything -- the corrected H2 recompute must not run if this
validation fails.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .common import ALLOWED_CONTEXT_USED, ALLOWED_LABELS, load_workbook_data_tabs

REQUIRED_COLS = ["pair_id", "domain", "string_a", "string_b", "label", "justification", "context_used"]
EXPECTED_ROWS = 500
EXPECTED_DOMAIN = "biomedical_diabetes_mellitus"

# columns that must NEVER appear in the re-annotation output: any reference
# to the prior (superseded) A2 diabetes labels, Annotator 1's labels, or
# system/model metadata would mean independence was violated.
FORBIDDEN_COLUMN_TERMS = [
    "annotator_1", "original_a2", "stratum", "jaro", "tfidf", "tf_idf",
    "embedding", "frequency", "route", "rank", "confidence", "gold", "guard",
    "claude", "openai", "anthropic", "model",
]


class ReannotationValidationError(Exception):
    pass


@dataclass
class ReannotationValidationResult:
    ok: bool
    row_count: int = 0
    missing_labels: int = 0
    invalid_labels: list = field(default_factory=list)
    invalid_context_used: list = field(default_factory=list)
    changed_strings: list = field(default_factory=list)
    duplicate_pair_ids: list = field(default_factory=list)
    non_diabetes_rows: int = 0
    unknown_pair_ids: list = field(default_factory=list)
    missing_from_completed: list = field(default_factory=list)
    forbidden_columns: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def validate_diabetes_reannotation(
    xlsx_path: Path,
    canonical_bio: pd.DataFrame,
    expected_rows: int = EXPECTED_ROWS,
) -> ReannotationValidationResult:
    if not xlsx_path.exists():
        raise ReannotationValidationError(f"Diabetes re-annotation completed workbook not found at {xlsx_path}")

    df = load_workbook_data_tabs(xlsx_path)
    # the shared workbook layout always includes an (empty) CE tab -- only
    # the diabetes rows are in scope for this validator.
    df = df[df["domain"] == EXPECTED_DOMAIN].reset_index(drop=True) if "domain" in df.columns else df

    result = ReannotationValidationResult(ok=True)

    missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        raise ReannotationValidationError(f"Re-annotation workbook missing required columns: {missing_cols}")

    extra_cols = [c for c in df.columns if c not in REQUIRED_COLS and c != "_sheet"]
    forbidden = [c for c in extra_cols if any(term in c.lower() for term in FORBIDDEN_COLUMN_TERMS)]
    if forbidden:
        result.forbidden_columns = forbidden
        result.ok = False
        result.issues.append(f"workbook exposes forbidden columns (prior labels or system metadata): {forbidden}")

    result.row_count = len(df)
    if result.row_count != expected_rows:
        result.ok = False
        result.issues.append(f"expected {expected_rows} diabetes rows, found {result.row_count}")

    non_diabetes = df["domain"] != EXPECTED_DOMAIN
    result.non_diabetes_rows = int(non_diabetes.sum())
    if result.non_diabetes_rows:
        result.ok = False
        result.issues.append(f"{result.non_diabetes_rows} rows are not domain={EXPECTED_DOMAIN}")

    dup = df["pair_id"][df["pair_id"].duplicated()]
    if len(dup):
        result.duplicate_pair_ids = sorted(set(dup))
        result.ok = False
        result.issues.append(f"{len(dup)} duplicated pair_id rows")

    missing_pair_id = df["pair_id"].isna() | (df["pair_id"].astype(str).str.strip() == "")
    if missing_pair_id.any():
        result.ok = False
        result.issues.append(f"{int(missing_pair_id.sum())} rows have a missing/blank pair_id")

    missing_label_mask = df["label"].isna() | (df["label"].astype(str).str.strip() == "")
    result.missing_labels = int(missing_label_mask.sum())
    if result.missing_labels:
        result.ok = False
        result.issues.append(f"{result.missing_labels} pairs have no label (re-annotation not actually complete)")

    bad_label_mask = ~df["label"].isin(ALLOWED_LABELS) & ~missing_label_mask
    if bad_label_mask.any():
        result.invalid_labels = sorted(set(df.loc[bad_label_mask, "label"]))
        result.ok = False
        result.issues.append(f"invalid label values found: {result.invalid_labels}")

    bad_context_mask = ~df["context_used"].isin(ALLOWED_CONTEXT_USED)
    if bad_context_mask.any():
        result.invalid_context_used = sorted(set(df.loc[bad_context_mask, "context_used"].astype(str)))
        result.ok = False
        result.issues.append(f"invalid/blank context_used values found: {result.invalid_context_used}")

    canonical_by_id = canonical_bio.set_index("pair_id")
    df_by_id = df.drop_duplicates(subset="pair_id", keep="first").set_index("pair_id")

    unknown_ids = set(df["pair_id"]) - set(canonical_by_id.index)
    if unknown_ids:
        result.unknown_pair_ids = sorted(unknown_ids)[:5]
        result.ok = False
        result.issues.append(f"{len(unknown_ids)} pair_id values not present in the canonical diabetes benchmark")

    changed = []
    for pid in df_by_id.index:
        if pid not in canonical_by_id.index:
            continue
        row = df_by_id.loc[pid]
        canon = canonical_by_id.loc[pid]
        if (row["string_a"], row["string_b"]) != (canon["string_a"], canon["string_b"]):
            changed.append(pid)
    if changed:
        result.changed_strings = changed
        result.ok = False
        result.issues.append(f"{len(changed)} pair_ids have a changed string_a/string_b vs the canonical source")

    missing_from_completed = set(canonical_by_id.index) - set(df_by_id.index)
    if missing_from_completed:
        result.missing_from_completed = sorted(missing_from_completed)[:5]
        result.ok = False
        result.issues.append(f"{len(missing_from_completed)} canonical diabetes pair_ids missing from this workbook")

    return result


if __name__ == "__main__":
    raise SystemExit(
        "This module validates the REAL completed diabetes re-annotation workbook. Invoke it via the corrected H2 driver, not directly."
    )
