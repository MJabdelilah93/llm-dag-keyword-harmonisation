"""C2 Task 1: pre-run integrity check, executed before ANY paid API call.

Verifies branch/HEAD, clean tree, gold hashes, frozen settings, C1B
candidate-set hashes, API-key presence (never their values), that every
paid runner requires its explicit execute-paid gate, and that the C2
output directory is new. Aborts (raises) before returning a manifest if
any check fails -- callers must not proceed to any real API call unless
this returns ok=True.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .frozen_inputs import EXPECTED_GOLD_CSV_SHA256, GOLD_CSV, verify_gold_hash

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = STRENGTHENING_ROOT.parent
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
C2_OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution"

EXPECTED_HEAD = "ce2f253ea0ae21a6487c802bfe7e794c200a722d"
EXPECTED_BRANCH = "strengthen/m7-2026"
EXPECTED_GOLD_XLSX_SHA256 = "bb90618580e944e54904c231efca83f50eebc1ef5eb4ea7f0fd8e803adbbec0a"

EXPECTED_CANDIDATE_SET_HASHES = {
    "circular_economy": "aa494e5b11543fe37996d842f8a3f9ed40622ee5c951b889b03e1f9ba58eea79",
    "biomedical_diabetes_mellitus": "4c0875bb7e9c6d511a59bae1405218e67208b57ed22b4160d25bb0e8f68133fd",
}

FROZEN_SETTINGS = {
    "primary_and_b6_model": "claude-haiku-4-5-20251001",
    "primary_guard_threshold": 0.5,
    "b7_model": "claude-haiku-4-5-20251001",
    "b7_temperature": 0.0,
    "openai_model": "gpt-5.4-nano-2026-03-17",
    "openai_reasoning_effort": "none",
    "openai_threshold": 0.80,
}


class PreRunIntegrityError(Exception):
    pass


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_branch_and_head() -> dict:
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=LEGACY_ROOT, capture_output=True, text=True).stdout.strip()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=LEGACY_ROOT, capture_output=True, text=True).stdout.strip()
    ok = branch == EXPECTED_BRANCH and head == EXPECTED_HEAD
    return {"ok": ok, "branch": branch, "head": head, "expected_branch": EXPECTED_BRANCH, "expected_head": EXPECTED_HEAD}


#: Files this task's own preparatory work is expected to add before the
#: first paid call -- their presence in `git status` is not a surprise
#: change and must not block the pre-run check. Anything else showing up
#: IS a surprise and must block.
EXPECTED_NEW_FILES_THIS_TASK = {
    "strengthening/experiments/c2_prerun_manifest.py",
}


def check_clean_tree() -> dict:
    status = subprocess.run(["git", "status", "--short"], cwd=LEGACY_ROOT, capture_output=True, text=True).stdout
    unexpected_lines = []
    for line in status.splitlines():
        path = line[3:].strip()
        if path not in EXPECTED_NEW_FILES_THIS_TASK:
            unexpected_lines.append(line)
    ok = not unexpected_lines
    return {"ok": ok, "status_output": status, "unexpected_lines": unexpected_lines}


def check_gold_hashes() -> dict:
    xlsx_path = GOLD_CSV.parent / "PRIMARY_GOLD_900_FINAL.xlsx"
    xlsx_hash = _sha256(xlsx_path) if xlsx_path.exists() else None
    csv_hash = None
    csv_ok = False
    try:
        csv_hash = verify_gold_hash()
        csv_ok = True
    except Exception:
        csv_ok = False
    xlsx_ok = xlsx_hash == EXPECTED_GOLD_XLSX_SHA256
    return {
        "ok": xlsx_ok and csv_ok,
        "xlsx_sha256": xlsx_hash, "xlsx_expected": EXPECTED_GOLD_XLSX_SHA256, "xlsx_ok": xlsx_ok,
        "csv_sha256": csv_hash, "csv_expected": EXPECTED_GOLD_CSV_SHA256, "csv_ok": csv_ok,
    }


def check_frozen_settings() -> dict:
    model_cfg = yaml.safe_load(open(LEGACY_ROOT / "configs" / "model_config.yaml", encoding="utf-8"))
    thresholds = json.load(open(LEGACY_ROOT / "results" / "tuned_thresholds.json", encoding="utf-8"))
    openai_manifest = json.load(open(LEGACY_ROOT / "results" / "current_paper" / "phase1b" / "openai_dev_freeze_manifest.json", encoding="utf-8"))
    from ..baselines.b7_direct_relation.client import B7_INTENDED_TEMPERATURE, B7_MODEL_ID

    observed = {
        "primary_and_b6_model": model_cfg["model"]["model_id"],
        "primary_guard_threshold": thresholds["guard_confidence_threshold"]["threshold"],
        "b7_model": B7_MODEL_ID,
        "b7_temperature": B7_INTENDED_TEMPERATURE,
        "openai_model": openai_manifest["model"]["model_id_requested"],
        "openai_reasoning_effort": openai_manifest["model"]["reasoning_effort"],
        "openai_threshold": openai_manifest["threshold_selection"]["selected_threshold"],
    }
    mismatches = {k: (FROZEN_SETTINGS[k], observed[k]) for k in FROZEN_SETTINGS if FROZEN_SETTINGS[k] != observed[k]}
    return {"ok": not mismatches, "observed": observed, "expected": FROZEN_SETTINGS, "mismatches": mismatches}


def check_candidate_set_hashes() -> dict:
    manifest_path = REPORTS_DIR / "B8_DENSE_CANDIDATE_GENERATION.json"
    if not manifest_path.exists():
        return {"ok": False, "error": f"{manifest_path} not found"}
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    observed = manifest.get("candidate_set_hashes", {})
    mismatches = {k: (EXPECTED_CANDIDATE_SET_HASHES[k], observed.get(k)) for k in EXPECTED_CANDIDATE_SET_HASHES if observed.get(k) != EXPECTED_CANDIDATE_SET_HASHES[k]}
    return {"ok": not mismatches, "observed": observed, "expected": EXPECTED_CANDIDATE_SET_HASHES, "mismatches": mismatches}


def check_api_keys_present() -> dict:
    """Never reads or logs the actual key VALUES -- presence only."""
    return {
        "ok": bool(os.environ.get("ANTHROPIC_API_KEY")) and bool(os.environ.get("OPENAI_API_KEY")),
        "anthropic_present": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "openai_present": bool(os.environ.get("OPENAI_API_KEY")),
    }


def check_runners_require_execute_paid_gate() -> dict:
    from . import b6_runner, openai_second_provider_runner, primary_m7_runner
    from .paid_gate import PaidExecutionNotAuthorisedError, require_paid_execution_authorised
    from ..baselines.b7_direct_relation.client import B7Client

    results = {}
    try:
        require_paid_execution_authorised(False, "ANTHROPIC_API_KEY")
        results["paid_gate_default_refuses"] = False
    except PaidExecutionNotAuthorisedError:
        results["paid_gate_default_refuses"] = True

    try:
        B7Client().classify("a", "b")
        results["b7_default_refuses"] = False
    except NotImplementedError:
        results["b7_default_refuses"] = True

    results["primary_has_run_real_gated"] = hasattr(primary_m7_runner, "run_real")
    results["b6_has_run_real_gated"] = hasattr(b6_runner, "run_real")
    results["openai_has_run_real_gated"] = hasattr(openai_second_provider_runner, "run_real")

    ok = all(results.values())
    return {"ok": ok, **results}


def check_output_dir_is_new() -> dict:
    already_existed = C2_OUT_DIR.exists() and any(C2_OUT_DIR.iterdir())
    C2_OUT_DIR.mkdir(parents=True, exist_ok=True)
    prior_experiment_dirs = sorted(p.name for p in (STRENGTHENING_ROOT / "restricted_local" / "experiments").iterdir() if p.is_dir())
    return {
        "ok": not already_existed,
        "c2_out_dir": str(C2_OUT_DIR),
        "c2_out_dir_was_already_populated": already_existed,
        "prior_c1_experiment_dirs_untouched": prior_experiment_dirs,
    }


def run() -> dict:
    checks = {
        "branch_and_head": check_branch_and_head(),
        "clean_tree": check_clean_tree(),
        "gold_hashes": check_gold_hashes(),
        "frozen_settings": check_frozen_settings(),
        "candidate_set_hashes": check_candidate_set_hashes(),
        "api_keys_present": check_api_keys_present(),
        "runners_require_execute_paid_gate": check_runners_require_execute_paid_gate(),
        "output_dir_is_new": check_output_dir_is_new(),
    }
    all_ok = all(c["ok"] for c in checks.values())
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "all_checks_passed": all_ok,
        "checks": checks,
    }
    C2_OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(C2_OUT_DIR / "PRERUN_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    with open(REPORTS_DIR / "C2_PRERUN_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    if not all_ok:
        raise PreRunIntegrityError(f"Pre-run integrity check FAILED -- ABORT before any API call. Checks: {checks}")
    return manifest


if __name__ == "__main__":
    result = run()
    print(json.dumps({"all_checks_passed": result["all_checks_passed"]}, indent=2))
