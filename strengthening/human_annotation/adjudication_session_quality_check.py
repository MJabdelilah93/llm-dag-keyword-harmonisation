"""Gold-freeze Step 3: string-free audit-log quality check for the
completed CORRECTED adjudication session. No minimum-distribution or
minimum-duration requirement is imposed; only a sub-100ms/obvious
automated-repeat signature, or the completed file existing before all
rows had a valid label, would be grounds to stop for review.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1"
CORRECTED_DIR = PKG_DIR / "h2" / "corrected"
AUDIT_LOG_PATH = CORRECTED_DIR / "logs" / "PRIMARY_ADJUDICATION_CORRECTED_audit_log.csv"

REPORT_JSON_OUT = STRENGTHENING_ROOT / "reports" / "PRIMARY_ADJUDICATION_SESSION_QUALITY_CHECK.json"
REPORT_MD_OUT = STRENGTHENING_ROOT / "reports" / "PRIMARY_ADJUDICATION_SESSION_QUALITY_CHECK.md"


def analyze_session(rows: list[dict]) -> dict:
    for r in rows:
        r["ts"] = datetime.fromisoformat(r["timestamp"])

    action_counts = dict(Counter(r["action"] for r in rows))
    decide_rows = [r for r in rows if r["action"] in ("label", "relabel")]

    final_label: dict[str, str] = {}
    first_seen_order: list[str] = []
    for r in sorted(decide_rows, key=lambda r: r["ts"]):
        if r["pair_id"] not in final_label:
            first_seen_order.append(r["pair_id"])
        final_label[r["pair_id"]] = r["new_label"]

    pair_counts = Counter(r["pair_id"] for r in decide_rows)
    relabeled_or_reconfirmed = sorted(k for k, v in pair_counts.items() if v > 1)

    timestamps = sorted(r["ts"] for r in decide_rows)
    first, last = (timestamps[0], timestamps[-1]) if timestamps else (None, None)
    duration_s = (last - first).total_seconds() if timestamps else None
    intervals = sorted((timestamps[i] - timestamps[i - 1]).total_seconds() for i in range(1, len(timestamps)))
    n = len(intervals)

    longest_run, longest_run_label, cur_run, cur_label = 0, None, 0, None
    for pid in first_seen_order:
        lbl = final_label[pid]
        if lbl == cur_label:
            cur_run += 1
        else:
            cur_label, cur_run = lbl, 1
        if cur_run > longest_run:
            longest_run, longest_run_label = cur_run, cur_label

    return {
        "total_audit_log_rows": len(rows),
        "action_counts": action_counts,
        "n_decide_actions_label_plus_relabel": len(decide_rows),
        "n_distinct_pairs_decided": len(final_label),
        "relabel_or_reconfirm_count": len(relabeled_or_reconfirmed),
        "skip_count": action_counts.get("skip", 0),
        "context_opened_count": action_counts.get("context_opened", 0),
        "first_timestamp_utc": first.isoformat() if first else None,
        "last_timestamp_utc": last.isoformat() if last else None,
        "duration_span_seconds": round(duration_s, 1) if duration_s is not None else None,
        "duration_span_human": str(last - first) if timestamps else None,
        "median_inter_decision_interval_s": round(intervals[n // 2], 3) if n else None,
        "min_inter_decision_interval_s": round(min(intervals), 3) if intervals else None,
        "max_inter_decision_interval_s": round(max(intervals), 1) if intervals else None,
        "n_intervals_under_1s": len([iv for iv in intervals if iv < 1.0]),
        "n_intervals_under_100ms": len([iv for iv in intervals if iv < 0.1]),
        "longest_identical_label_run": longest_run,
        "longest_identical_label_run_value": longest_run_label,
        "final_label_distribution": dict(Counter(final_label.values())),
        "evidence_of_stuck_key_or_autorepeat": n > 0 and len([iv for iv in intervals if iv < 0.1]) > 0,
        "evidence_of_duplicated_gui_callback": len(relabeled_or_reconfirmed) > 10,
    }


def run(completed_path: Path, n_expected_rows: int = 286) -> dict:
    if not AUDIT_LOG_PATH.exists():
        raise FileNotFoundError(f"{AUDIT_LOG_PATH} does not exist -- adjudication session log missing")

    rows = list(csv.DictReader(open(AUDIT_LOG_PATH, encoding="utf-8")))
    session = analyze_session(rows)

    # completed-file-only-after-all-valid-labels is a structural code
    # guarantee (AdjudicationSession.write_completed_if_done only writes
    # when is_complete() is True for every row), verified here by the fact
    # that the completed file exists with exactly n_expected_rows non-blank
    # adjudicated labels -- checked independently in the validation step,
    # not re-derived here from the log (the log does not record file writes).
    completed_file_exists = Path(completed_path).exists()

    anomaly_detected = session["evidence_of_stuck_key_or_autorepeat"] or session["evidence_of_duplicated_gui_callback"]
    now = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at_utc": now,
        "session": session,
        "completed_file_exists": completed_file_exists,
        "completed_file_note": (
            "AdjudicationSession.write_completed_if_done() only writes the completed file once every row has a "
            "non-blank adjudicated_label (code guarantee, unit-tested); this is verified independently in the "
            "mechanical validation step by checking every row of the completed file has a valid label."
        ),
        "mechanical_anomaly_detected": anomaly_detected,
        "recommendation": "STOP_FOR_REVIEW" if anomaly_detected else "PROCEED",
    }
    with open(REPORT_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    _write_markdown(report)
    return report


def _write_markdown(report: dict) -> None:
    s = report["session"]
    lines = [
        "# Corrected primary adjudication session quality check",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "String-free audit-log summary of the completed corrected (per-row-anonymised) adjudication session. "
        "No minimum duration or distribution is imposed; only a sub-100ms/automated-repeat signature would be "
        "grounds to stop for review.",
        "",
        f"- Total adjudication decisions (label+relabel/reconfirm): {s['n_decide_actions_label_plus_relabel']}",
        f"- Distinct pairs decided: {s['n_distinct_pairs_decided']}",
        f"- Relabels/reconfirms: {s['relabel_or_reconfirm_count']}",
        f"- Skips: {s['skip_count']}",
        f"- Context openings: {s['context_opened_count']}",
        f"- Session span: {s['duration_span_human']} ({s['first_timestamp_utc']} to {s['last_timestamp_utc']})",
        f"- Median inter-decision interval (s): {s['median_inter_decision_interval_s']}",
        f"- Min inter-decision interval (s): {s['min_inter_decision_interval_s']}",
        f"- Intervals under 100ms: {s['n_intervals_under_100ms']}",
        f"- Longest identical-label run: {s['longest_identical_label_run']} ({s['longest_identical_label_run_value']})",
        f"- Final adjudicated label distribution: {s['final_label_distribution']}",
        "",
        f"- Evidence of stuck key / autorepeat: {s['evidence_of_stuck_key_or_autorepeat']}",
        f"- Evidence of duplicated GUI callback (>10 relabels/reconfirms): {s['evidence_of_duplicated_gui_callback']}",
        f"- Completed file present: {report['completed_file_exists']}",
        f"- {report['completed_file_note']}",
        "",
        "## Result",
        "",
        f"- Mechanical anomaly detected: {report['mechanical_anomaly_detected']}",
        f"- Recommendation: {report['recommendation']}",
    ]
    REPORT_MD_OUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run(CORRECTED_DIR / "PRIMARY_ADJUDICATION_CORRECTED_COMPLETED.xlsx")
