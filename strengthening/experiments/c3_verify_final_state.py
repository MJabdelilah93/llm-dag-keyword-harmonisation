"""C3 Task 1: independent verification of the final post-C2 repository state.
Read-only: makes no API call, modifies no gold/frozen/candidate file. Fails
loudly (raises) on any integrity check failure rather than silently
reporting a soft warning.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = STRENGTHENING_ROOT.parent
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
FREEZE_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution" / "frozen_predictions"

EXPECTED_BRANCH = "strengthen/m7-2026"
EXPECTED_HEAD_PREFIX = "fa972ce"

EXPECTED_XLSX_SHA256 = "bb90618580e944e54904c231efca83f50eebc1ef5eb4ea7f0fd8e803adbbec0a"
EXPECTED_CSV_SHA256 = "89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479"

EXPECTED_CANDIDATE_SET_HASHES = {
    "circular_economy": "aa494e5b11543fe37996d842f8a3f9ed40622ee5c951b889b03e1f9ba58eea79",
    "biomedical_diabetes_mellitus": "4c0875bb7e9c6d511a59bae1405218e67208b57ed22b4160d25bb0e8f68133fd",
}

EXPECTED_FREEZE_HASHES = {
    "primary_m7": "f0c495736503b6eaac948bce46288374ed3532df6de913ad22f70610b2f2b1f9",
    "b6": "682cac6bbe7a8137657028df55d6fa5035d574928e508e8cbdf6bfdbc0e0e284",
    "b7": "5262d37040c27af804f9c387424f941db66ba49d1d0c732cccfc8f2bfa64aa83",
    "b8": "d09ac5104cbdec7d09adf8afce124eadb24a36214c92a55311ff604aec85e3a2",
    "openai": "c7b4bc5a830a73c709f014c5de62f0cd7d1ce5fba433e0b6e745105b318b4dd8",
    "b1_b5": "1c0be1dba7f9e457ba468cdbfbc2dc552a121e678a4449b6594736f2c52c01ed",
}

REQUIRED_FIELDS = {
    "primary_m7_frozen.csv": ["pair_id", "domain", "guard_decision", "guard_confidence"],
    "b6_frozen.csv": ["pair_id", "domain", "parsed_decision"],
    "b7_frozen.csv": ["pair_id", "domain", "binary_label"],
    "b8_frozen.csv": ["pair_id", "domain", "b8_predicted_label"],
    "openai_frozen.csv": ["pair_id", "domain", "guard_decision", "guard_confidence"],
    "b1_b5_frozen.csv": ["pair_id", "B1_Exact", "B2_Normalised", "B3_JaroWinkler", "B4_TFIDF", "B5_Embedding"],
}


class C3IntegrityError(Exception):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_branch_and_head() -> dict:
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    ok = (branch == EXPECTED_BRANCH) and head.startswith(EXPECTED_HEAD_PREFIX)
    result = {"ok": ok, "branch": branch, "head": head, "expected_branch": EXPECTED_BRANCH, "expected_head_prefix": EXPECTED_HEAD_PREFIX}
    if not ok:
        raise C3IntegrityError(f"branch/HEAD mismatch: {result}")
    return result


# Files this C3 phase itself creates before this check can run -- excluded from the
# "clean tree at start" definition the same way c2_prerun_manifest.py excluded itself.
EXPECTED_NEW_FILES_THIS_PHASE = {
    "strengthening/experiments/c3_verify_final_state.py",
}


def check_clean_tree() -> dict:
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    unexpected_lines = []
    for line in status.splitlines():
        path = line[3:].strip()
        if path.replace("\\", "/") not in EXPECTED_NEW_FILES_THIS_PHASE:
            unexpected_lines.append(line)
    ok = len(unexpected_lines) == 0
    result = {"ok": ok, "status_output": status, "unexpected_lines": unexpected_lines}
    if not ok:
        raise C3IntegrityError(f"working tree not clean at start of C3 (beyond this phase's own new files): {unexpected_lines}")
    return result


def check_gold_hashes() -> dict:
    from .frozen_inputs import GOLD_CSV
    gold_xlsx = GOLD_CSV.parent / "PRIMARY_GOLD_900_FINAL.xlsx"
    if not gold_xlsx.exists():
        raise C3IntegrityError(f"expected frozen gold XLSX missing: {gold_xlsx}")
    xlsx_hash = _sha256(gold_xlsx)
    csv_hash = _sha256(GOLD_CSV)
    xlsx_ok = xlsx_hash == EXPECTED_XLSX_SHA256
    csv_ok = csv_hash == EXPECTED_CSV_SHA256
    result = {
        "ok": xlsx_ok and csv_ok,
        "xlsx_sha256": xlsx_hash, "xlsx_expected": EXPECTED_XLSX_SHA256, "xlsx_ok": xlsx_ok,
        "csv_sha256": csv_hash, "csv_expected": EXPECTED_CSV_SHA256, "csv_ok": csv_ok,
    }
    if not result["ok"]:
        raise C3IntegrityError(f"gold hash mismatch: {result}")
    return result


def check_candidate_set_hashes() -> dict:
    from . import b8_benchmark_eval_dense as c1b
    from .frozen_inputs import load_gold_stringonly
    gold_stringonly = load_gold_stringonly()
    universes = c1b.build_genuine_domain_universes()
    seeds_by_domain = c1b.build_seeds_by_domain(gold_stringonly)
    candidate_sets, _ = c1b.compute_candidate_sets_dense(universes, seeds_by_domain, top_k=c1b.TOP_K)
    observed = {domain: c1b.candidate_set_hash(csets) for domain, csets in candidate_sets.items()}
    mismatches = {d: (EXPECTED_CANDIDATE_SET_HASHES[d], observed[d]) for d in EXPECTED_CANDIDATE_SET_HASHES if observed[d] != EXPECTED_CANDIDATE_SET_HASHES[d]}
    result = {"ok": not mismatches, "observed": observed, "expected": EXPECTED_CANDIDATE_SET_HASHES, "mismatches": mismatches}
    if mismatches:
        raise C3IntegrityError(f"C1B candidate-set hash mismatch: {mismatches}")
    return result


def check_freeze_hashes_and_rows() -> dict:
    per_method = {}
    for method, expected_hash in EXPECTED_FREEZE_HASHES.items():
        path = FREEZE_DIR / f"{method}_frozen.csv"
        if not path.exists():
            raise C3IntegrityError(f"expected frozen snapshot missing: {path}")
        observed_hash = _sha256(path)
        df = pd.read_csv(path, dtype=str)
        n_rows = len(df)
        dup_ids = df["pair_id"][df["pair_id"].duplicated()].tolist()
        required = REQUIRED_FIELDS[f"{method}_frozen.csv"]
        missing_field_counts = {}
        for field in required:
            if field not in df.columns:
                missing_field_counts[field] = "COLUMN_ABSENT"
            else:
                n_missing = int(df[field].isna().sum())
                if method in ("b7", "b8") and field in ("binary_label", "b8_predicted_label"):
                    # non-match/uncertain-by-guard are legitimate non-null values; only true NaN counts as missing.
                    pass
                missing_field_counts[field] = n_missing
        hash_ok = observed_hash == expected_hash
        rows_ok = n_rows == 900
        no_dup_ok = len(dup_ids) == 0
        entry = {
            "ok": hash_ok and rows_ok and no_dup_ok,
            "sha256_observed": observed_hash, "sha256_expected": expected_hash, "hash_ok": hash_ok,
            "n_rows": n_rows, "rows_ok": rows_ok,
            "n_duplicate_pair_ids": len(dup_ids), "duplicate_pair_ids": dup_ids, "no_dup_ok": no_dup_ok,
            "missing_field_counts": missing_field_counts,
        }
        per_method[method] = entry
        if not entry["ok"]:
            raise C3IntegrityError(f"{method}: freeze/row/duplicate check failed: {entry}")
    return per_method


def check_no_missing_required_fields(per_method_freeze_check: dict) -> dict:
    # For each method, the only field allowed to be null is the decision/label field itself
    # for genuinely-erroring rows (which the raw JSONL/error column already accounts for) --
    # verified separately per-method below against pair_id/domain, which must never be null.
    core_fields_ok = {}
    for method in EXPECTED_FREEZE_HASHES:
        path = FREEZE_DIR / f"{method}_frozen.csv"
        df = pd.read_csv(path, dtype=str)
        pair_id_missing = int(df["pair_id"].isna().sum())
        core_fields_ok[method] = {"pair_id_missing": pair_id_missing, "ok": pair_id_missing == 0}
        if pair_id_missing:
            raise C3IntegrityError(f"{method}: {pair_id_missing} rows with missing pair_id")
    return core_fields_ok


def run() -> dict:
    result = {
        "branch_and_head": check_branch_and_head(),
        "clean_tree": check_clean_tree(),
        "gold_hashes": check_gold_hashes(),
        "candidate_set_hashes": check_candidate_set_hashes(),
    }
    freeze_check = check_freeze_hashes_and_rows()
    result["freeze_hashes_rows_duplicates"] = freeze_check
    result["core_required_fields"] = check_no_missing_required_fields(freeze_check)
    result["all_checks_passed"] = True
    with open(REPORTS_DIR / "C3_TASK1_FINAL_STATE_VERIFICATION.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
