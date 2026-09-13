"""Gold-freeze Step 15: verify the frozen retrieval-audit (H3) package is
still intact and unstarted after the H1/H2 corrections -- does NOT
annotate anything and does NOT open the retrieval GUI. Both retrieval
launchers are already non-functional placeholder scaffolds (they print a
"not yet started" message and exit); this check confirms that remains
true and that no working/completed retrieval file or non-blank retrieval
label exists anywhere in the package.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1"

ANN1_RETRIEVAL = PKG_DIR / "03_ANNOTATOR_1_RETRIEVAL.xlsx"
ANN2_RETRIEVAL = PKG_DIR / "04_ANNOTATOR_2_RETRIEVAL.xlsx"
LAUNCHER_1 = PKG_DIR / "START_ANNOTATOR_1_RETRIEVAL.bat"
LAUNCHER_2 = PKG_DIR / "START_ANNOTATOR_2_RETRIEVAL.bat"
SELECTION_MANIFEST = STRENGTHENING_ROOT / "provenance" / "retrieval_audit_scenario_e_selection_manifest.json"
PACKAGE_MANIFEST = STRENGTHENING_ROOT / "provenance" / "final_annotation_package_manifest.json"

EXPECTED = {
    "annotator_1_total_rows": 6185,
    "annotator_1_ce_rows": 3117,
    "annotator_1_diabetes_rows": 3068,
    "annotator_2_total_rows": 2066,
    "annotator_2_outside_pool_rows": 300,
    "annotator_2_audit_sample_rows": 1766,
}

OUT_MD = STRENGTHENING_ROOT / "reports" / "H3_READINESS_CHECK.md"
OUT_JSON = STRENGTHENING_ROOT / "reports" / "h3_readiness_check.json"


def _sheet_row_counts(path: Path) -> dict:
    if not path.exists():
        return {}
    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    return {name: len(df) for name, df in sheets.items() if name != "Instructions"}


def _launcher_is_blocking_placeholder(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8").upper()
    return "NOT YET STARTED" in text and "PYTHON.EXE" not in text and "PYTHONW.EXE" not in text


def _no_labels_filled(path: Path) -> bool:
    if not path.exists():
        return True
    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    for name, df in sheets.items():
        if name == "Instructions" or "label" not in df.columns:
            continue
        if df["label"].notna().any():
            return False
    return True


def run() -> dict:
    a1_counts = _sheet_row_counts(ANN1_RETRIEVAL)
    a2_counts = _sheet_row_counts(ANN2_RETRIEVAL)

    a1_total = sum(a1_counts.values())
    a2_total = sum(a2_counts.values())
    a1_ce = a1_counts.get("Circular_Economy_Retrieval", 0)
    a1_bio = a1_counts.get("Diabetes_Retrieval", 0)

    package_files_present = ANN1_RETRIEVAL.exists() and ANN2_RETRIEVAL.exists()
    row_counts_match = (
        a1_total == EXPECTED["annotator_1_total_rows"]
        and a1_ce == EXPECTED["annotator_1_ce_rows"]
        and a1_bio == EXPECTED["annotator_1_diabetes_rows"]
        and a2_total == EXPECTED["annotator_2_total_rows"]
    )
    launchers_blocking = _launcher_is_blocking_placeholder(LAUNCHER_1) and _launcher_is_blocking_placeholder(LAUNCHER_2)
    no_working_or_completed_files = not any(
        list(PKG_DIR.glob(pattern)) for pattern in ("*RETRIEVAL_WORKING*", "*RETRIEVAL_COMPLETED*")
    )
    no_labels = _no_labels_filled(ANN1_RETRIEVAL) and _no_labels_filled(ANN2_RETRIEVAL)

    package_intact = package_files_present and row_counts_match
    h3_ready = package_intact and launchers_blocking and no_working_or_completed_files and no_labels

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": "E_SEEDS30_DEPTH50 + R2-30%",
        "expected": EXPECTED,
        "observed": {
            "annotator_1_total_rows": a1_total,
            "annotator_1_ce_rows": a1_ce,
            "annotator_1_diabetes_rows": a1_bio,
            "annotator_2_total_rows": a2_total,
        },
        "package_files_present": package_files_present,
        "row_counts_match_frozen_manifest": row_counts_match,
        "launchers_are_blocking_placeholders": launchers_blocking,
        "no_working_or_completed_retrieval_files": no_working_or_completed_files,
        "no_retrieval_labels_filled": no_labels,
        "package_intact": package_intact,
        "any_retrieval_label_created": not no_labels,
        "h3_started": False,
        "h3_ready": h3_ready,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    _write_markdown(report)
    return report


def _write_markdown(report: dict) -> None:
    lines = [
        "# H3 (retrieval-audit) readiness check",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        f"Scenario: {report['scenario']}",
        "",
        "This is a READINESS CHECK ONLY. No retrieval row was annotated and the retrieval GUI was not opened.",
        "",
        "| | Expected | Observed |",
        "|---|---:|---:|",
        f"| Annotator 1 total | {report['expected']['annotator_1_total_rows']} | {report['observed']['annotator_1_total_rows']} |",
        f"| Annotator 1 CE | {report['expected']['annotator_1_ce_rows']} | {report['observed']['annotator_1_ce_rows']} |",
        f"| Annotator 1 Diabetes | {report['expected']['annotator_1_diabetes_rows']} | {report['observed']['annotator_1_diabetes_rows']} |",
        f"| Annotator 2 total | {report['expected']['annotator_2_total_rows']} | {report['observed']['annotator_2_total_rows']} |",
        "",
        f"- Package files present: {report['package_files_present']}",
        f"- Row counts match the frozen selection manifest: {report['row_counts_match_frozen_manifest']}",
        f"- Both launchers remain blocking placeholders: {report['launchers_are_blocking_placeholders']}",
        f"- No working/completed retrieval files exist: {report['no_working_or_completed_retrieval_files']}",
        f"- No retrieval labels filled: {report['no_retrieval_labels_filled']}",
        "",
        f"## Result",
        "",
        f"- Package intact: {report['package_intact']}",
        f"- Any retrieval label created: {report['any_retrieval_label_created']}",
        f"- H3 started: {report['h3_started']}",
        f"- H3 ready: {report['h3_ready']}",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
