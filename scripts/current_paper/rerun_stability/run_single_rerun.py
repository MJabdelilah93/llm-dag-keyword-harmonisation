"""
run_single_rerun.py
=====================
PHASE 1A / TASK 6 — complete, ready-to-execute harness for ONE independent
rerun of the pinned primary model against the frozen 149-pair test set.

DOES NOT CALL THE REAL API IN PHASE 1A. `--mode real` is fully implemented
and ready for Phase 1B, but this script is only ever invoked here with
`--mode dry-run`, which uses the synthetic MockClient and never imports the
`anthropic` package or touches the network.

Design requirements satisfied (Phase 1A Task 6):
  - exact frozen test set (data/benchmark/test_set.csv, 149 pairs, read-only)
  - exact verified v1 prompt (prompts/v1.0.0/system_prompt.txt +
    user_prompt_standard.txt), hashed and recorded per call
  - temperature=0, max_tokens=256, top_p never passed (matches v1 exactly)
  - guard threshold=0.50 (frozen, docs/provenance/phase1_benchmark_freeze.md)
  - NO auxiliary context -- only user_prompt_standard.txt is ever used
  - fresh call for every pair, NO caching/reuse/resume-by-existing-log logic
    (unlike the original scripts/run_full_workflow.py's dev-log-reuse path)
  - one NEW immutable output directory per invocation
    (results/current_paper/rerun_stability/run_<run_id>/), never appended to
    or overwritten by a later run
  - every record includes: timestamp, model identifier returned by the API,
    request parameters, response metadata, token usage, cost, prompt hash,
    pair identifier, raw response, parsed response, final guarded decision
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_v1 import apply_guard, GUARD_THRESHOLD, GUARD_VERSION
from llm_client import AnthropicClient, MockClient, MODEL_ID, TEMPERATURE, MAX_TOKENS

COST_PER_1K_IN = 0.00025   # haiku approximate pricing, matches v1's own historical constant
COST_PER_1K_OUT = 0.00125


def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    return "non_match" if lbl in ("non-match", "non_match") else lbl


def load_frozen_test_set(evidence_root: Path):
    path = evidence_root / "data" / "benchmark" / "test_set.csv"
    if not path.exists():
        sys.exit(f"ERROR: frozen test set not found at {path}")
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["gold_label"] = norm_label(r["gold_label"])
            rows.append(r)
    if len(rows) != 149:
        sys.exit(f"ERROR: expected 149 frozen test pairs, found {len(rows)} -- "
                  f"STOP, the frozen benchmark input has changed (see Task 1 freeze).")
    return rows


def load_frozen_prompts(repo_root: Path):
    system_path = repo_root / "prompts" / "v1.0.0" / "system_prompt.txt"
    user_path = repo_root / "prompts" / "v1.0.0" / "user_prompt_standard.txt"
    system_prompt = system_path.read_text(encoding="utf-8")
    user_template = user_path.read_text(encoding="utf-8")
    return system_prompt, user_template


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"))
    ap.add_argument("--mode", choices=["real", "dry-run"], required=True)
    ap.add_argument("--run-id", required=True,
                     help="Unique identifier for this run, e.g. rerun_01 or dry_run_synthetic_A")
    ap.add_argument("--mock-seed", type=int, default=0, help="Only used in --mode dry-run")
    ap.add_argument("--mock-noise-rate", type=float, default=0.03, help="Only used in --mode dry-run")
    ap.add_argument("--i-have-authorisation", action="store_true",
                     help="Required in addition to --mode real. Set only after explicit "
                          "Phase 1B human authorisation (see PHASE_1A_PRE_API_REPORT.md).")
    args = ap.parse_args()

    if args.mode == "real" and not args.i_have_authorisation:
        sys.exit("REFUSED: --mode real requires --i-have-authorisation. This is a deliberate, "
                 "auditable second guard beyond the --mode flag itself -- it must be passed "
                 "explicitly on the command line, never hardcoded, for every real invocation.")

    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")
    evidence_root = Path(args.evidence_root)
    repo_root = Path(__file__).resolve().parents[3]

    test_rows = load_frozen_test_set(evidence_root)
    system_prompt, user_template = load_frozen_prompts(repo_root)
    system_prompt_hash = sha256_str(system_prompt)
    user_template_hash = sha256_str(user_template)

    out_dir = repo_root / "results" / "current_paper" / "rerun_stability" / f"run_{args.run_id}"
    if out_dir.exists():
        sys.exit(f"REFUSED: output directory already exists ({out_dir}). "
                 f"Every run must write to a NEW immutable directory -- choose a different --run-id.")
    out_dir.mkdir(parents=True)

    if args.mode == "real":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            sys.exit("ERROR: ANTHROPIC_API_KEY not set.")
        client = AnthropicClient(api_key=api_key)
    else:
        gold_lookup = {r["pair_id"]: r["gold_label"] for r in test_rows}
        client = MockClient(seed=args.mock_seed, gold_lookup=gold_lookup, noise_rate=args.mock_noise_rate)

    started_at = datetime.now(timezone.utc).isoformat()
    records = []
    total_cost = 0.0
    for row in test_rows:
        user_prompt = user_template.format(keyword_a=row["keyword_a"], keyword_b=row["keyword_b"])
        call_result = client.call(system_prompt, user_prompt, pair_id=row["pair_id"])
        guard = apply_guard(call_result["full_response"], GUARD_THRESHOLD)
        cost = (call_result["input_tokens"] / 1000 * COST_PER_1K_IN +
                call_result["output_tokens"] / 1000 * COST_PER_1K_OUT)
        total_cost += cost
        record = {
            "pair_id": row["pair_id"],
            "gold_label": row["gold_label"],
            "stratum": row.get("stratum"),
            **call_result,
            "estimated_cost_usd": round(cost, 6),
            "guard_decision": guard["decision"],
            "guard_confidence": guard["confidence"],
            "guard_applied": guard["guard_applied"],
            "guard_reason": guard["guard_reason"],
            "guard_threshold_used": GUARD_THRESHOLD,
            "guard_version": GUARD_VERSION,
        }
        records.append(record)

    finished_at = datetime.now(timezone.utc).isoformat()

    raw_path = out_dir / "raw_outputs.jsonl"
    with open(raw_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest = {
        "run_id": args.run_id,
        "mode": args.mode,
        "is_synthetic": args.mode == "dry-run",
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "n_pairs": len(test_rows),
        "n_pairs_expected": 149,
        "model_id_requested": MODEL_ID,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "top_p_passed": False,
        "auxiliary_context_used": False,
        "guard_threshold": GUARD_THRESHOLD,
        "guard_version": GUARD_VERSION,
        "system_prompt_sha256": system_prompt_hash,
        "user_prompt_template_sha256": user_template_hash,
        "frozen_test_set_sha256": "996248ac3e4a7e6dc65ac027fcca891b9e0c798282df7d2c840f13739e28aae5",
        "cache_reuse_policy": "NONE -- every pair gets a fresh call, no existing log is ever read or skipped",
        "total_estimated_cost_usd": round(total_cost, 4),
        "total_input_tokens": sum(r["input_tokens"] for r in records),
        "total_output_tokens": sum(r["output_tokens"] for r in records),
    }
    if args.mode == "dry-run":
        manifest["WARNING"] = ("SYNTHETIC DRY-RUN. Responses were generated by MockClient, "
                                "not the real Anthropic API. This run has NO evidential value "
                                "about the real model's rerun-stability and must never be "
                                "presented as such.")

    with open(out_dir / "run_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Run '{args.run_id}' complete ({args.mode}). n={len(records)}. "
          f"Output: {out_dir}")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
