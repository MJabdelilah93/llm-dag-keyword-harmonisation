"""H2 Steps 2+3: align both completed primary workbooks by pair_id (never
by row position -- each annotator's workbook has an independently
randomised row order) and compute inter-annotator agreement statistics.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import ALLOWED_LABELS, cohens_kappa, raw_agreement
from .merge_primary_annotations import merge as merge_primary

LABEL_ORDER = ["match", "non-match", "uncertain"]


def confusion_matrix(df: pd.DataFrame) -> dict:
    """3x3 confusion matrix: rows = annotator_1_label, cols = annotator_2_label."""
    matrix = {a: {b: 0 for b in LABEL_ORDER} for a in LABEL_ORDER}
    for a, b in zip(df["annotator_1_label"], df["annotator_2_label"]):
        matrix[a][b] += 1
    return matrix


def disagreement_types(df: pd.DataFrame) -> dict:
    disagreements = df[~df["agree"]]
    unordered_counts: dict[str, int] = {}
    directional_counts: dict[str, int] = {}
    other = 0
    for a, b in zip(disagreements["annotator_1_label"], disagreements["annotator_2_label"]):
        pair = tuple(sorted((a, b)))
        if set(pair).issubset(set(LABEL_ORDER)) and len(set(pair)) == 2:
            key = f"{pair[0]} vs {pair[1]}"
            unordered_counts[key] = unordered_counts.get(key, 0) + 1
        else:
            other += 1
        dkey = f"annotator_1={a} / annotator_2={b}"
        directional_counts[dkey] = directional_counts.get(dkey, 0) + 1
    return {"unordered": unordered_counts, "directional": directional_counts, "other": other}


def context_use_crosstab(df: pd.DataFrame) -> dict:
    a1 = df["annotator_1_context_used"] == "yes"
    a2 = df["annotator_2_context_used"] == "yes"
    patterns = {
        "neither": (~a1) & (~a2),
        "annotator_1_only": a1 & (~a2),
        "annotator_2_only": (~a1) & a2,
        "both": a1 & a2,
    }
    out = {}
    for name, mask in patterns.items():
        n = int(mask.sum())
        n_disagree = int((~df.loc[mask, "agree"]).sum()) if n else 0
        out[name] = {
            "n": n,
            "proportion_of_total": round(n / len(df), 4) if len(df) else None,
            "disagreement_count": n_disagree,
            "disagreement_rate": round(n_disagree / n, 4) if n else None,
        }
    return out


def agreement_summary(df: pd.DataFrame) -> dict:
    n = len(df)
    agreements = int(df["agree"].sum())
    disagreements = n - agreements
    a1_labels = df["annotator_1_label"].tolist()
    a2_labels = df["annotator_2_label"].tolist()
    return {
        "n": n,
        "agreements": agreements,
        "disagreements": disagreements,
        "raw_agreement_proportion": round(raw_agreement(a1_labels, a2_labels), 4) if n else None,
        "cohens_kappa": round(cohens_kappa(a1_labels, a2_labels, classes=LABEL_ORDER), 4) if n else None,
        "kappa_terminology_note": "reported as inter-annotator agreement (Cohen's kappa), not 'reliability'",
        "annotator_1_label_distribution": df["annotator_1_label"].value_counts().to_dict(),
        "annotator_2_label_distribution": df["annotator_2_label"].value_counts().to_dict(),
        "confusion_matrix_rows_annotator_1_cols_annotator_2": confusion_matrix(df),
    }


def build_full_report(ann1_completed: Path, ann2_completed: Path) -> dict:
    merged = merge_primary(ann1_completed, ann2_completed)
    assert set(merged["annotator_1_label"]) <= set(ALLOWED_LABELS)
    assert set(merged["annotator_2_label"]) <= set(ALLOWED_LABELS)

    ce = merged[merged["domain"] == "circular_economy"]
    bio = merged[merged["domain"] == "biomedical_diabetes_mellitus"]

    report = {
        "overall": agreement_summary(merged),
        "circular_economy": agreement_summary(ce),
        "biomedical_diabetes_mellitus": agreement_summary(bio),
        "disagreement_types_overall": disagreement_types(merged),
        "context_use_crosstab_overall": context_use_crosstab(merged),
        "historical_context_only_not_a_comparison": {
            "legacy_pilot_full_round_cohens_kappa": 0.8075,
            "note": (
                "This is the ORIGINAL legacy benchmark's full-round Cohen's kappa, included here purely as "
                "historical background. It is NOT a statistical comparison against the new 900-pair benchmark's "
                "agreement figures above -- different annotators, different pairs, different domains."
            ),
        },
    }
    return report, merged
