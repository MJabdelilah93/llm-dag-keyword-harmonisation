"""C1 Task 14: open biomedical (diabetes) release PRECHECK.

No release action is taken here -- this only reads the existing
BIOMEDICAL_RELEASE_READINESS report/module and produces a clear manifest
separating SAFE/INTENDED PUBLIC fields from RESTRICTED/INTERNAL fields,
preserving the established 497 CC BY / 3 CC0 accounting.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..human_annotation.biomedical_release_readiness import (
    METHODOLOGY_INTERNAL_COLUMNS,
    REQUIRES_SEPARATE_REVIEW_COLUMNS,
    SAFE_TO_RELEASE_COLUMNS,
    run as run_readiness_check,
)

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
BIO_CANDIDATE_SOURCE = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
REPORTS_DIR = STRENGTHENING_ROOT / "reports"


def build_manifest() -> dict:
    readiness = run_readiness_check()
    bio = pd.read_csv(BIO_CANDIDATE_SOURCE, dtype=str)
    licence_counts = bio["source_licence"].value_counts().to_dict()

    manifest = {
        "n_diabetes_pairs": len(bio),
        "source_licence_counts": licence_counts,
        "licence_accounting_matches_established_497_cc_by_3_cc0": (
            licence_counts.get("CC BY", 0) == 497 and licence_counts.get("CC0", 0) == 3
        ),
        "release_readiness_result": readiness["release_readiness"],
        "public_release_performed": False,
        "safe_public_fields": SAFE_TO_RELEASE_COLUMNS,
        "restricted_methodology_internal_fields": METHODOLOGY_INTERNAL_COLUMNS,
        "requires_separate_licensing_review_fields": REQUIRES_SEPARATE_REVIEW_COLUMNS,
        "action_taken_this_phase": "PRECHECK ONLY -- no files published, no external upload, no release decision made.",
    }
    with open(REPORTS_DIR / "BIOMEDICAL_RELEASE_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    _write_markdown(manifest)
    return manifest


def _write_markdown(manifest: dict) -> None:
    lines = [
        "# Biomedical (diabetes) release manifest -- PRECHECK ONLY",
        "",
        f"Diabetes pairs: {manifest['n_diabetes_pairs']}",
        f"Licence counts: {manifest['source_licence_counts']}",
        f"Matches established 497 CC BY / 3 CC0 accounting: {manifest['licence_accounting_matches_established_497_cc_by_3_cc0']}",
        f"Release readiness result: {manifest['release_readiness_result']}",
        f"Public release performed: {manifest['public_release_performed']}",
        "",
        "## Safe / intended public fields", "",
    ] + [f"- {c}" for c in manifest["safe_public_fields"]] + [
        "", "## Restricted / methodology-internal fields (withheld from default release)", "",
    ] + [f"- {c}" for c in manifest["restricted_methodology_internal_fields"]] + [
        "", "## Fields requiring a separate human/licensing review before release", "",
    ] + [f"- {c}" for c in manifest["requires_separate_licensing_review_fields"]] + [
        "", manifest["action_taken_this_phase"],
    ]
    (REPORTS_DIR / "BIOMEDICAL_RELEASE_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    build_manifest()
