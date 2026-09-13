"""C1 Task 2: frozen-inference input builder.

Builds deterministic, gold-label-free evaluation inputs for CE400,
diabetes500, and pooled900 from the frozen PRIMARY_GOLD_900_FINAL.csv.

Every prediction runner in this package must receive ONLY the columns
produced here (pair_id, domain, string_a, string_b) -- NEVER
final_gold_label or any other gold-derived column -- so that no model
call can be influenced, even accidentally, by the answer. Gold is joined
back only in a separate evaluation step, after predictions are fully
produced and saved to disk.

Aborts loudly (raises FrozenInputError) if the frozen gold CSV's hash
does not match the one recorded when the gold was frozen -- this must be
checked before doing anything else, every time this module is used.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
GOLD_CSV = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "gold" / "PRIMARY_GOLD_900_FINAL.csv"
EXPECTED_GOLD_CSV_SHA256 = "89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479"

FROZEN_INPUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "experiments" / "frozen_inputs"

INPUT_COLUMNS = ["pair_id", "domain", "string_a", "string_b"]
FORBIDDEN_GOLD_DERIVED_COLUMNS = {
    "final_gold_label", "gold_source", "annotator_1_label", "annotator_1_justification",
    "annotator_2_corrected_label", "annotator_2_justification", "annotator_2_annotation_source",
    "initial_agreement", "adjudicated_label", "adjudicator_notes",
    "superseded_original_a2_diabetes_label",
}


class FrozenInputError(Exception):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_gold_hash() -> str:
    if not GOLD_CSV.exists():
        raise FrozenInputError(f"Frozen gold CSV not found: {GOLD_CSV} -- ABORT")
    actual = _sha256(GOLD_CSV)
    if actual != EXPECTED_GOLD_CSV_SHA256:
        raise FrozenInputError(
            f"Frozen gold CSV hash mismatch -- ABORT before doing anything else. "
            f"Expected {EXPECTED_GOLD_CSV_SHA256}, got {actual}"
        )
    return actual


def load_gold_stringonly() -> pd.DataFrame:
    """Reads the frozen gold CSV but returns ONLY the columns a model
    call may ever see (pair_id, domain, string_a, string_b)."""
    verify_gold_hash()
    df = pd.read_csv(GOLD_CSV, dtype=str)
    return df[INPUT_COLUMNS].copy()


def build_partitions() -> dict[str, pd.DataFrame]:
    stringonly = load_gold_stringonly()
    ce = stringonly[stringonly["domain"] == "circular_economy"].reset_index(drop=True)
    bio = stringonly[stringonly["domain"] == "biomedical_diabetes_mellitus"].reset_index(drop=True)
    pooled = stringonly.reset_index(drop=True)
    return {"ce400": ce, "diabetes500": bio, "pooled900": pooled}


@dataclass
class PartitionValidationResult:
    ok: bool
    issues: list = field(default_factory=list)


def validate_partitions(partitions: dict[str, pd.DataFrame]) -> PartitionValidationResult:
    issues: list[str] = []
    ce, bio, pooled = partitions["ce400"], partitions["diabetes500"], partitions["pooled900"]

    if len(ce) != 400:
        issues.append(f"CE400 row count != 400 ({len(ce)})")
    if len(bio) != 500:
        issues.append(f"diabetes500 row count != 500 ({len(bio)})")
    if len(pooled) != 900:
        issues.append(f"pooled900 row count != 900 ({len(pooled)})")

    for name, df in partitions.items():
        if df["pair_id"].duplicated().any():
            issues.append(f"{name}: duplicate pair_id found")
        missing_strings = df["string_a"].isna() | (df["string_a"] == "") | df["string_b"].isna() | (df["string_b"] == "")
        if missing_strings.any():
            issues.append(f"{name}: {int(missing_strings.sum())} rows have a missing string_a/string_b")
        leaked = FORBIDDEN_GOLD_DERIVED_COLUMNS & set(df.columns)
        if leaked:
            issues.append(f"{name}: gold-derived columns leaked into frozen-inference input: {sorted(leaked)}")

    if set(ce["pair_id"]) & set(bio["pair_id"]):
        issues.append("CE400 and diabetes500 pair_id sets overlap -- must be disjoint")
    if (set(ce["pair_id"]) | set(bio["pair_id"])) != set(pooled["pair_id"]):
        issues.append("pooled900 is not exactly the union of CE400 and diabetes500")

    return PartitionValidationResult(ok=len(issues) == 0, issues=issues)


def write_partitions(partitions: dict[str, pd.DataFrame]) -> dict[str, Path]:
    FROZEN_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, df in partitions.items():
        out = FROZEN_INPUT_DIR / f"{name}_frozen_input.csv"
        df.to_csv(out, index=False, encoding="utf-8")
        paths[name] = out
    return paths


def build_and_write() -> dict:
    partitions = build_partitions()
    validation = validate_partitions(partitions)
    if not validation.ok:
        raise FrozenInputError(f"Frozen input validation FAILED -- not writing anything. Issues: {validation.issues}")
    paths = write_partitions(partitions)
    return {"partitions": partitions, "paths": paths, "validation": validation, "gold_csv_sha256": EXPECTED_GOLD_CSV_SHA256}


if __name__ == "__main__":
    result = build_and_write()
    for name, path in result["paths"].items():
        print(f"{name}: {len(result['partitions'][name])} rows -> {path}")
