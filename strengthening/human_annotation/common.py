"""Shared helpers for post-annotation automation."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ALLOWED_LABELS = {"match", "non-match", "uncertain"}
ALLOWED_CONTEXT_USED = {"yes", "no"}


def load_workbook_data_tabs(xlsx_path: Path) -> pd.DataFrame:
    """Reads every non-Instructions tab of a completed workbook and
    concatenates them into one dataframe (adds a `_sheet` column)."""
    sheets = pd.read_excel(xlsx_path, sheet_name=None, dtype=str)
    frames = []
    for name, df in sheets.items():
        if name == "Instructions":
            continue
        df = df.copy()
        df["_sheet"] = name
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def cohens_kappa(labels_a: list[str], labels_b: list[str], classes: list[str] | None = None) -> float:
    """Standard Cohen's kappa for two raters over a fixed label set."""
    if classes is None:
        classes = sorted(set(labels_a) | set(labels_b))
    n = len(labels_a)
    if n == 0:
        return float("nan")
    idx = {c: i for i, c in enumerate(classes)}
    k = len(classes)
    confusion = [[0] * k for _ in range(k)]
    for a, b in zip(labels_a, labels_b):
        confusion[idx[a]][idx[b]] += 1
    po = sum(confusion[i][i] for i in range(k)) / n
    row_marg = [sum(confusion[i]) / n for i in range(k)]
    col_marg = [sum(confusion[i][j] for i in range(k)) / n for j in range(k)]
    pe = sum(row_marg[i] * col_marg[i] for i in range(k))
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def raw_agreement(labels_a: list[str], labels_b: list[str]) -> float:
    if not labels_a:
        return float("nan")
    return sum(1 for a, b in zip(labels_a, labels_b) if a == b) / len(labels_a)
