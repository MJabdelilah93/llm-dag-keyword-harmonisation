"""
reparse_dev_log_v1.py
======================
PHASE 0B / TASK 4 — dev-log provenance repair, WITHOUT any new API call.

Reads results/llm_logs/dev_workflow_raw_outputs.jsonl from the historical
evidence tree (read-only) and re-applies the verified v1 G1-G4 guard logic
(copied verbatim from scripts/run_full_workflow.py, confirmed identical
during the 2026-08 audit) to each entry's *stored* full_response text.

The original historical log is never modified. This script writes a NEW,
clearly-versioned derived artefact — dev_workflow_reparsed_v1.jsonl — that
contains corrected guard/decision metadata alongside the unchanged raw
full_response text, plus explicit provenance fields per entry documenting
that no new model call was made.

Because the output still contains real Scopus-derived keyword strings
(keyword_a/keyword_b) and raw model text, it is written to a local-only,
git-ignored directory (restricted_local/), never committed to the repair
branch. Only aggregate verification numbers are written to a public,
git-tracked summary (see the companion .txt output).

Usage:
    python reparse_dev_log_v1.py --evidence-root "<path to original evidence tree>"

If --evidence-root is omitted, the V1_EVIDENCE_ROOT environment variable is
used. Neither this script nor its defaults hardcode a personal machine path.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

VALID_DECISIONS = {"match", "non_match", "uncertain"}
PARSER_VERSION = "v1_verified_guard_reparse_1.0.0"


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def apply_guard(raw_response: str, confidence_threshold: float) -> dict:
    """Verbatim v1 G1-G4 logic, copied from scripts/run_full_workflow.py."""
    result = {"decision": "uncertain", "confidence": 0.0, "justification": "",
              "guard_applied": None, "guard_reason": None}
    clean_response = _strip_markdown_fence(raw_response)
    try:
        parsed = json.loads(clean_response)
    except (json.JSONDecodeError, ValueError):
        result["guard_applied"] = "G1"
        result["guard_reason"] = "malformed_parse_failure"
        return result
    required = {"decision", "confidence", "justification"}
    if not required.issubset(parsed.keys()):
        missing = required - parsed.keys()
        result["guard_applied"] = "G2"
        result["guard_reason"] = f"malformed_missing_field:{','.join(missing)}"
        return result
    decision = str(parsed.get("decision", "")).strip().lower()
    if decision not in VALID_DECISIONS:
        result["guard_applied"] = "G3"
        result["guard_reason"] = f"invalid_decision:{decision}"
        return result
    result["decision"] = decision
    result["justification"] = str(parsed.get("justification", ""))
    try:
        conf = float(parsed.get("confidence", 0.0))
        conf = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        conf = 0.0
    result["confidence"] = conf
    if decision != "uncertain" and conf < confidence_threshold:
        result["decision"] = "uncertain"
        result["guard_applied"] = "G4"
        result["guard_reason"] = f"confidence_{conf:.3f}_below_threshold_{confidence_threshold:.3f}"
        return result
    return result


def raw_decision_of(full_response: str) -> str:
    try:
        parsed = json.loads(_strip_markdown_fence(full_response))
        rd = str(parsed.get("decision", "uncertain")).strip().lower()
        return rd if rd in VALID_DECISIONS else "uncertain"
    except Exception:
        return "uncertain"


def binary_metrics(gold, pred):
    binary_pairs = [(g, p) for g, p in zip(gold, pred) if g != "uncertain"]
    decided_pairs = [(g, p) for g, p in binary_pairs if p != "uncertain"]
    n = len(gold)
    n_unc = sum(1 for p in pred if p == "uncertain")
    coverage = (n - n_unc) / n if n else 0.0
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
    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4), "coverage": round(coverage, 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"),
                     help="Path to the historical evidence tree (contains data/, results/).")
    ap.add_argument("--output-dir", default=None,
                     help="Defaults to <repair-repo-root>/restricted_local/dev_log_repair/")
    ap.add_argument("--threshold", type=float, default=0.50,
                     help="Confidence threshold — 0.50 is the verified v1 value.")
    args = ap.parse_args()

    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set. "
                 "This script never hardcodes a personal machine path.")
    evidence_root = Path(args.evidence_root)
    dev_log_path = evidence_root / "results" / "llm_logs" / "dev_workflow_raw_outputs.jsonl"
    dev_set_path = evidence_root / "data" / "benchmark" / "dev_set.csv"
    if not dev_log_path.exists() or not dev_set_path.exists():
        sys.exit(f"ERROR: expected evidence not found under {evidence_root}")

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.output_dir) if args.output_dir else repo_root / "restricted_local" / "dev_log_repair"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_hash = hashlib.sha256(dev_log_path.read_bytes()).hexdigest()
    repair_ts = datetime.now(timezone.utc).isoformat()

    entries = []
    with open(dev_log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue

    out_path = out_dir / "dev_workflow_reparsed_v1.jsonl"
    with open(out_path, "w", encoding="utf-8") as fout:
        for e in entries:
            full_response = e.get("full_response", "")
            guard = apply_guard(full_response, args.threshold)
            raw_dec = raw_decision_of(full_response)
            repaired = {
                "pair_id": e.get("pair_id"),
                "keyword_a": e.get("keyword_a"),
                "keyword_b": e.get("keyword_b"),
                "gold_label": e.get("gold_label"),
                "full_response": full_response,  # UNCHANGED raw model text
                "model_id": e.get("model_id"),
                "timestamp_original_call": e.get("timestamp"),
                # Repaired/derived fields (this script's output, not the original log's):
                "raw_decision_reparsed": raw_dec,
                "guard_decision_reparsed": guard["decision"],
                "guard_confidence_reparsed": guard["confidence"],
                "guard_applied_reparsed": guard["guard_applied"],
                "guard_reason_reparsed": guard["guard_reason"],
                "confidence_threshold_used": args.threshold,
                # Provenance — mandatory per Phase 0B Task 4:
                "_provenance": {
                    "status": "RETROSPECTIVELY RECONSTRUCTED — derived metadata only",
                    "source_file": "results/llm_logs/dev_workflow_raw_outputs.jsonl",
                    "source_file_sha256": source_hash,
                    "repair_date_utc": repair_ts,
                    "parser_version": PARSER_VERSION,
                    "new_api_call_made": False,
                    "raw_response_unchanged": True,
                    "note": "Only derived parsing/guard metadata was reconstructed from the "
                            "unchanged, historical full_response text. The stored "
                            "guard_applied/raw_decision/guard_decision fields in the ORIGINAL "
                            "dev_workflow_raw_outputs.jsonl are known to be corrupted for all "
                            "351 valid rows (100% spurious G1 malformed_parse_failure) despite "
                            "valid underlying JSON — see docs/provenance/dev_log_repair_summary.md.",
                },
            }
            fout.write(json.dumps(repaired, ensure_ascii=False) + "\n")

    # Independent verification against dev_set.csv gold labels
    import csv
    gold_by_pair = {}
    with open(dev_set_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lbl = row["gold_label"].strip().lower()
            gold_by_pair[row["pair_id"]] = "non_match" if lbl in ("non-match", "non_match") else lbl

    aligned_gold, aligned_pred_guard, aligned_pred_raw = [], [], []
    for pid, gold in gold_by_pair.items():
        entry = next((e for e in entries if e.get("pair_id") == pid), None)
        if entry is None:
            aligned_gold.append(gold); aligned_pred_guard.append("uncertain"); aligned_pred_raw.append("uncertain")
            continue
        g = apply_guard(entry.get("full_response", ""), args.threshold)
        aligned_gold.append(gold)
        aligned_pred_guard.append(g["decision"])
        aligned_pred_raw.append(raw_decision_of(entry.get("full_response", "")))

    m_guard = binary_metrics(aligned_gold, aligned_pred_guard)
    m_raw = binary_metrics(aligned_gold, aligned_pred_raw)

    summary_lines = [
        "DEV LOG REPAIR — VERIFICATION SUMMARY (aggregate only, no keyword strings)",
        "=" * 70,
        f"Parser version: {PARSER_VERSION}",
        f"Repair date (UTC): {repair_ts}",
        f"Source file SHA-256: {source_hash}",
        f"New API call made: False",
        f"Threshold used: {args.threshold}",
        "",
        f"Reparsed dev metrics (with guard): {m_guard}",
        f"Reparsed dev metrics (no guard):   {m_raw}",
        "",
        "Expected (from Phase 0A/0B independent verification):",
        "  precision=0.9798 recall=0.9604 f1=0.9700 coverage=0.9003 threshold=0.50",
        "",
        "MATCH: " + str(m_guard.get("precision") == 0.9798 and m_guard.get("recall") == 0.9604
                        and m_guard.get("f1") == 0.97 and m_guard.get("coverage") == 0.9003),
    ]
    print("\n".join(summary_lines))

    return out_path, source_hash, repair_ts, m_guard, m_raw


if __name__ == "__main__":
    main()
