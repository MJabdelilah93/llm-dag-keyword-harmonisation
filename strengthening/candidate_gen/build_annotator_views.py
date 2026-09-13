"""Build the annotator-visible extracts (primary benchmark + retrieval
audit) with ONLY the allowed columns, blank label/justification/
context_used, and independently randomised row order per annotator.
Never exposes stratum/scores/routes/ranks/frequencies/audit-category.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "_intermediate"

ANN1_SEED = 42
ANN2_SEED = 43

PRIMARY_COLS = ["pair_id", "domain", "string_a", "string_b", "label", "justification", "context_used"]
RETRIEVAL_COLS = ["retrieval_pair_id", "domain", "seed_string", "candidate_string", "label", "justification", "context_used"]


def shuffled(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    idx = list(df.index)
    random.Random(seed).shuffle(idx)
    return df.loc[idx].reset_index(drop=True)


def build_primary() -> tuple[pd.DataFrame, pd.DataFrame]:
    ce = pd.read_csv(STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv")
    bio = pd.read_csv(STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv")
    combined = pd.concat([ce, bio], ignore_index=True)
    combined["label"] = ""
    combined["justification"] = ""
    combined["context_used"] = ""
    view = combined[PRIMARY_COLS].copy()

    ann1 = shuffled(view, ANN1_SEED)
    ann2 = shuffled(view, ANN2_SEED)
    ann1.insert(0, "row_number", range(1, len(ann1) + 1))
    ann2.insert(0, "row_number", range(1, len(ann2) + 1))
    return ann1, ann2


def build_retrieval() -> tuple[pd.DataFrame, pd.DataFrame]:
    ce = pd.read_csv(OUT_DIR / "scenario_e_ce_master.csv")
    bio = pd.read_csv(OUT_DIR / "scenario_e_bio_master.csv")
    combined = pd.concat([ce, bio], ignore_index=True)

    combined["label"] = ""
    combined["justification"] = ""
    combined["context_used"] = ""

    ann1_full = combined[RETRIEVAL_COLS].copy()
    ann2_mask = combined["outside_pool_sample"] | combined["audit_sample_selected"]
    ann2_full = combined.loc[ann2_mask, RETRIEVAL_COLS].copy()

    ann1 = shuffled(ann1_full, ANN1_SEED)
    ann2 = shuffled(ann2_full, ANN2_SEED)
    ann1.insert(0, "row_number", range(1, len(ann1) + 1))
    ann2.insert(0, "row_number", range(1, len(ann2) + 1))
    return ann1, ann2


def main():
    p1, p2 = build_primary()
    assert set(p1["pair_id"]) == set(p2["pair_id"]), "Annotator 1/2 primary pair_id sets differ"
    assert len(p1) == 900 and len(p2) == 900
    p1.to_csv(OUT_DIR / "primary_annotator_1.csv", index=False, encoding="utf-8")
    p2.to_csv(OUT_DIR / "primary_annotator_2.csv", index=False, encoding="utf-8")
    order_differs = list(p1["pair_id"]) != list(p2["pair_id"])
    print(f"Primary: {len(p1)} rows each, CE={int((p1['domain']=='circular_economy').sum())}, "
          f"bio={int((p1['domain']=='biomedical_diabetes_mellitus').sum())}, order_differs={order_differs}")

    r1, r2 = build_retrieval()
    r1.to_csv(OUT_DIR / "retrieval_annotator_1.csv", index=False, encoding="utf-8")
    r2.to_csv(OUT_DIR / "retrieval_annotator_2.csv", index=False, encoding="utf-8")
    assert set(r2["retrieval_pair_id"]).issubset(set(r1["retrieval_pair_id"]))
    print(f"Retrieval: annotator_1={len(r1)} rows, annotator_2={len(r2)} rows "
          f"(annotator_2 subset of annotator_1: {set(r2['retrieval_pair_id']).issubset(set(r1['retrieval_pair_id']))})")


if __name__ == "__main__":
    main()
