"""Parts E/F/G: R1 vs R2 retrieval-annotation protocol workload, escalation
threshold planning, and the final Pareto-reasonable design comparison.
Consumes strengthening/reports/retrieval_audit_burden_analysis.json (Part
D, already regenerated with scenarios A-H); does not re-touch any audit
CSV.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]

AUDIT_FRACTIONS = [0.20, 0.30, 0.40]
ESCALATION_THRESHOLDS = [0.01, 0.02, 0.05]
ANNOTATION_TIME_SECONDS = [15, 30, 45]
PRIMARY_BENCHMARK_PAIRS = 900  # 400 CE + 500 biomedical
PRIMARY_BENCHMARK_JUDGEMENTS = PRIMARY_BENCHMARK_PAIRS * 2  # two independent annotators


def r1_judgements(total_rows: int) -> int:
    return total_rows * 2


def r2_judgements(total_rows: int, in_pool_rows: int, outside_pool_rows: int, audit_fraction: float) -> dict:
    ann1 = total_rows  # annotator 1 labels every row exactly once
    ann2_outside = outside_pool_rows  # annotator 2 re-labels all outside-pool rows
    ann2_audit_sample = math.ceil(in_pool_rows * audit_fraction)  # stratified random sample of in-pool rows
    ann2 = ann2_outside + ann2_audit_sample
    return {
        "annotator_1_judgements": ann1,
        "annotator_2_judgements": ann2,
        "annotator_2_in_pool_audit_sample_size": ann2_audit_sample,
        "total_judgements": ann1 + ann2,
        "double_coded_rows": ann2,  # rows seen by both annotators -- basis for agreement estimation
        "singly_coded_rows": total_rows - ann2_outside - ann2_audit_sample if total_rows >= ann2 else max(total_rows - ann2, 0),
    }


def escalation_table(in_pool_rows: int) -> dict:
    out = {}
    for frac in AUDIT_FRACTIONS:
        sample_size = math.ceil(in_pool_rows * frac)
        out[f"{int(frac*100)}pct_audit_sample_size"] = {
            f"{int(t*100)}pct_threshold_triggering_error_count": math.ceil(sample_size * t) for t in ESCALATION_THRESHOLDS
        }
        out[f"{int(frac*100)}pct_audit_sample_size"]["sample_size"] = sample_size
    return out


def hours(judgements: int) -> dict:
    return {f"{s}s_per_judgement": round(judgements * s / 3600, 2) for s in ANNOTATION_TIME_SECONDS}


def main():
    burden = json.load(open(STRENGTHENING_ROOT / "reports" / "retrieval_audit_burden_analysis.json"))
    scenarios = burden["scenarios_definition"]

    design_options = {}
    for name in scenarios:
        ce = burden["circular_economy"][name]
        bio = burden["biomedical"][name]
        total_rows = ce["total_rows_requiring_judgement"] + bio["total_rows_requiring_judgement"]
        in_pool = ce["deduplicated_annotation_rows_in_pool"] + bio["deduplicated_annotation_rows_in_pool"]
        outside_pool = ce["outside_pool_rows"] + bio["outside_pool_rows"]

        r1 = {"total_judgements": r1_judgements(total_rows), "hours": hours(r1_judgements(total_rows))}
        r2 = {}
        for frac in AUDIT_FRACTIONS:
            res = r2_judgements(total_rows, in_pool, outside_pool, frac)
            res["hours"] = hours(res["total_judgements"])
            r2[f"{int(frac*100)}pct_audit"] = res

        design_options[name] = {
            "seed_count_ce": ce["seed_count"],
            "seed_count_bio": bio["seed_count"],
            "total_rows": total_rows,
            "in_pool_rows": in_pool,
            "outside_pool_rows": outside_pool,
            "retention_pct_ce": ce["candidate_retention_pct_of_full_design"],
            "retention_pct_bio": bio["candidate_retention_pct_of_full_design"],
            "retention_pct_by_band_ce": ce["candidate_retention_pct_by_difficulty_band"],
            "R1_full_double_annotation": r1,
            "R2_primary_plus_blinded_audit": r2,
            "escalation_planning": escalation_table(in_pool),
        }

    # Combined with fixed primary-benchmark workload
    combined_with_benchmark = {}
    for name, d in design_options.items():
        combined_with_benchmark[name] = {
            "benchmark_judgements": PRIMARY_BENCHMARK_JUDGEMENTS,
            "R1_retrieval_judgements": d["R1_full_double_annotation"]["total_judgements"],
            "R1_combined_judgements": PRIMARY_BENCHMARK_JUDGEMENTS + d["R1_full_double_annotation"]["total_judgements"],
            "R1_combined_hours": {
                k: round(PRIMARY_BENCHMARK_JUDGEMENTS * int(k.split("s_per_judgement")[0]) / 3600 + v, 2)
                for k, v in d["R1_full_double_annotation"]["hours"].items()
            },
            "R2_30pct_retrieval_judgements": d["R2_primary_plus_blinded_audit"]["30pct_audit"]["total_judgements"],
            "R2_30pct_combined_judgements": PRIMARY_BENCHMARK_JUDGEMENTS + d["R2_primary_plus_blinded_audit"]["30pct_audit"]["total_judgements"],
        }

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "primary_benchmark_workload": {
            "pairs": PRIMARY_BENCHMARK_PAIRS,
            "annotators": 2,
            "judgements": PRIMARY_BENCHMARK_JUDGEMENTS,
            "note": "adjudication time NOT included -- depends on disagreement rate, reported separately as a formula: adjudicated_pairs = pairs * disagreement_rate; each needs 1 additional adjudicator judgement",
        },
        "protocol_definitions": {
            "R1": "Two independent annotators label every retrieval-audit row (full double annotation). NOT proposed as a replacement for the primary 400+500 benchmark's own two-annotator+adjudicator process, which is unchanged.",
            "R2": "Annotator 1 independently labels every retrieval-audit row (single pass). Annotator 2 remains blinded to annotator 1's labels, labels ALL outside-pool rows, and labels a PRE-SPECIFIED stratified random sample (by pair_id/domain/route/difficulty-band, selected BEFORE annotator 1's labels are seen) of in-pool rows at a fixed audit fraction. R2 is NOT equivalent to full double annotation -- it is a quality-audited secondary validation design with a smaller double-coded subset used to estimate agreement and residual risk on the singly-coded remainder.",
        },
        "design_options": design_options,
        "combined_with_primary_benchmark": combined_with_benchmark,
    }

    out_json = STRENGTHENING_ROOT / "reports" / "final_annotation_design_options.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Wrote {out_json}")

    # Markdown summary (FULL, E, REDUCED-1, H as representative rows; full data in JSON)
    lines = [
        "# Final annotation design options",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "## Primary benchmark workload (fixed, unaffected by retrieval-audit design)",
        f"- {PRIMARY_BENCHMARK_PAIRS} pairs (400 CE + 500 biomedical) x 2 independent annotators = **{PRIMARY_BENCHMARK_JUDGEMENTS} judgements**",
        "- Adjudication time NOT included above -- it depends on the (unknown until annotation occurs) disagreement rate: "
        "each disagreeing pair needs one additional adjudicator judgement, i.e. adjudication_judgements = 900 x disagreement_rate.",
        "",
        "## Protocol definitions",
        f"- **R1**: {report['protocol_definitions']['R1']}",
        f"- **R2**: {report['protocol_definitions']['R2']}",
        "",
        "## R1 vs R2 workload, all 8 retrieval-audit scenarios (combined CE+biomedical)",
        "| Scenario | Total rows | R1 judgements | R2-20% judgements | R2-30% judgements | R2-40% judgements |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, d in design_options.items():
        lines.append(
            f"| {name} | {d['total_rows']} | {d['R1_full_double_annotation']['total_judgements']} | "
            f"{d['R2_primary_plus_blinded_audit']['20pct_audit']['total_judgements']} | "
            f"{d['R2_primary_plus_blinded_audit']['30pct_audit']['total_judgements']} | "
            f"{d['R2_primary_plus_blinded_audit']['40pct_audit']['total_judgements']} |"
        )
    lines += [
        "",
        "## Escalation-threshold planning (example: FULL scenario, in-pool rows = "
        f"{design_options['FULL']['in_pool_rows']})",
        "Audited-error counts that would trigger escalation to a larger second-annotator sample, at each "
        "candidate threshold. Thresholds are NOT chosen here -- these are planning tables only.",
        "",
        "| Audit fraction | Sample size | 1% threshold (errors) | 2% threshold | 5% threshold |",
        "|---|---:|---:|---:|---:|",
    ]
    for frac_key, vals in design_options["FULL"]["escalation_planning"].items():
        lines.append(
            f"| {frac_key.split('_')[0]} | {vals['sample_size']} | {vals['1pct_threshold_triggering_error_count']} | "
            f"{vals['2pct_threshold_triggering_error_count']} | {vals['5pct_threshold_triggering_error_count']} |"
        )
    lines += [
        "",
        "(Escalation tables for all 8 scenarios are in the JSON companion file, key `design_options.<SCENARIO>.escalation_planning`.)",
        "",
        "## Combined workload: primary benchmark + retrieval audit (R1, hours)",
        "| Scenario | Combined judgements (R1) | 15s hrs | 30s hrs | 45s hrs |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, d in combined_with_benchmark.items():
        lines.append(
            f"| {name} | {d['R1_combined_judgements']} | {d['R1_combined_hours']['15s_per_judgement']} | "
            f"{d['R1_combined_hours']['30s_per_judgement']} | {d['R1_combined_hours']['45s_per_judgement']} |"
        )
    lines += [
        "",
        "## Agreement estimation, adjudication, and escalation procedure (R2)",
        "1. **Inter-annotator agreement** on the double-coded subset (annotator 2's outside-pool + audit-sample rows): "
        "compute Cohen's kappa (three-way: match/non-match/uncertain) exactly as already implemented in "
        "`strengthening/metrics/three_way.py` / a pairwise-agreement helper, restricted to the double-coded rows.",
        "2. **Adjudicate all disagreements** within the double-coded subset via the same third-adjudicator process "
        "used for the primary benchmark (no new process invented).",
        "3. **Residual false-negative risk in singly-coded rows**: use the disagreement/positive-miss rate observed "
        "in the double-coded sample as a point estimate (with a binomial/Wilson confidence interval, given the "
        "sample size) for the error rate in the singly-coded remainder -- report this as an estimated range, not a "
        "point guarantee.",
        "4. **Escalation trigger**: if the audited disagreement or positive-miss rate in the double-coded sample "
        "exceeds a pre-specified threshold (candidates: 1%/2%/5%, see table above -- ChatGPT/the user selects one, "
        "not decided here), escalate by increasing the audit fraction (e.g. 20% -> 40%) or moving to full R1 "
        "double annotation for the affected scenario/domain.",
        "",
        "R2 is a quality-audited secondary validation design, NOT claimed equivalent to full double annotation.",
    ]
    out_md = STRENGTHENING_ROOT / "reports" / "final_annotation_design_options.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
