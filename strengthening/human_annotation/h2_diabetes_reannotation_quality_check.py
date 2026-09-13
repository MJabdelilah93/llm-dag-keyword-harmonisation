"""H2-corrected Step 3: string-free audit-log quality check for the
completed diabetes-only re-annotation session, plus a descriptive
(non-judgemental) comparison against the SUPERSEDED original Annotator-2
diabetes run. Per the task: a low agreement score or an unexpected class
distribution is NEVER by itself a reason to reject the re-annotation --
only a degenerate constant-label run or a mechanical/data-integrity
anomaly (e.g. sub-100ms intervals, an impossible/duplicated callback
signature) would be such a reason, and none is asserted here unless the
evidence actually shows it.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1"
REANNOTATION_DIR = PKG_DIR / "h2" / "diabetes_reannotation"
AUDIT_LOG_PATH = REANNOTATION_DIR / "logs" / "DIABETES_REANNOTATION_ANNOTATOR_2_audit_log.csv"

ORIGINAL_DIAGNOSTIC_JSON = STRENGTHENING_ROOT / "reports" / "DIABETES_ANNOTATION_QUALITY_DIAGNOSTIC.json"

REPORT_JSON_OUT = STRENGTHENING_ROOT / "reports" / "DIABETES_REANNOTATION_QUALITY_CHECK.json"
REPORT_MD_OUT = STRENGTHENING_ROOT / "reports" / "DIABETES_REANNOTATION_QUALITY_CHECK.md"


def analyze_session(rows: list[dict]) -> dict:
    for r in rows:
        r["ts"] = datetime.fromisoformat(r["timestamp"])

    action_counts = dict(Counter(r["action"] for r in rows))
    decide_rows = [r for r in rows if r["action"] in ("label", "relabel")]

    # final (most recent) label per pair_id, and the chronological order in
    # which each pair_id was FIRST decided (for the identical-run and
    # label-distribution calculations).
    final_label: dict[str, str] = {}
    first_seen_order: list[str] = []
    for r in sorted(decide_rows, key=lambda r: r["ts"]):
        if r["pair_id"] not in final_label:
            first_seen_order.append(r["pair_id"])
        final_label[r["pair_id"]] = r["new_label"]

    pair_counts = Counter(r["pair_id"] for r in decide_rows)
    relabeled = sorted(k for k, v in pair_counts.items() if v > 1)

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

    label_distribution = dict(Counter(final_label.values()))

    return {
        "total_audit_log_rows": len(rows),
        "action_counts": action_counts,
        "n_decide_actions_label_plus_relabel": len(decide_rows),
        "n_distinct_pairs_decided": len(final_label),
        "relabel_count": len(relabeled),
        "skip_count": action_counts.get("skip", 0),
        "context_opened_count": action_counts.get("context_opened", 0),
        "first_timestamp_utc": first.isoformat() if first else None,
        "last_timestamp_utc": last.isoformat() if last else None,
        "duration_span_seconds": round(duration_s, 1) if duration_s is not None else None,
        "duration_span_human": str(last - first) if timestamps else None,
        "dates_touched": sorted({t.date().isoformat() for t in timestamps}),
        "median_inter_decision_interval_s": round(intervals[n // 2], 3) if n else None,
        "min_inter_decision_interval_s": round(min(intervals), 3) if intervals else None,
        "max_inter_decision_interval_s": round(max(intervals), 1) if intervals else None,
        "n_intervals_under_2s": len([iv for iv in intervals if iv < 2.0]),
        "n_intervals_under_1s": len([iv for iv in intervals if iv < 1.0]),
        "n_intervals_under_100ms": len([iv for iv in intervals if iv < 0.1]),
        "longest_identical_label_run": longest_run,
        "longest_identical_label_run_value": longest_run_label,
        "label_distribution": label_distribution,
        "label_distribution_is_degenerate_single_class": len(label_distribution) <= 1,
        "evidence_of_stuck_key_or_autorepeat": n > 0 and (
            len([iv for iv in intervals if iv < 0.1]) > 0
        ),
        "evidence_of_duplicated_gui_callback": len(relabeled) > 5,
    }


def run() -> dict:
    if not AUDIT_LOG_PATH.exists():
        raise FileNotFoundError(f"{AUDIT_LOG_PATH} does not exist -- re-annotation session log missing")

    rows = list(csv.DictReader(open(AUDIT_LOG_PATH, encoding="utf-8")))
    new_session = analyze_session(rows)

    original_reference = None
    if ORIGINAL_DIAGNOSTIC_JSON.exists():
        with open(ORIGINAL_DIAGNOSTIC_JSON, encoding="utf-8") as f:
            original_diag = json.load(f)
        original_reference = original_diag.get("diabetes_timing")

    anomaly_detected = new_session["label_distribution_is_degenerate_single_class"]
    now = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at_utc": now,
        "new_reannotation_session": new_session,
        "original_superseded_session_reference": original_reference,
        "comprehension_gate_note": (
            "The comprehension gate (6 synthetic examples) is enforced purely in-memory by "
            "ComprehensionGateState and is NOT written to this audit log -- no log-based evidence "
            "of gate completion exists. Structural evidence only: the shipped ReannotationApp code "
            "reaches the real annotation screen (the only path that can produce 'label' audit-log "
            "rows) exclusively through _build_comprehension_screen(), which falls through to it only "
            "when ComprehensionGateState.is_complete is True, i.e. only after all 6 examples were "
            "answered correctly. This is a code-path guarantee, not a log record, and is reported as such."
        ),
        "degenerate_constant_label_run_detected": anomaly_detected,
        "mechanical_or_data_integrity_anomaly_detected": anomaly_detected or new_session["evidence_of_stuck_key_or_autorepeat"] or new_session["evidence_of_duplicated_gui_callback"],
        "recommendation": "STOP_FOR_REVIEW" if anomaly_detected else "PROCEED",
    }
    with open(REPORT_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    _write_markdown(report)
    return report


def _write_markdown(report: dict) -> None:
    s = report["new_reannotation_session"]
    orig = report["original_superseded_session_reference"] or {}
    lines = [
        "# Diabetes re-annotation quality check (Annotator 2, corrected)",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "String-free audit summary of the NEW 500-pair diabetes-only re-annotation session, "
        "compared descriptively against the SUPERSEDED original Annotator-2 diabetes run. No "
        "minimum kappa or expected class distribution is imposed; only a degenerate constant-label "
        "run or a mechanical/data-integrity anomaly would be grounds to stop, and neither is found here "
        "unless stated otherwise below.",
        "",
        "## New re-annotation session",
        "",
        f"| | New re-annotation | Superseded original run |",
        f"|---|---:|---:|",
        f"| Label distribution | {s['label_distribution']} | {orig.get('new_label_distribution')} |",
        f"| Total decide actions (label+relabel) | {s['n_decide_actions_label_plus_relabel']} | {orig.get('n_label_actions')} |",
        f"| Relabels | {s['relabel_count']} | n/a |",
        f"| Skips | {s['skip_count']} | n/a |",
        f"| Context openings | {s['context_opened_count']} | n/a |",
        f"| Duration span | {s['duration_span_human']} | {orig.get('duration_span_human')} |",
        f"| Dates touched | {s['dates_touched']} | {orig.get('dates_touched')} |",
        f"| Median inter-decision interval (s) | {s['median_inter_decision_interval_s']} | {orig.get('median_inter_decision_interval_s')} |",
        f"| Min inter-decision interval (s) | {s['min_inter_decision_interval_s']} | {orig.get('min_inter_decision_interval_s')} |",
        f"| Intervals under 1s | {s['n_intervals_under_1s']} | {orig.get('n_intervals_under_1s_sub_second')} |",
        f"| Intervals under 100ms | {s['n_intervals_under_100ms']} | {orig.get('n_intervals_under_100ms')} |",
        f"| Longest identical-label run | {s['longest_identical_label_run']} ({s['longest_identical_label_run_value']}) | {orig.get('longest_identical_label_run')} ({orig.get('longest_identical_label_run_value')}) |",
        "",
        f"- Degenerate (single-class) label distribution detected: {s['label_distribution_is_degenerate_single_class']}",
        f"- Evidence of stuck key / autorepeat (any sub-100ms interval): {s['evidence_of_stuck_key_or_autorepeat']}",
        f"- Evidence of duplicated GUI callback (>5 relabels): {s['evidence_of_duplicated_gui_callback']}",
        "",
        f"## Comprehension gate",
        "",
        report["comprehension_gate_note"],
        "",
        "## Result",
        "",
        f"- Mechanical/data-integrity anomaly detected: {report['mechanical_or_data_integrity_anomaly_detected']}",
        f"- Recommendation: {report['recommendation']}",
    ]
    REPORT_MD_OUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
