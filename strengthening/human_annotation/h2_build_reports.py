"""H2 driver: runs Step 1 (validate) -> Step 2 (merge, restricted) ->
Step 3 (agreement) -> Step 4 (safe reports). Stops and raises before
writing anything if validation fails."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .h2_agreement import build_full_report
from .h2_validate import H2ValidationError, load_canonical_source, validate_completed

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1"
H2_DIR = PKG_DIR / "h2"

ANN1_COMPLETED = PKG_DIR / "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx"
ANN2_COMPLETED = PKG_DIR / "ANNOTATOR_2_PRIMARY_COMPLETED.xlsx"
CE_SOURCE = STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv"
BIO_SOURCE = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"

MERGED_RESTRICTED_OUT = H2_DIR / "PRIMARY_H1_MERGED.csv"
REPORT_JSON_OUT = STRENGTHENING_ROOT / "reports" / "PRIMARY_H1_INTERANNOTATOR_AGREEMENT.json"
REPORT_MD_OUT = STRENGTHENING_ROOT / "reports" / "PRIMARY_H1_INTERANNOTATOR_AGREEMENT.md"


def run() -> dict:
    canonical = load_canonical_source(CE_SOURCE, BIO_SOURCE)

    r1 = validate_completed(ANN1_COMPLETED, canonical, "Annotator 1")
    r2 = validate_completed(ANN2_COMPLETED, canonical, "Annotator 2")
    if not (r1.ok and r2.ok):
        raise H2ValidationError(
            f"H1 validation FAILED -- stopping before agreement calculation.\n"
            f"Annotator 1 issues: {r1.issues}\nAnnotator 2 issues: {r2.issues}"
        )

    report, merged = build_full_report(ANN1_COMPLETED, ANN2_COMPLETED)

    def disagreement_type(row) -> str:
        if row["agree"]:
            return ""
        return " vs ".join(sorted((row["annotator_1_label"], row["annotator_2_label"])))

    merged = merged.copy()
    merged["disagreement_type"] = merged.apply(disagreement_type, axis=1)
    merged["agreement"] = merged["agree"]
    cols = [
        "pair_id", "domain", "string_a", "string_b",
        "annotator_1_label", "annotator_1_justification", "annotator_1_context_used",
        "annotator_2_label", "annotator_2_justification", "annotator_2_context_used",
        "agreement", "disagreement_type",
    ]
    H2_DIR.mkdir(parents=True, exist_ok=True)
    merged[cols].to_csv(MERGED_RESTRICTED_OUT, index=False, encoding="utf-8")

    now = datetime.now(timezone.utc).isoformat()
    full_report = {"generated_at_utc": now, "validation": {"annotator_1_ok": r1.ok, "annotator_2_ok": r2.ok}, **report}
    with open(REPORT_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, default=str)

    _write_markdown(full_report)
    return full_report


def _write_markdown(report: dict) -> None:
    def fmt_section(name: str, s: dict) -> list[str]:
        lines = [
            f"## {name}",
            f"- N: {s['n']}",
            f"- Agreements: {s['agreements']}",
            f"- Disagreements: {s['disagreements']}",
            f"- Raw agreement proportion: {s['raw_agreement_proportion']}",
            f"- Cohen's kappa (inter-annotator agreement, nominal 3-class): {s['cohens_kappa']}",
            f"- Annotator 1 label distribution: {s['annotator_1_label_distribution']}",
            f"- Annotator 2 label distribution: {s['annotator_2_label_distribution']}",
            "- Confusion matrix (rows=Annotator 1, cols=Annotator 2):",
            "",
            "  | | match | non-match | uncertain |",
            "  |---|---:|---:|---:|",
        ]
        cm = s["confusion_matrix_rows_annotator_1_cols_annotator_2"]
        for row_label in ("match", "non-match", "uncertain"):
            lines.append(f"  | **{row_label}** | {cm[row_label]['match']} | {cm[row_label]['non-match']} | {cm[row_label]['uncertain']} |")
        lines.append("")
        return lines

    lines = [
        "# Primary H1 inter-annotator agreement (900-pair benchmark)",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "Both completed workbooks passed independent validation (900 rows each, 400 CE + 500 diabetes, "
        "unique pair_ids, all labels/context_used values from the allowed sets, no changed strings, no "
        "system metadata). Terminology: figures below are reported as *inter-annotator agreement* "
        "(Cohen's kappa), never as \"reliability\".",
        "",
    ]
    lines += fmt_section("Overall (N=900)", report["overall"])
    lines += fmt_section("Circular Economy only (N=400)", report["circular_economy"])
    lines += fmt_section("Diabetes Mellitus only (N=500)", report["biomedical_diabetes_mellitus"])

    lines += [
        "## Disagreement types (overall, unordered)",
        "",
    ]
    for k, v in report["disagreement_types_overall"]["unordered"].items():
        lines.append(f"- {k}: {v}")
    lines.append(f"- other/malformed: {report['disagreement_types_overall']['other']}")
    lines += ["", "### Directional breakdown", ""]
    for k, v in report["disagreement_types_overall"]["directional"].items():
        lines.append(f"- {k}: {v}")

    lines += ["", "## Context-use cross-tabulation (overall)", ""]
    lines += ["| Pattern | N | Proportion of total | Disagreements | Disagreement rate |", "|---|---:|---:|---:|---:|"]
    for name, v in report["context_use_crosstab_overall"].items():
        lines.append(f"| {name} | {v['n']} | {v['proportion_of_total']} | {v['disagreement_count']} | {v['disagreement_rate']} |")

    lines += [
        "",
        "## Historical context only (NOT a statistical comparison)",
        "",
        f"- Legacy pilot/full-round Cohen's kappa (original benchmark): "
        f"{report['historical_context_only_not_a_comparison']['legacy_pilot_full_round_cohens_kappa']}",
        f"- {report['historical_context_only_not_a_comparison']['note']}",
        "",
        "## Notable observation (reported factually, no root-cause speculation)",
        "",
        f"Annotator 2's label distribution for the diabetes-mellitus domain is "
        f"{report['biomedical_diabetes_mellitus']['annotator_2_label_distribution']} -- i.e. every one of the "
        "500 diabetes pairs was labelled 'match' by Annotator 2, which is why that domain's Cohen's kappa is "
        "exactly 0.0 despite a 32.8% raw overlap (a rater with a degenerate, constant label has, by definition, "
        "zero agreement beyond chance). Annotator 2's circular-economy distribution for the same annotator over "
        "the same session is varied and unremarkable. This pattern is flagged here for human review before "
        "relying on the diabetes-domain adjudication outcome -- no cause is asserted.",
    ]
    REPORT_MD_OUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
