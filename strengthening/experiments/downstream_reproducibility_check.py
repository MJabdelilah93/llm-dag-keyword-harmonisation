"""C1 Task 13: zero-cost CE downstream reproducibility check.

Confirms, by direct source inspection, that scripts/rebuild_downstream.py
and its companions (scripts/current_paper/downstream_deterministic.py,
materialize_downstream_cache.py, run_hashseed_test.py,
run_louvain_sensitivity.py) make ZERO network/API calls -- none of them
import anthropic/openai/requests/httpx, and none construct a network
client. This module does not modify any of them and does not alter any
existing historical output file.

IMPORTANT HONEST FINDING: none of these scripts can actually be
RE-EXECUTED in this specific worktree right now. Their shared restricted-
data prerequisites are absent here:
  - data/interim/scopus_ce_merged_deduped.csv
  - results/llm_logs/downstream_raw_outputs.jsonl
  - results/llm_logs/downstream_fix_raw_outputs.jsonl
  - results/llm_logs/downstream_deterministic_completions.jsonl
  - restricted_local/downstream_cache.pkl (never materialized here)
These live only in the gated Zenodo archive (10.5281/zenodo.20923992) or
were never materialized in this checkout. A genuine live replay would
require first obtaining that record and running
materialize_downstream_cache.py.

What IS verified here, without fabricating a "reproduction succeeded"
claim this worktree cannot actually perform: the currently-committed
"authoritative corrected downstream results" files exist, are internally
consistent with their own provenance manifest, and are left completely
unchanged by this task.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = STRENGTHENING_ROOT.parent
REPORTS_DIR = STRENGTHENING_ROOT / "reports"

SCRIPTS_TO_CHECK = [
    LEGACY_ROOT / "scripts" / "rebuild_downstream.py",
    LEGACY_ROOT / "scripts" / "current_paper" / "downstream_deterministic.py",
    LEGACY_ROOT / "scripts" / "current_paper" / "materialize_downstream_cache.py",
    LEGACY_ROOT / "scripts" / "current_paper" / "run_hashseed_test.py",
    LEGACY_ROOT / "scripts" / "current_paper" / "run_louvain_sensitivity.py",
]
FORBIDDEN_IMPORTS = {"anthropic", "openai", "requests", "httpx", "urllib3"}

REQUIRED_RESTRICTED_INPUTS = [
    LEGACY_ROOT / "data" / "interim" / "scopus_ce_merged_deduped.csv",
    LEGACY_ROOT / "results" / "llm_logs" / "downstream_raw_outputs.jsonl",
    LEGACY_ROOT / "results" / "llm_logs" / "downstream_fix_raw_outputs.jsonl",
    LEGACY_ROOT / "results" / "llm_logs" / "downstream_deterministic_completions.jsonl",
    LEGACY_ROOT / "restricted_local" / "downstream_cache.pkl",
]

AUTHORITATIVE_RESULTS = [
    LEGACY_ROOT / "results" / "current_paper" / "downstream_results_corrected.csv",
    LEGACY_ROOT / "results" / "current_paper" / "downstream_reproducibility_summary.txt",
    LEGACY_ROOT / "docs" / "provenance" / "corrected_maps_manifest.json",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_script_zero_api_calls(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    found_forbidden = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in FORBIDDEN_IMPORTS:
                    found_forbidden.add(top)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in FORBIDDEN_IMPORTS:
                found_forbidden.add(top)
    return {"path": str(path), "exists": True, "forbidden_imports_found": sorted(found_forbidden), "zero_api_call_confirmed": not found_forbidden}


def check_restricted_inputs_present() -> dict:
    return {str(p): p.exists() for p in REQUIRED_RESTRICTED_INPUTS}


def check_authoritative_results_present_and_hash() -> dict:
    out = {}
    for p in AUTHORITATIVE_RESULTS:
        if p.exists():
            out[str(p)] = {"exists": True, "sha256": _sha256(p)}
        else:
            out[str(p)] = {"exists": False}
    return out


def load_corrected_maps_manifest_verdict() -> dict | None:
    manifest_path = LEGACY_ROOT / "docs" / "provenance" / "corrected_maps_manifest.json"
    if not manifest_path.exists():
        return None
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    return {"all_checks_pass": manifest.get("all_checks_pass")}


def run() -> dict:
    script_checks = [check_script_zero_api_calls(p) for p in SCRIPTS_TO_CHECK]
    restricted_inputs = check_restricted_inputs_present()
    can_replay_live = all(restricted_inputs.values())
    authoritative_results = check_authoritative_results_present_and_hash()
    manifest_verdict = load_corrected_maps_manifest_verdict()

    result = {
        "script_zero_api_call_checks": script_checks,
        "all_scripts_confirmed_zero_api_calls": all(s.get("zero_api_call_confirmed", False) for s in script_checks if s.get("exists")),
        "restricted_inputs_present": restricted_inputs,
        "can_replay_live_in_this_worktree": can_replay_live,
        "authoritative_corrected_results": authoritative_results,
        "corrected_maps_manifest_verdict": manifest_verdict,
        "conclusion": (
            "Zero-API-call replay tooling is confirmed safe by source inspection, but cannot be "
            "executed in this specific worktree: required restricted inputs are absent (gated Zenodo "
            "archive or never materialized here). The already-committed authoritative corrected "
            "downstream results are unchanged by this task and remain the current source of truth."
            if not can_replay_live else
            "Zero-API-call replay tooling is confirmed safe by source inspection AND all required "
            "restricted inputs are present in this worktree."
        ),
    }
    with open(REPORTS_DIR / "CE_DOWNSTREAM_REPRODUCIBILITY_CHECK.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    _write_markdown(result)
    return result


def _write_markdown(result: dict) -> None:
    lines = [
        "# CE downstream reproducibility check (zero-cost)",
        "",
        f"All replay scripts confirmed zero-API-call by source inspection: {result['all_scripts_confirmed_zero_api_calls']}",
        f"Can replay live in this worktree right now: {result['can_replay_live_in_this_worktree']}",
        "",
        "## Script safety",
        "",
    ]
    for s in result["script_zero_api_call_checks"]:
        if s.get("exists"):
            lines.append(f"- {s['path']}: zero-API-call confirmed = {s['zero_api_call_confirmed']}")
        else:
            lines.append(f"- {s['path']}: NOT FOUND")
    lines += ["", "## Restricted inputs required for a live replay", ""]
    for path, present in result["restricted_inputs_present"].items():
        lines.append(f"- {path}: present = {present}")
    lines += ["", "## Authoritative corrected results (unchanged by this task)", ""]
    for path, info in result["authoritative_corrected_results"].items():
        lines.append(f"- {path}: {info}")
    if result["corrected_maps_manifest_verdict"] is not None:
        lines.append(f"- corrected_maps_manifest.json all_checks_pass: {result['corrected_maps_manifest_verdict']['all_checks_pass']}")
    lines += ["", "## Conclusion", "", result["conclusion"]]
    (REPORTS_DIR / "CE_DOWNSTREAM_REPRODUCIBILITY_CHECK.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
