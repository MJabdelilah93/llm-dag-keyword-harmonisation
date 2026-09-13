"""H2-corrected Step 9: build the disagreement-only
PRIMARY_ADJUDICATION_CORRECTED.xlsx from the CORRECTED merged H2 data
(Annotator 1's original 900 labels vs the corrected Annotator-2 composite:
original CE 400 + re-annotated diabetes 500).

CRITICAL BLINDING IMPROVEMENT over the original package: the previous H1
adjudication report accidentally disclosed the fixed, whole-package A/B
mapping. This package therefore anonymises annotator identity
INDEPENDENTLY PER DISAGREEMENT ROW -- a hidden, seeded random draw decides
the A/B orientation separately for every row, so no global position can be
used to infer which real annotator made which decision. The seed and the
full per-row mapping are recorded ONLY in a private, restricted provenance
file -- never in the adjudicator-facing package, never in any tracked
report, never shown by the GUI.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

ADJUDICATION_COLUMNS = [
    "adjudication_row", "pair_id", "domain", "string_a", "string_b",
    "decision_A", "decision_B", "justification_A", "justification_B",
    "context_used_A", "context_used_B",
    "adjudicated_label", "adjudicator_notes", "adjudicator_context_used",
]


def generate_hidden_seed() -> int:
    """A true (non-reproducible) draw used to seed the per-row RNG for one
    package-building run. The seed itself is recorded only in the private
    mapping file, never in code or in any tracked report."""
    return random.SystemRandom().randint(1, 2**31 - 1)


def choose_ab_mapping_per_row(pair_ids: list[str], seed: int) -> dict[str, dict[str, str]]:
    """Independent coin-flip per pair_id (iterated in sorted order so the
    result does not depend on incoming row order), seeded for
    reproducibility given the (private) seed."""
    rng = random.Random(seed)
    mapping: dict[str, dict[str, str]] = {}
    for pid in sorted(pair_ids):
        if rng.random() < 0.5:
            mapping[pid] = {"annotator_1": "A", "annotator_2": "B"}
        else:
            mapping[pid] = {"annotator_1": "B", "annotator_2": "A"}
    return mapping


def build_adjudication_dataframe_per_row(merged: pd.DataFrame, row_mapping: dict[str, dict[str, str]]) -> pd.DataFrame:
    disagreements = merged[~merged["agree"]].sort_values("pair_id").reset_index(drop=True)

    def col_for(real_annotator: str, field: str) -> str:
        return f"annotator_{real_annotator[-1]}_{field}"

    rows = []
    for i, row in disagreements.iterrows():
        pid = row["pair_id"]
        mapping = row_mapping[pid]
        record = {
            "adjudication_row": i + 1, "pair_id": pid, "domain": row["domain"],
            "string_a": row["string_a"], "string_b": row["string_b"],
        }
        for real_annotator, letter in mapping.items():
            record[f"decision_{letter}"] = row[col_for(real_annotator, "label")]
            record[f"justification_{letter}"] = row[col_for(real_annotator, "justification")]
            record[f"context_used_{letter}"] = row[col_for(real_annotator, "context_used")]
        record["adjudicated_label"] = ""
        record["adjudicator_notes"] = ""
        record["adjudicator_context_used"] = ""
        rows.append(record)
    return pd.DataFrame(rows, columns=ADJUDICATION_COLUMNS)


def write_adjudication_package(df: pd.DataFrame, out_path: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Disagreements")
    ws.append(ADJUDICATION_COLUMNS)
    for _, row in df.iterrows():
        ws.append([row[c] for c in ADJUDICATION_COLUMNS])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)


def write_private_row_mapping(row_mapping: dict[str, dict[str, str]], seed: int, n_disagreements: int, out_path: Path) -> None:
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "n_disagreements": n_disagreements,
        "mapping_per_pair_id": row_mapping,
        "note": "PRIVATE. Per-row A/B anonymisation for the CORRECTED adjudication package. Never shown to the adjudicator, never committed. Restricted provenance only.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def build(merged: pd.DataFrame, corrected_dir: Path, seed: int | None = None) -> dict:
    if seed is None:
        seed = generate_hidden_seed()
    disagreement_ids = list(merged.loc[~merged["agree"], "pair_id"])
    row_mapping = choose_ab_mapping_per_row(disagreement_ids, seed)
    df = build_adjudication_dataframe_per_row(merged, row_mapping)

    out_path = corrected_dir / "PRIMARY_ADJUDICATION_CORRECTED.xlsx"
    write_adjudication_package(df, out_path)
    write_private_row_mapping(row_mapping, seed, len(df), corrected_dir / "AB_MAPPING_PER_ROW_PRIVATE.json")

    n_a1_as_a = sum(1 for m in row_mapping.values() if m["annotator_1"] == "A")
    n_a1_as_b = len(row_mapping) - n_a1_as_a
    return {
        "path": out_path,
        "n_disagreements": len(df),
        "n_annotator_1_as_A": n_a1_as_a,
        "n_annotator_1_as_B": n_a1_as_b,
    }


if __name__ == "__main__":
    raise SystemExit(
        "Invoke via the corrected H2 driver (build() above), not directly, so it uses the real corrected merged data."
    )
