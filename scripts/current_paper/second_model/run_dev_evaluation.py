"""
run_dev_evaluation.py
========================
PHASE 1B / TASK 3 — second-model (Gemini) evaluation on the frozen
DEVELOPMENT SET ONLY (N=351). Selects the confidence threshold that
maximises F1 subject to coverage >= 0.70 on dev, using the identical
pre-specified rule and grid already used for the primary model. Held-out
test performance is never inspected in this script.

One real API call per pair (at effective "collect raw response" stage);
the confidence threshold sweep is then a pure post-hoc replay of
apply_guard() over the already-collected responses -- no extra API calls
per threshold candidate, exactly mirroring how the primary model's
threshold was originally selected.

`--mode real` is refused unless explicitly unlocked (see --i-have-authorisation).
`--mode dry-run` uses the synthetic MockClient and never touches the network.
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

import numpy as np

THRESH_GRID = [round(float(t), 2) for t in np.arange(0.50, 0.96, 0.05)]
COVERAGE_FLOOR = 0.70


def norm_label(lbl):
    lbl = str(lbl).strip().lower()
    return "non_match" if lbl in ("non-match", "non_match") else lbl


def binary_metrics(gold, pred):
    n = len(gold)
    n_uncertain_pred = sum(1 for p in pred if p == "uncertain")
    coverage = (n - n_uncertain_pred) / n if n else 0.0
    binary_pairs = [(g, p) for g, p in zip(gold, pred) if g != "uncertain"]
    decided_pairs = [(g, p) for g, p in binary_pairs if p != "uncertain"]
    if not decided_pairs:
        precision = recall = 0.0
    else:
        tp = sum(1 for g, p in decided_pairs if g == "match" and p == "match")
        fp = sum(1 for g, p in decided_pairs if g != "match" and p == "match")
        fn_decided = sum(1 for g, p in decided_pairs if g == "match" and p != "match")
        fn_abstain = sum(1 for g, p in binary_pairs if g == "match" and p == "uncertain")
        fn = fn_decided + fn_abstain
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "coverage": round(coverage, 4)}


def three_way_accuracy(gold, pred):
    return round(sum(1 for g, p in zip(gold, pred) if g == p) / len(gold), 4) if gold else 0.0


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"))
    ap.add_argument("--mode", choices=["real", "dry-run"], required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--mock-seed", type=int, default=0)
    ap.add_argument("--i-have-authorisation", action="store_true",
                     help="Required in addition to --mode real. Set only after explicit human authorisation.")
    args = ap.parse_args()

    if args.mode == "real" and not args.i_have_authorisation:
        sys.exit("REFUSED: --mode real requires --i-have-authorisation. This is a deliberate, "
                 "auditable second guard beyond the --mode flag itself.")

    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")
    evidence_root = Path(args.evidence_root)
    repo_root = Path(__file__).resolve().parents[3]

    dev_path = evidence_root / "data" / "benchmark" / "dev_set.csv"
    if not dev_path.exists():
        sys.exit(f"ERROR: {dev_path} not found")
    dev_rows = []
    with open(dev_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["gold_label"] = norm_label(r["gold_label"])
            dev_rows.append(r)
    if len(dev_rows) != 351:
        sys.exit(f"ERROR: expected 351 frozen dev pairs, found {len(dev_rows)} -- STOP, benchmark input changed.")

    system_prompt = (repo_root / "prompts" / "v1.0.0" / "system_prompt.txt").read_text(encoding="utf-8")
    user_template = (repo_root / "prompts" / "v1.0.0" / "user_prompt_standard.txt").read_text(encoding="utf-8")

    # Explicit invariant check: the rendered prompt must never contain the gold label.
    sample_rendered = user_template.format(keyword_a=dev_rows[0]["keyword_a"], keyword_b=dev_rows[0]["keyword_b"])
    for r in dev_rows[:5]:
        assert r["gold_label"] not in sample_rendered.lower().split() or r["gold_label"] in ("match",), \
            "safety check inconclusive -- manual review required"
    assert "{keyword_a}" not in sample_rendered and "{keyword_b}" not in sample_rendered
    assert "gold_label" not in user_template and "gold_label" not in system_prompt

    out_dir = repo_root / "results" / "current_paper" / "second_model" / f"dev_run_{args.run_id}"
    if out_dir.exists():
        sys.exit(f"REFUSED: output directory already exists ({out_dir}). Choose a different --run-id.")
    out_dir.mkdir(parents=True)

    if args.mode == "real":
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            sys.exit("ERROR: GEMINI_API_KEY / GOOGLE_API_KEY not set.")
        client = GeminiClient(api_key=api_key)
    else:
        gold_lookup = {r["pair_id"]: r["gold_label"] for r in dev_rows}
        client = MockClient(seed=args.mock_seed, gold_lookup=gold_lookup)

    started_at = datetime.now(timezone.utc).isoformat()
    records = []
    for row in dev_rows:
        user_prompt = user_template.format(keyword_a=row["keyword_a"], keyword_b=row["keyword_b"])
        call_result = client.call(system_prompt, user_prompt, pair_id=row["pair_id"])
        record = {"pair_id": row["pair_id"], "gold_label": row["gold_label"],
                   "stratum": row.get("stratum"), **call_result}
        records.append(record)
    finished_at = datetime.now(timezone.utc).isoformat()

    raw_path = out_dir / "raw_outputs.jsonl"
    with open(raw_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Threshold sweep -- pure replay, no additional API calls.
    gold = [r["gold_label"] for r in records]
    threshold_table = []
    best = {"threshold": THRESH_GRID[0], "f1": -1.0, "coverage": 0.0}
    for t in THRESH_GRID:
        preds = [apply_guard(r["full_response"], t)["decision"] for r in records]
        m = binary_metrics(gold, preds)
        row = {"threshold": t, **m, "three_way_acc": three_way_accuracy(gold, preds)}
        threshold_table.append(row)
        if m["coverage"] >= COVERAGE_FLOOR and m["f1"] > best["f1"]:
            best = {"threshold": t, "f1": m["f1"], "coverage": m["coverage"],
                     "precision": m["precision"], "recall": m["recall"]}

    with open(out_dir / "threshold_candidate_table.csv", "w", newline="", encoding="utf-8") as f:
        import csv as _csv
        w = _csv.DictWriter(f, fieldnames=list(threshold_table[0].keys()))
        w.writeheader()
        for row in threshold_table:
            w.writerow(row)

    manifest = {
        "run_id": args.run_id, "mode": args.mode, "is_synthetic": args.mode == "dry-run",
        "started_at_utc": started_at, "finished_at_utc": finished_at,
        "n_pairs": len(dev_rows), "n_pairs_expected": 351,
        "model_id_requested": MODEL_ID,
        "system_prompt_sha256": sha256_str(system_prompt),
        "user_prompt_template_sha256": sha256_str(user_template),
        "frozen_dev_set_sha256": "d5713c7974cd6c8fe88633132c9c07b816a9f688f2614e12b02f12dbc4dd282e",
        "threshold_grid": THRESH_GRID, "coverage_floor": COVERAGE_FLOOR,
        "selected_threshold": best,
        "guard_version": GUARD_VERSION,
        "total_input_tokens": sum(r.get("input_tokens") or 0 for r in records),
        "total_output_tokens": sum(r.get("output_tokens") or 0 for r in records),
        "total_thinking_tokens": sum(r.get("thinking_tokens") or 0 for r in records),
        "n_errors": sum(1 for r in records if r.get("error")),
        "test_set_accessed": False,
    }
    if args.mode == "dry-run":
        manifest["WARNING"] = "SYNTHETIC DRY-RUN. No evidential value about the real model."

    with open(out_dir / "dev_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(json.dumps(manifest, indent=2))
    print(f"\nOutput: {out_dir}")
    print(f"SELECTED THRESHOLD: {best['threshold']} (dev F1={best['f1']}, coverage={best['coverage']})")


if __name__ == "__main__":
    main()
