"""
run_test_evaluation.py
=========================
PHASE 1B / TASK 4 — second-model (Gemini) evaluation on the frozen
HELD-OUT TEST SET, exactly once, using the threshold already frozen by
run_dev_evaluation.py. Refuses to run without an explicit
--frozen-threshold value AND a --dev-manifest reference for provenance;
refuses to run twice into the same --run-id (immutability); refuses
--mode real without --i-have-authorisation.
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
from guard_v1 import apply_guard, GUARD_VERSION
from llm_client import GeminiClient, MockClient, MODEL_ID


def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    return "non_match" if lbl in ("non-match", "non_match") else lbl


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"))
    ap.add_argument("--mode", choices=["real", "dry-run"], required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--frozen-threshold", type=float, required=True)
    ap.add_argument("--dev-manifest", required=True, help="Path to the dev_manifest.json that selected this threshold")
    ap.add_argument("--mock-seed", type=int, default=1)
    ap.add_argument("--i-have-authorisation", action="store_true")
    args = ap.parse_args()

    if args.mode == "real" and not args.i_have_authorisation:
        sys.exit("REFUSED: --mode real requires --i-have-authorisation.")

    dev_manifest_path = Path(args.dev_manifest)
    if not dev_manifest_path.exists():
        sys.exit(f"ERROR: --dev-manifest not found: {dev_manifest_path}")
    dev_manifest = json.loads(dev_manifest_path.read_text(encoding="utf-8"))
    if dev_manifest.get("test_set_accessed"):
        sys.exit("REFUSED: the referenced dev manifest claims test_set_accessed=true -- "
                 "threshold selection must never have seen the test set.")
    if abs(dev_manifest["selected_threshold"]["threshold"] - args.frozen_threshold) > 1e-9:
        sys.exit(f"REFUSED: --frozen-threshold ({args.frozen_threshold}) does not match the "
                 f"dev manifest's selected threshold ({dev_manifest['selected_threshold']['threshold']}).")

    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")
    evidence_root = Path(args.evidence_root)
    repo_root = Path(__file__).resolve().parents[3]

    test_path = evidence_root / "data" / "benchmark" / "test_set.csv"
    if not test_path.exists():
        sys.exit(f"ERROR: {test_path} not found")
    test_rows = []
    with open(test_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["gold_label"] = norm_label(r["gold_label"])
            test_rows.append(r)
    if len(test_rows) != 149:
        sys.exit(f"ERROR: expected 149 frozen test pairs, found {len(test_rows)} -- STOP.")

    system_prompt = (repo_root / "prompts" / "v1.0.0" / "system_prompt.txt").read_text(encoding="utf-8")
    user_template = (repo_root / "prompts" / "v1.0.0" / "user_prompt_standard.txt").read_text(encoding="utf-8")

    out_dir = repo_root / "results" / "current_paper" / "second_model" / f"test_run_{args.run_id}"
    if out_dir.exists():
        sys.exit(f"REFUSED: output directory already exists ({out_dir}). Choose a different --run-id.")
    out_dir.mkdir(parents=True)

    if args.mode == "real":
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            sys.exit("ERROR: GEMINI_API_KEY / GOOGLE_API_KEY not set.")
        client = GeminiClient(api_key=api_key)
    else:
        gold_lookup = {r["pair_id"]: r["gold_label"] for r in test_rows}
        client = MockClient(seed=args.mock_seed, gold_lookup=gold_lookup)

    started_at = datetime.now(timezone.utc).isoformat()
    records = []
    for row in test_rows:
        user_prompt = user_template.format(keyword_a=row["keyword_a"], keyword_b=row["keyword_b"])
        call_result = client.call(system_prompt, user_prompt, pair_id=row["pair_id"])
        guard = apply_guard(call_result["full_response"], args.frozen_threshold)
        record = {"pair_id": row["pair_id"], "gold_label": row["gold_label"], "stratum": row.get("stratum"),
                   **call_result,
                   "guard_decision": guard["decision"], "guard_confidence": guard["confidence"],
                   "guard_applied": guard["guard_applied"], "guard_reason": guard["guard_reason"],
                   "guard_threshold_used": args.frozen_threshold, "guard_version": GUARD_VERSION}
        records.append(record)
    finished_at = datetime.now(timezone.utc).isoformat()

    raw_path = out_dir / "raw_outputs.jsonl"
    with open(raw_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest = {
        "run_id": args.run_id, "mode": args.mode, "is_synthetic": args.mode == "dry-run",
        "started_at_utc": started_at, "finished_at_utc": finished_at,
        "n_pairs": len(test_rows), "n_pairs_expected": 149,
        "model_id_requested": MODEL_ID,
        "frozen_threshold_used": args.frozen_threshold,
        "dev_manifest_reference": str(dev_manifest_path),
        "system_prompt_sha256": sha256_str(system_prompt),
        "user_prompt_template_sha256": sha256_str(user_template),
        "frozen_test_set_sha256": "996248ac3e4a7e6dc65ac027fcca891b9e0c798282df7d2c840f13739e28aae5",
        "guard_version": GUARD_VERSION,
        "total_input_tokens": sum(r.get("input_tokens") or 0 for r in records),
        "total_output_tokens": sum(r.get("output_tokens") or 0 for r in records),
        "total_thinking_tokens": sum(r.get("thinking_tokens") or 0 for r in records),
        "n_errors": sum(1 for r in records if r.get("error")),
        "this_test_set_may_only_be_accessed_once": True,
    }
    if args.mode == "dry-run":
        manifest["WARNING"] = "SYNTHETIC DRY-RUN. No evidential value about the real model."

    with open(out_dir / "test_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(json.dumps(manifest, indent=2))
    print(f"\nOutput: {out_dir}")


if __name__ == "__main__":
    main()
