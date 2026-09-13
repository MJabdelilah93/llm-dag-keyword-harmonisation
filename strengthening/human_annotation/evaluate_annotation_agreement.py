"""Compute raw agreement and Cohen's kappa (three-way: match/non-match/
uncertain) on a merged primary- or retrieval-annotation dataframe,
restricted to double-coded rows.

DO NOT run against real annotator files until the relevant merge step is
complete.
"""
from __future__ import annotations

import pandas as pd

from .common import ALLOWED_LABELS, cohens_kappa, raw_agreement


def evaluate(merged: pd.DataFrame, double_coded_mask: pd.Series | None = None) -> dict:
    df = merged if double_coded_mask is None else merged[double_coded_mask]
    a1 = df["annotator_1_label"].tolist()
    a2 = df["annotator_2_label"].tolist()
    classes = sorted(ALLOWED_LABELS)
    return {
        "n_double_coded": len(df),
        "raw_agreement": raw_agreement(a1, a2),
        "cohens_kappa": cohens_kappa(a1, a2, classes=classes),
        "label_distribution_annotator_1": pd.Series(a1).value_counts().to_dict() if a1 else {},
        "label_distribution_annotator_2": pd.Series(a2).value_counts().to_dict() if a2 else {},
        "n_disagreements": int((df["annotator_1_label"] != df["annotator_2_label"]).sum()),
    }


if __name__ == "__main__":
    raise SystemExit(
        "This script evaluates agreement on REAL merged annotations and must not be run until the relevant "
        "merge step is complete. Import evaluate() from a driver script instead."
    )
