"""H2 Step 5: build the disagreement-only PRIMARY_ADJUDICATION.xlsx,
with annotators anonymised as A/B (one fixed, randomly-chosen mapping for
the whole package -- never per-row, so the adjudicator cannot infer a
pattern). The mapping itself is recorded ONLY in a private, restricted
provenance file, never in the adjudicator-facing package or in any
tracked/safe report.
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


def choose_ab_mapping(rng_seed: int | None = None) -> dict[str, str]:
    """One fixed, random coin-flip for the whole package: either
    (annotator_1->A, annotator_2->B) or the reverse. If rng_seed is None,
    uses a true (non-reproducible) random draw -- this is a one-time
    package-building decision, not something that needs to be
    scientifically reproducible; tests pass an explicit seed instead."""
    rng = random.Random(rng_seed) if rng_seed is not None else random.SystemRandom()
    if rng.random() < 0.5:
        return {"annotator_1": "A", "annotator_2": "B"}
    return {"annotator_1": "B", "annotator_2": "A"}


def build_adjudication_dataframe(merged: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    disagreements = merged[~merged["agree"]].sort_values("pair_id").reset_index(drop=True)

    def col_for(real_annotator: str, field: str) -> str:
        return f"annotator_{real_annotator[-1]}_{field}"

    rows = []
    for i, row in disagreements.iterrows():
        record = {"adjudication_row": i + 1, "pair_id": row["pair_id"], "domain": row["domain"],
                  "string_a": row["string_a"], "string_b": row["string_b"]}
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


def write_private_mapping(mapping: dict[str, str], n_disagreements: int, out_path: Path) -> None:
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mapping_annotator_to_letter": mapping,
        "n_disagreements": n_disagreements,
        "note": "PRIVATE. Never shown to the adjudicator, never committed. Restricted provenance only.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


if __name__ == "__main__":
    raise SystemExit(
        "Invoke via the H2 driver (build() below), not directly, so it uses the real merged H1 data."
    )


def build(merged: pd.DataFrame, h2_dir: Path, rng_seed: int | None = None) -> dict:
    mapping = choose_ab_mapping(rng_seed)
    df = build_adjudication_dataframe(merged, mapping)
    out_path = h2_dir / "PRIMARY_ADJUDICATION.xlsx"
    write_adjudication_package(df, out_path)
    write_private_mapping(mapping, len(df), h2_dir / "AB_MAPPING_PRIVATE.json")
    return {"path": out_path, "n_disagreements": len(df), "mapping": mapping}
