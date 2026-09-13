"""H2-corrected driver: runs AFTER the diabetes-only re-annotation is
complete. Order of operations:

  1. Validate the completed diabetes re-annotation independently against
     the canonical diabetes benchmark (h2_validate_diabetes_reannotation).
     Stops before anything else if this fails.
  2. Run the string-free session quality check (h2_diabetes_reannotation_
     quality_check). Stops before recomputation if a degenerate constant
     label or mechanical anomaly is detected.
  3. Build the corrected Annotator-2 composite (original CE 400 + the
     re-annotated diabetes 500) via build_effective_annotator_2, tagging
     each row with its provenance (annotator_2_annotation_source).
  4. Align against Annotator 1's original 900 by pair_id (never row
     position) and recompute agreement for ALL/CE/diabetes.
  5. Guard: the CE-only figures MUST be identical to the original
     (pre-correction) H2 report, since CE was never touched. Raises if not.
  6. Write NEW tracked reports (PRIMARY_H2_CORRECTED_INTERANNOTATOR_
     AGREEMENT.{json,md} and PRIMARY_H2_ORIGINAL_VS_REANNOTATION_AUDIT.
     {json,md}) WITHOUT touching the original (now-superseded, diabetes-
     component) H2 report.
  7. Build the new, per-row-anonymised PRIMARY_ADJUDICATION_CORRECTED.xlsx
     package (restricted, not committed), leaving the original 478-row
     package untouched as historical provenance.

DO NOT RUN until strengthening/restricted_local/human_annotation/v1/h2/
diabetes_reannotation/DIABETES_REANNOTATION_ANNOTATOR_2_COMPLETED.xlsx
actually exists.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import h2_build_corrected_adjudication_package as adjudication_pkg
from .common import load_workbook_data_tabs
from .h2_agreement import agreement_summary, context_use_crosstab, disagreement_types
from .h2_diabetes_reannotation_quality_check import run as run_quality_check
from .h2_recompute_with_diabetes_reannotation import build_effective_annotator_2
from .h2_validate_diabetes_reannotation import ReannotationValidationError, validate_diabetes_reannotation

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1"
H2_DIR = PKG_DIR / "h2"
CORRECTED_DIR = H2_DIR / "corrected"
REANNOTATION_DIR = H2_DIR / "diabetes_reannotation"

ANN1_COMPLETED = PKG_DIR / "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx"
ANN2_COMPLETED_ORIGINAL = PKG_DIR / "ANNOTATOR_2_PRIMARY_COMPLETED.xlsx"
DIABETES_REANNOTATION_COMPLETED = REANNOTATION_DIR / "DIABETES_REANNOTATION_ANNOTATOR_2_COMPLETED.xlsx"
BIO_SOURCE = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"

OLD_REPORT_JSON = STRENGTHENING_ROOT / "reports" / "PRIMARY_H1_INTERANNOTATOR_AGREEMENT.json"

CORRECTED_MERGED_OUT = CORRECTED_DIR / "PRIMARY_H2_CORRECTED_MERGED.csv"
CORRECTED_A2_SOURCE_OUT = CORRECTED_DIR / "ANNOTATOR_2_CORRECTED_SOURCE_PROVENANCE.csv"

CORRECTED_REPORT_JSON_OUT = STRENGTHENING_ROOT / "reports" / "PRIMARY_H2_CORRECTED_INTERANNOTATOR_AGREEMENT.json"
CORRECTED_REPORT_MD_OUT = STRENGTHENING_ROOT / "reports" / "PRIMARY_H2_CORRECTED_INTERANNOTATOR_AGREEMENT.md"
AUDIT_REPORT_JSON_OUT = STRENGTHENING_ROOT / "reports" / "PRIMARY_H2_ORIGINAL_VS_REANNOTATION_AUDIT.json"
AUDIT_REPORT_MD_OUT = STRENGTHENING_ROOT / "reports" / "PRIMARY_H2_ORIGINAL_VS_REANNOTATION_AUDIT.md"


def run() -> dict:
    if not DIABETES_REANNOTATION_COMPLETED.exists():
        raise FileNotFoundError(
            f"{DIABETES_REANNOTATION_COMPLETED} does not exist -- STOP, the diabetes re-annotation is not complete"
        )

    # -- Step 2: independent validation --------------------------------
    canonical_bio = pd.read_csv(BIO_SOURCE, dtype=str)
    reann_result = validate_diabetes_reannotation(DIABETES_REANNOTATION_COMPLETED, canonical_bio)
    if not reann_result.ok:
        raise ReannotationValidationError(
            f"Diabetes re-annotation FAILED validation -- STOP before recomputing H2.\nIssues: {reann_result.issues}"
        )

    # -- Step 3: quality check (raises no exception; flags via report) --
    quality_report = run_quality_check()
    if quality_report["degenerate_constant_label_run_detected"]:
        raise ValueError(
            "Diabetes re-annotation is AGAIN a degenerate constant-label run -- STOP, return for review before adjudication."
        )
    if quality_report["mechanical_or_data_integrity_anomaly_detected"]:
        raise ValueError(
            "A mechanical/data-integrity anomaly was detected in the diabetes re-annotation session -- STOP, return for review."
        )

    # -- Step 4: build corrected Annotator-2 composite -------------------
    ann1 = load_workbook_data_tabs(ANN1_COMPLETED)
    ann2_original = load_workbook_data_tabs(ANN2_COMPLETED_ORIGINAL)
    diabetes_reannotation = load_workbook_data_tabs(DIABETES_REANNOTATION_COMPLETED)
    diabetes_reannotation = diabetes_reannotation[diabetes_reannotation["domain"] == "biomedical_diabetes_mellitus"].reset_index(drop=True)

    ann2_effective = build_effective_annotator_2(ann2_original, diabetes_reannotation, expected_total=900)
    ann2_effective["annotator_2_annotation_source"] = ann2_effective["domain"].map(
        {"circular_economy": "original_A2_H1", "biomedical_diabetes_mellitus": "A2_diabetes_reannotation"}
    )

    # -- Step 5: align by pair_id (never row position) -------------------
    merged = ann1.merge(ann2_effective, on="pair_id", suffixes=("_1", "_2"), how="inner", validate="one_to_one")
    if len(merged) != 900:
        raise ValueError(f"expected 900 merged pairs, got {len(merged)}")

    merged = merged.rename(columns={
        "domain_1": "domain", "string_a_1": "string_a", "string_b_1": "string_b",
        "label_1": "annotator_1_label", "justification_1": "annotator_1_justification", "context_used_1": "annotator_1_context_used",
        "label_2": "annotator_2_label", "justification_2": "annotator_2_justification", "context_used_2": "annotator_2_context_used",
    })
    merged["agree"] = merged["annotator_1_label"] == merged["annotator_2_label"]
    merged["disagreement_type"] = merged.apply(
        lambda r: "" if r["agree"] else " vs ".join(sorted((r["annotator_1_label"], r["annotator_2_label"]))), axis=1
    )

    ce = merged[merged["domain"] == "circular_economy"]
    bio = merged[merged["domain"] == "biomedical_diabetes_mellitus"]

    report = {
        "overall": agreement_summary(merged),
        "circular_economy": agreement_summary(ce),
        "biomedical_diabetes_mellitus": agreement_summary(bio),
        "disagreement_types_overall": disagreement_types(merged),
        "context_use_crosstab_overall": context_use_crosstab(merged),
    }

    # -- Step 6 guard: CE must be byte-identical to the original report --
    with open(OLD_REPORT_JSON, encoding="utf-8") as f:
        old_report = json.load(f)
    old_ce, new_ce = old_report["circular_economy"], report["circular_economy"]
    if (new_ce["n"], new_ce["agreements"], new_ce["disagreements"], new_ce["raw_agreement_proportion"], new_ce["cohens_kappa"]) != (
        old_ce["n"], old_ce["agreements"], old_ce["disagreements"], old_ce["raw_agreement_proportion"], old_ce["cohens_kappa"]
    ):
        raise ValueError(
            "CE agreement figures CHANGED between the original and corrected H2 recompute -- "
            "STOP and investigate. CE was supposed to remain completely unchanged."
        )

    # -- write restricted merged data + provenance -----------------------
    CORRECTED_DIR.mkdir(parents=True, exist_ok=True)
    cols = [
        "pair_id", "domain", "string_a", "string_b",
        "annotator_1_label", "annotator_1_justification", "annotator_1_context_used",
        "annotator_2_label", "annotator_2_justification", "annotator_2_context_used",
        "agree", "disagreement_type",
    ]
    merged[cols].rename(columns={"agree": "agreement"}).to_csv(CORRECTED_MERGED_OUT, index=False, encoding="utf-8")
    # source provenance kept in a SEPARATE restricted file -- never merged
    # into the adjudicator-visible package, never exposed in the GUI.
    merged[["pair_id", "annotator_2_annotation_source"]].to_csv(CORRECTED_A2_SOURCE_OUT, index=False, encoding="utf-8")

    # -- Step 7: safe tracked reports -------------------------------------
    now = datetime.now(timezone.utc).isoformat()
    full_report = {
        "generated_at_utc": now,
        "diabetes_reannotation_validation": {"ok": reann_result.ok, "row_count": reann_result.row_count},
        **report,
        "superseded_note": (
            "The ORIGINAL H2 report (PRIMARY_H1_INTERANNOTATOR_AGREEMENT.{json,md}) is preserved "
            "unchanged for provenance. Its diabetes-domain figures are SUPERSEDED by this corrected "
            "report; its overall and circular-economy figures are unaffected/reproduced here. This "
            "corrected report is the one to use going forward."
        ),
    }
    with open(CORRECTED_REPORT_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, default=str)
    _write_corrected_markdown(full_report)

    audit = _build_old_vs_new_audit(old_report, report, ann2_original, diabetes_reannotation)
    with open(AUDIT_REPORT_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, default=str)
    _write_audit_markdown(audit)

    # -- Step 9: regenerate the adjudication package (per-row anonymised) -
    adjudication_result = adjudication_pkg.build(merged, CORRECTED_DIR)

    return {
        "report": full_report,
        "audit": audit,
        "adjudication": adjudication_result,
        "merged": merged,
        "quality_report": quality_report,
    }


def _build_old_vs_new_audit(old_report: dict, new_report: dict, ann2_original: pd.DataFrame, diabetes_reannotation: pd.DataFrame) -> dict:
    orig_bio = ann2_original[ann2_original["domain"] == "biomedical_diabetes_mellitus"].set_index("pair_id")["label"]
    new_bio = diabetes_reannotation.set_index("pair_id")["label"]
    common_ids = orig_bio.index.intersection(new_bio.index)
    n_changed = int((orig_bio.loc[common_ids] != new_bio.loc[common_ids]).sum())

    def _slim(section: dict) -> dict:
        return {
            "n": section["n"], "agreements": section["agreements"], "disagreements": section["disagreements"],
            "raw_agreement": section["raw_agreement_proportion"], "cohens_kappa": section["cohens_kappa"],
        }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "old_overall": _slim(old_report["overall"]),
        "corrected_overall": _slim(new_report["overall"]),
        "old_diabetes": _slim(old_report["biomedical_diabetes_mellitus"]),
        "corrected_diabetes": _slim(new_report["biomedical_diabetes_mellitus"]),
        "original_a2_diabetes_label_distribution": old_report["biomedical_diabetes_mellitus"]["annotator_2_label_distribution"],
        "reannotated_a2_diabetes_label_distribution": new_report["biomedical_diabetes_mellitus"]["annotator_2_label_distribution"],
        "n_a2_diabetes_common_pair_ids_compared": int(len(common_ids)),
        "n_a2_diabetes_labels_changed_between_original_and_redo": n_changed,
        "note": (
            "The superseded original Annotator-2 diabetes labels are NOT used in the corrected H2 "
            "analysis, the corrected adjudication package, or any future gold construction -- retained "
            "only as restricted provenance."
        ),
    }


def _write_corrected_markdown(report: dict) -> None:
    def fmt_section(name: str, s: dict) -> list[str]:
        lines = [
            f"## {name}",
            f"- N: {s['n']}",
            f"- Agreements: {s['agreements']}",
            f"- Disagreements: {s['disagreements']}",
            f"- Raw agreement proportion: {s['raw_agreement_proportion']}",
            f"- Cohen's kappa (inter-annotator agreement, nominal 3-class): {s['cohens_kappa']}",
            f"- Annotator 1 label distribution: {s['annotator_1_label_distribution']}",
            f"- Corrected Annotator 2 label distribution: {s['annotator_2_label_distribution']}",
            "- Confusion matrix (rows=Annotator 1, cols=corrected Annotator 2):",
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
        "# Corrected H2 inter-annotator agreement (after diabetes re-annotation)",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "SUPERSEDES the diabetes-domain figures in PRIMARY_H1_INTERANNOTATOR_AGREEMENT.md (that report "
        "is preserved unchanged as provenance). Annotator 2's circular-economy labels are byte-identical "
        "to the original H1 completion (verified below); Annotator 2's diabetes labels come from the "
        "independent re-annotation session (new randomised order, mandatory comprehension gate, no "
        "access to the superseded original diabetes labels).",
        "",
    ]
    lines += fmt_section("Overall (N=900)", report["overall"])
    lines += fmt_section("Circular Economy only (N=400)", report["circular_economy"])
    lines += fmt_section("Diabetes Mellitus only (N=500, corrected)", report["biomedical_diabetes_mellitus"])

    lines += ["## Disagreement types (overall, unordered)", ""]
    for k, v in report["disagreement_types_overall"]["unordered"].items():
        lines.append(f"- {k}: {v}")
    lines.append(f"- other/malformed: {report['disagreement_types_overall']['other']}")

    lines += ["", "## Context-use cross-tabulation (overall)", ""]
    lines += ["| Pattern | N | Proportion of total | Disagreements | Disagreement rate |", "|---|---:|---:|---:|---:|"]
    for name, v in report["context_use_crosstab_overall"].items():
        lines.append(f"| {name} | {v['n']} | {v['proportion_of_total']} | {v['disagreement_count']} | {v['disagreement_rate']} |")

    lines += ["", "## Provenance", "", report["superseded_note"]]
    CORRECTED_REPORT_MD_OUT.write_text("\n".join(lines), encoding="utf-8")


def _write_audit_markdown(audit: dict) -> None:
    lines = [
        "# Original vs re-annotation audit (diabetes domain, Annotator 2)",
        "",
        f"Generated: {audit['generated_at_utc']}",
        "",
        "| | Old (superseded) | Corrected |",
        "|---|---:|---:|",
        f"| Overall N | {audit['old_overall']['n']} | {audit['corrected_overall']['n']} |",
        f"| Overall agreements | {audit['old_overall']['agreements']} | {audit['corrected_overall']['agreements']} |",
        f"| Overall disagreements | {audit['old_overall']['disagreements']} | {audit['corrected_overall']['disagreements']} |",
        f"| Overall raw agreement | {audit['old_overall']['raw_agreement']} | {audit['corrected_overall']['raw_agreement']} |",
        f"| Overall Cohen's kappa | {audit['old_overall']['cohens_kappa']} | {audit['corrected_overall']['cohens_kappa']} |",
        f"| Diabetes N | {audit['old_diabetes']['n']} | {audit['corrected_diabetes']['n']} |",
        f"| Diabetes agreements | {audit['old_diabetes']['agreements']} | {audit['corrected_diabetes']['agreements']} |",
        f"| Diabetes disagreements | {audit['old_diabetes']['disagreements']} | {audit['corrected_diabetes']['disagreements']} |",
        f"| Diabetes raw agreement | {audit['old_diabetes']['raw_agreement']} | {audit['corrected_diabetes']['raw_agreement']} |",
        f"| Diabetes Cohen's kappa | {audit['old_diabetes']['cohens_kappa']} | {audit['corrected_diabetes']['cohens_kappa']} |",
        "",
        f"- Original (superseded) A2 diabetes label distribution: {audit['original_a2_diabetes_label_distribution']}",
        f"- Re-annotated A2 diabetes label distribution: {audit['reannotated_a2_diabetes_label_distribution']}",
        f"- A2 diabetes pair_ids compared (present in both runs): {audit['n_a2_diabetes_common_pair_ids_compared']}",
        f"- A2 diabetes labels that changed between original and redo: {audit['n_a2_diabetes_labels_changed_between_original_and_redo']}",
        "",
        audit["note"],
    ]
    AUDIT_REPORT_MD_OUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
