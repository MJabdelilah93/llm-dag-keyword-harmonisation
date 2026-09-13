"""Diagnostic Step 10: recompute the full H2 agreement analysis after the
diabetes re-annotation is complete, replacing ONLY Annotator 2's diabetes
label set. Preserves: Annotator 1's original 900 labels unchanged,
Annotator 2's original circular-economy 400 labels unchanged, and the
original Annotator-2 diabetes annotations as provenance (never deleted,
referenced by source path in the output).

DO NOT RUN YET -- strengthening/restricted_local/human_annotation/v1/h2/
diabetes_reannotation/DIABETES_REANNOTATION_ANNOTATOR_2_COMPLETED.xlsx
does not exist until Annotator 2 actually completes the re-annotation.
Exercised with synthetic data only in
strengthening/tests/test_diabetes_reannotation_diagnostic.py.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import load_workbook_data_tabs
from .h2_agreement import agreement_summary, context_use_crosstab, disagreement_types

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1"
REANNOTATION_DIR = PKG_DIR / "h2" / "diabetes_reannotation"

ANN1_COMPLETED = PKG_DIR / "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx"
ANN2_COMPLETED_ORIGINAL = PKG_DIR / "ANNOTATOR_2_PRIMARY_COMPLETED.xlsx"
DIABETES_REANNOTATION_COMPLETED = REANNOTATION_DIR / "DIABETES_REANNOTATION_ANNOTATOR_2_COMPLETED.xlsx"


def build_effective_annotator_2(ann2_original: pd.DataFrame, diabetes_reannotation: pd.DataFrame, expected_total: int = 900) -> pd.DataFrame:
    """Returns Annotator 2's EFFECTIVE label set for the recomputed
    analysis: original CE rows unchanged, diabetes rows replaced by the
    re-annotation. The original diabetes rows are kept in a separate
    provenance column, never discarded."""
    ce = ann2_original[ann2_original["domain"] == "circular_economy"].copy()
    diabetes_original = ann2_original[ann2_original["domain"] == "biomedical_diabetes_mellitus"].copy()

    diabetes_new = diabetes_reannotation.rename(
        columns={"label": "label", "justification": "justification", "context_used": "context_used"}
    ).copy()
    # attach original diabetes label/justification/context_used as provenance columns
    orig_by_id = diabetes_original.set_index("pair_id")
    diabetes_new["original_a2_diabetes_label"] = diabetes_new["pair_id"].map(orig_by_id["label"])
    diabetes_new["original_a2_diabetes_justification"] = diabetes_new["pair_id"].map(orig_by_id["justification"])
    diabetes_new["original_a2_diabetes_context_used"] = diabetes_new["pair_id"].map(orig_by_id["context_used"])

    ce["original_a2_diabetes_label"] = ""
    ce["original_a2_diabetes_justification"] = ""
    ce["original_a2_diabetes_context_used"] = ""

    cols = ["pair_id", "domain", "string_a", "string_b", "label", "justification", "context_used",
            "original_a2_diabetes_label", "original_a2_diabetes_justification", "original_a2_diabetes_context_used"]
    combined = pd.concat([ce[cols], diabetes_new[cols]], ignore_index=True)
    if len(combined) != expected_total or combined["pair_id"].nunique() != expected_total:
        raise ValueError(
            f"effective Annotator 2 set must have exactly {expected_total} unique pair_ids, "
            f"got {len(combined)} rows / {combined['pair_id'].nunique()} unique"
        )
    return combined


def recompute(ann1_completed: Path, ann2_completed_original: Path, diabetes_reannotation_completed: Path) -> dict:
    if not diabetes_reannotation_completed.exists():
        raise FileNotFoundError(
            f"{diabetes_reannotation_completed} does not exist -- diabetes re-annotation is not complete yet"
        )

    ann1 = load_workbook_data_tabs(ann1_completed)
    ann2_original = load_workbook_data_tabs(ann2_completed_original)
    diabetes_reannotation = load_workbook_data_tabs(diabetes_reannotation_completed)

    ann2_effective = build_effective_annotator_2(ann2_original, diabetes_reannotation)

    merged = ann1.merge(
        ann2_effective, on="pair_id", suffixes=("_1", "_2"), how="inner", validate="one_to_one"
    )
    if len(merged) != 900:
        raise ValueError(f"expected 900 merged pairs, got {len(merged)}")

    merged = merged.rename(columns={
        "domain_1": "domain", "string_a_1": "string_a", "string_b_1": "string_b",
        "label_1": "annotator_1_label", "justification_1": "annotator_1_justification", "context_used_1": "annotator_1_context_used",
        "label_2": "annotator_2_label", "justification_2": "annotator_2_justification", "context_used_2": "annotator_2_context_used",
    })
    merged["agree"] = merged["annotator_1_label"] == merged["annotator_2_label"]

    ce = merged[merged["domain"] == "circular_economy"]
    bio = merged[merged["domain"] == "biomedical_diabetes_mellitus"]

    return {
        "overall": agreement_summary(merged),
        "circular_economy": agreement_summary(ce),
        "biomedical_diabetes_mellitus": agreement_summary(bio),
        "disagreement_types_overall": disagreement_types(merged),
        "context_use_crosstab_overall": context_use_crosstab(merged),
        "provenance_note": (
            "Annotator 2's circular-economy labels are UNCHANGED from the original H1 completion. "
            "Annotator 2's diabetes labels come from the re-annotation; the original (degenerate) "
            "diabetes labels are preserved per-row in original_a2_diabetes_label for provenance, "
            f"never deleted, sourced from {ann2_completed_original}."
        ),
    }, merged


if __name__ == "__main__":
    raise SystemExit(
        "NOT TO BE RUN YET. Requires DIABETES_REANNOTATION_ANNOTATOR_2_COMPLETED.xlsx to actually exist. "
        "See strengthening/tests/test_diabetes_reannotation_diagnostic.py for synthetic-data exercises."
    )
