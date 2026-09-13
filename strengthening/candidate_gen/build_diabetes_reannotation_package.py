"""Diagnostic Step 5: build a fresh, blank-label diabetes-only
re-annotation package for Annotator 2. Same 500 canonical diabetes
pair_ids/strings, a NEW deterministic row-order seed (never used for any
prior ordering), no reference anywhere to the original Annotator 2
diabetes labels, Annotator 1 labels, or any model/system information.
Never touches or overwrites the original H1 completed files.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
BIO_SOURCE = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "h2" / "diabetes_reannotation"
OUT_XLSX = OUT_DIR / "DIABETES_REANNOTATION_ANNOTATOR_2.xlsx"

# 42 = Annotator 1 primary row order, 43 = Annotator 2 primary row order.
# This MUST be a new seed never used for any prior ordering decision.
REANNOTATION_ORDER_SEED = 44

COLS = ["pair_id", "domain", "string_a", "string_b", "label", "justification", "context_used"]


def build() -> pd.DataFrame:
    bio = pd.read_csv(BIO_SOURCE, dtype=str)
    assert len(bio) == 500, f"expected 500 canonical diabetes pairs, found {len(bio)}"
    assert bio["pair_id"].nunique() == 500

    view = bio[["pair_id", "domain", "string_a", "string_b"]].copy()
    view["label"] = ""
    view["justification"] = ""
    view["context_used"] = ""

    idx = list(view.index)
    random.Random(REANNOTATION_ORDER_SEED).shuffle(idx)
    shuffled = view.loc[idx].reset_index(drop=True)
    shuffled.insert(0, "row_number", range(1, len(shuffled) + 1))
    return shuffled


def write(df: pd.DataFrame, out_path: Path = OUT_XLSX) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Diabetes_500_Reannotation")
    ws.append(["row_number"] + COLS)
    for _, row in df.iterrows():
        ws.append([row["row_number"]] + [row[c] for c in COLS])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


def main():
    df = build()
    out = write(df)
    print(f"Wrote {out} ({len(df)} rows, order seed={REANNOTATION_ORDER_SEED})")
    print("Same 500 pair_ids as canonical:", set(df["pair_id"]) == set(pd.read_csv(BIO_SOURCE, dtype=str)["pair_id"]))
    print("All labels blank:", (df["label"] == "").all())


if __name__ == "__main__":
    main()
