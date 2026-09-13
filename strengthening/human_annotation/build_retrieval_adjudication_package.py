"""From merged retrieval annotations, build a disagreement-only
adjudication file restricted to the DOUBLE-CODED subset (rows both
annotators actually labelled -- outside-pool + audit sample). Never
overwrites existing files.

DO NOT run against real annotator files until Phase H3 merge is complete.

`build()`/`write()` below are the original (H3-design-era) builder, kept
unchanged for backward compatibility with existing tests -- it exposes
annotator_1_label/annotator_2_label directly (no A/B anonymisation).

`build_anonymised()`/`write_anonymised()` are a FUTURE scaffold, added
after the H2 correction found that a single fixed whole-package A/B
mapping can leak a pattern: they anonymise annotator identity
INDEPENDENTLY PER DISAGREEMENT ROW, the same principle used for the
corrected H2 adjudication package. Neither is invoked by any driver yet --
there are no retrieval labels to adjudicate until Phase H3 annotation is
complete. Exercised with synthetic data only.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def build(merged: pd.DataFrame) -> pd.DataFrame:
    double_coded = merged[merged["double_coded"]]
    disagreements = double_coded[~double_coded["agree"]].copy()
    disagreements["adjudicated_label"] = ""
    disagreements["adjudicator_notes"] = ""
    cols = [
        "retrieval_pair_id", "domain", "seed_string", "candidate_string",
        "annotator_1_label", "annotator_1_justification",
        "annotator_2_label", "annotator_2_justification",
        "adjudicated_label", "adjudicator_notes",
    ]
    return disagreements[cols].reset_index(drop=True)


def write(merged: pd.DataFrame, out_path: Path) -> Path:
    if out_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing adjudication package: {out_path}")
    pkg = build(merged)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pkg.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


ANONYMISED_COLUMNS = [
    "adjudication_row", "retrieval_pair_id", "domain", "seed_string", "candidate_string",
    "decision_A", "decision_B", "justification_A", "justification_B",
    "adjudicated_label", "adjudicator_notes",
]


def generate_hidden_seed() -> int:
    return random.SystemRandom().randint(1, 2**31 - 1)


def choose_ab_mapping_per_row(retrieval_pair_ids: list[str], seed: int) -> dict[str, dict[str, str]]:
    rng = random.Random(seed)
    mapping: dict[str, dict[str, str]] = {}
    for pid in sorted(retrieval_pair_ids):
        if rng.random() < 0.5:
            mapping[pid] = {"annotator_1": "A", "annotator_2": "B"}
        else:
            mapping[pid] = {"annotator_1": "B", "annotator_2": "A"}
    return mapping


def build_anonymised(merged: pd.DataFrame, row_mapping: dict[str, dict[str, str]]) -> pd.DataFrame:
    double_coded = merged[merged["double_coded"]]
    disagreements = double_coded[~double_coded["agree"]].sort_values("retrieval_pair_id").reset_index(drop=True)

    def col_for(real_annotator: str, field: str) -> str:
        return f"annotator_{real_annotator[-1]}_{field}"

    rows = []
    for i, row in disagreements.iterrows():
        pid = row["retrieval_pair_id"]
        mapping = row_mapping[pid]
        record = {
            "adjudication_row": i + 1, "retrieval_pair_id": pid, "domain": row["domain"],
            "seed_string": row["seed_string"], "candidate_string": row["candidate_string"],
        }
        for real_annotator, letter in mapping.items():
            record[f"decision_{letter}"] = row[col_for(real_annotator, "label")]
            record[f"justification_{letter}"] = row[col_for(real_annotator, "justification")]
        record["adjudicated_label"] = ""
        record["adjudicator_notes"] = ""
        rows.append(record)
    return pd.DataFrame(rows, columns=ANONYMISED_COLUMNS)


def write_private_row_mapping(row_mapping: dict[str, dict[str, str]], seed: int, n_disagreements: int, out_path: Path) -> None:
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "n_disagreements": n_disagreements,
        "mapping_per_retrieval_pair_id": row_mapping,
        "note": "PRIVATE. Per-row A/B anonymisation for the future retrieval adjudication package. Never shown to the adjudicator, never committed.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def write_anonymised(merged: pd.DataFrame, out_dir: Path, seed: int | None = None) -> dict:
    if seed is None:
        seed = generate_hidden_seed()
    double_coded = merged[merged["double_coded"]]
    disagreement_ids = list(double_coded.loc[~double_coded["agree"], "retrieval_pair_id"])
    row_mapping = choose_ab_mapping_per_row(disagreement_ids, seed)
    pkg = build_anonymised(merged, row_mapping)

    out_path = out_dir / "RETRIEVAL_ADJUDICATION.csv"
    if out_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing adjudication package: {out_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    pkg.to_csv(out_path, index=False, encoding="utf-8")
    write_private_row_mapping(row_mapping, seed, len(pkg), out_dir / "RETRIEVAL_AB_MAPPING_PER_ROW_PRIVATE.json")
    return {"path": out_path, "n_disagreements": len(pkg)}


if __name__ == "__main__":
    raise SystemExit(
        "This script builds an adjudication package from REAL merged retrieval annotations and must not be run "
        "until Phase H3 merge is complete. Import build()/write() (or build_anonymised()/write_anonymised() for "
        "the future per-row-anonymised package) from a driver script instead."
    )
