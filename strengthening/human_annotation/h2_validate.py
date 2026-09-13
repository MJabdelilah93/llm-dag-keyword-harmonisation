"""H2 Step 1: independent validation of both completed primary workbooks
against the canonical 900-pair benchmark source (not against each other,
and not by re-trusting either annotator's own workbook). Fails loudly
(raises H2ValidationError) rather than silently repairing anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .common import ALLOWED_CONTEXT_USED, ALLOWED_LABELS, load_workbook_data_tabs

REQUIRED_COLS = ["pair_id", "domain", "string_a", "string_b", "label", "justification", "context_used"]
EXPECTED_TOTAL = 900
EXPECTED_CE = 400
EXPECTED_DIABETES = 500


class H2ValidationError(Exception):
    pass


@dataclass
class H2ValidationResult:
    annotator_label: str
    ok: bool
    row_count: int = 0
    ce_count: int = 0
    diabetes_count: int = 0
    missing_labels: int = 0
    invalid_labels: list = field(default_factory=list)
    invalid_context_used: list = field(default_factory=list)
    changed_strings: list = field(default_factory=list)
    duplicate_pair_ids: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def load_canonical_source(ce_source_csv: Path, bio_source_csv: Path) -> pd.DataFrame:
    ce = pd.read_csv(ce_source_csv, dtype=str)
    bio = pd.read_csv(bio_source_csv, dtype=str)
    canonical = pd.concat([ce[REQUIRED_COLS[:4]], bio[REQUIRED_COLS[:4]]], ignore_index=True)
    return canonical


def validate_completed(
    xlsx_path: Path,
    canonical: pd.DataFrame,
    annotator_label: str,
    expected_total: int = EXPECTED_TOTAL,
    expected_ce: int = EXPECTED_CE,
    expected_diabetes: int = EXPECTED_DIABETES,
) -> H2ValidationResult:
    if not xlsx_path.exists():
        raise H2ValidationError(f"{annotator_label}: completed workbook not found at {xlsx_path}")

    df = load_workbook_data_tabs(xlsx_path)
    result = H2ValidationResult(annotator_label=annotator_label, ok=True)

    missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        raise H2ValidationError(f"{annotator_label}: completed workbook missing required columns: {missing_cols}")

    # no system/model metadata introduced -- only the expected columns may be present
    forbidden_terms = ["stratum", "jaro", "tfidf", "tf_idf", "embedding", "frequency", "route", "rank",
                        "confidence", "gold", "guard", "claude", "openai", "anthropic", "model"]
    extra_cols = [c for c in df.columns if c not in REQUIRED_COLS and c != "_sheet"]
    leaked = [c for c in extra_cols if any(term in c.lower() for term in forbidden_terms)]
    if leaked:
        raise H2ValidationError(f"{annotator_label}: workbook exposes unexpected system/model metadata columns: {leaked}")

    result.row_count = len(df)
    if result.row_count != expected_total:
        result.ok = False
        result.issues.append(f"expected {expected_total} rows, found {result.row_count}")

    dup = df["pair_id"][df["pair_id"].duplicated()]
    if len(dup):
        result.duplicate_pair_ids = sorted(set(dup))
        result.ok = False
        result.issues.append(f"{len(dup)} duplicated pair_id rows")

    result.ce_count = int((df["domain"] == "circular_economy").sum())
    result.diabetes_count = int((df["domain"] == "biomedical_diabetes_mellitus").sum())
    if result.ce_count != expected_ce:
        result.ok = False
        result.issues.append(f"expected {expected_ce} circular_economy rows, found {result.ce_count}")
    if result.diabetes_count != expected_diabetes:
        result.ok = False
        result.issues.append(f"expected {expected_diabetes} biomedical_diabetes_mellitus rows, found {result.diabetes_count}")

    missing_pair_id = df["pair_id"].isna() | (df["pair_id"].astype(str).str.strip() == "")
    if missing_pair_id.any():
        result.ok = False
        result.issues.append(f"{int(missing_pair_id.sum())} rows have a missing/blank pair_id")

    missing_label_mask = df["label"].isna() | (df["label"].astype(str).str.strip() == "")
    result.missing_labels = int(missing_label_mask.sum())
    if result.missing_labels:
        result.ok = False
        result.issues.append(f"{result.missing_labels} pairs have no label (H1 not actually complete)")

    bad_label_mask = ~df["label"].isin(ALLOWED_LABELS) & ~missing_label_mask
    if bad_label_mask.any():
        result.invalid_labels = sorted(set(df.loc[bad_label_mask, "label"]))
        result.ok = False
        result.issues.append(f"invalid label values found: {result.invalid_labels}")

    bad_context_mask = ~df["context_used"].isin(ALLOWED_CONTEXT_USED) & df["context_used"].notna() & (df["context_used"].astype(str).str.strip() != "")
    if bad_context_mask.any():
        result.invalid_context_used = sorted(set(df.loc[bad_context_mask, "context_used"]))
        result.ok = False
        result.issues.append(f"invalid context_used values found: {result.invalid_context_used}")

    canonical_by_id = canonical.set_index("pair_id")
    # De-duplicate by pair_id (keep first) before indexing for the string-drift
    # check below: duplicate rows are already flagged above as their own issue,
    # and set_index().loc[] on a duplicated key returns a DataFrame rather than
    # a Series, which would make the tuple comparison below raise instead of
    # reporting a clean per-pair result.
    df_by_id = df.drop_duplicates(subset="pair_id", keep="first").set_index("pair_id")
    unknown_ids = set(df["pair_id"]) - set(canonical_by_id.index)
    if unknown_ids:
        result.ok = False
        result.issues.append(f"{len(unknown_ids)} pair_id values not present in the canonical 900-pair source: {sorted(unknown_ids)[:5]}")

    changed = []
    for pid in df_by_id.index:
        if pid not in canonical_by_id.index:
            continue
        row = df_by_id.loc[pid]
        canon = canonical_by_id.loc[pid]
        if (row["string_a"], row["string_b"], row["domain"]) != (canon["string_a"], canon["string_b"], canon["domain"]):
            changed.append(pid)
    if changed:
        result.changed_strings = changed
        result.ok = False
        result.issues.append(f"{len(changed)} pair_ids have a changed string_a/string_b/domain vs the canonical source")

    missing_from_completed = set(canonical_by_id.index) - set(df_by_id.index)
    if missing_from_completed:
        result.ok = False
        result.issues.append(f"{len(missing_from_completed)} canonical pair_ids missing from this completed workbook")

    return result


if __name__ == "__main__":
    raise SystemExit(
        "This module validates REAL completed annotator workbooks. Invoke it via the H2 driver script, not directly."
    )
