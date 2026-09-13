"""Gold-freeze Step 13: release-readiness CHECK ONLY for the 500 diabetes
pairs -- does not publish or upload anything. Verifies the source-article
licence provenance still holds CC BY/CC0, checks that the biomedical
derivative carries no restricted (Scopus/circular-economy) contamination,
and lists which columns of the biomedical candidate source may safely be
released versus which require a separate review. String-free (reports
counts/column names/licence labels only, never keyword content).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
BIO_CANDIDATE_SOURCE = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
GOLD_CSV = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "gold" / "PRIMARY_GOLD_900_FINAL.csv"
PROVENANCE_AUDIT_JSON = STRENGTHENING_ROOT / "reports" / "biomedical_500_provenance_audit.json"

ALLOWED_RELEASE_LICENCES = {"CC BY", "CC0"}

# columns from the biomedical candidate source that carry only public,
# licence-cleared content and internal (non-identifying) generation
# metadata -- safe to release as-is.
SAFE_TO_RELEASE_COLUMNS = [
    "pair_id", "domain", "string_a", "string_b", "frequency_a", "frequency_b",
    "canonical_unordered_pair_key", "source_licence", "source_pmcids_a", "source_pmcids_b",
]
# internal scoring/sampling-design columns: not licence-restricted, but
# expose methodology/route-selection internals -- withheld from the
# DEFAULT release bundle pending a separate decision on whether to
# publish them (they do not need a licensing review, just a design one).
METHODOLOGY_INTERNAL_COLUMNS = [
    "candidate_stratum", "proposing_routes", "route_specific_ranks",
    "jaro_winkler_score", "tfidf_cosine", "embedding_cosine",
    "acronym_feature", "punctuation_feature", "plural_feature", "malformed_feature", "short_form_feature",
    "generation_seed", "generation_timestamp_utc",
]
# free-text / compiled-title fields that must NOT be included in a default
# release without a separate licensing/attribution review, even though the
# underlying articles are CC BY/CC0 -- human justification text can quote
# or paraphrase source material unpredictably, and a compiled title list
# is a separate derivative work from the single-pair benchmark rows.
REQUIRES_SEPARATE_REVIEW_COLUMNS = [
    "annotator_1_justification", "annotator_2_justification", "adjudicator_notes",
    "context_lookup_titles",
]


def run() -> dict:
    bio = pd.read_csv(BIO_CANDIDATE_SOURCE, dtype=str)
    licence_counts = bio["source_licence"].value_counts().to_dict()
    non_compliant = int((~bio["source_licence"].isin(ALLOWED_RELEASE_LICENCES)).sum())

    provenance_valid = None
    if PROVENANCE_AUDIT_JSON.exists():
        with open(PROVENANCE_AUDIT_JSON, encoding="utf-8") as f:
            prov = json.load(f)
        provenance_valid = prov.get("result") == "PASS" and prov.get("invalid", 1) == 0

    ce_contamination_check = {"checked": False}
    if GOLD_CSV.exists():
        gold = pd.read_csv(GOLD_CSV, dtype=str)
        bio_gold = gold[gold["domain"] == "biomedical_diabetes_mellitus"]
        ce_gold = gold[gold["domain"] == "circular_economy"]
        ce_contamination_check = {
            "checked": True,
            "biomedical_gold_rows": len(bio_gold),
            "circular_economy_gold_rows": len(ce_gold),
            "biomedical_rows_all_domain_tagged_correctly": bool((bio_gold["domain"] == "biomedical_diabetes_mellitus").all()),
            "biomedical_pair_ids_disjoint_from_ce_pair_ids": len(set(bio_gold["pair_id"]) & set(ce_gold["pair_id"])) == 0,
            "biomedical_gold_row_count_matches_expected_500": len(bio_gold) == 500,
        }

    ready = (
        non_compliant == 0
        and (provenance_valid is not False)
        and ce_contamination_check.get("checked", False)
        and ce_contamination_check.get("biomedical_pair_ids_disjoint_from_ce_pair_ids", False)
        and ce_contamination_check.get("biomedical_gold_row_count_matches_expected_500", False)
    )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_diabetes_pairs": len(bio),
        "source_licence_counts": licence_counts,
        "n_non_cc_by_or_cc0": non_compliant,
        "provenance_audit_previously_passed": provenance_valid,
        "ce_contamination_check": ce_contamination_check,
        "safe_to_release_columns": SAFE_TO_RELEASE_COLUMNS,
        "methodology_internal_columns_withheld_by_default": METHODOLOGY_INTERNAL_COLUMNS,
        "requires_separate_review_columns": REQUIRES_SEPARATE_REVIEW_COLUMNS,
        "public_release_performed": False,
        "release_readiness": "READY_FOR_FUTURE_RELEASE_DECISION" if ready else "NOT_READY",
    }
    _write_markdown(report)
    return report


def _write_markdown(report: dict) -> None:
    lines = [
        "# Biomedical (diabetes) release readiness check",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "This is a READINESS CHECK ONLY. Nothing has been uploaded or published.",
        "",
        f"- Diabetes pairs: {report['n_diabetes_pairs']}",
        f"- Source licence counts: {report['source_licence_counts']}",
        f"- Non CC BY / CC0 rows: {report['n_non_cc_by_or_cc0']}",
        f"- Prior provenance audit passed: {report['provenance_audit_previously_passed']}",
        f"- CE contamination check: {report['ce_contamination_check']}",
        "",
        "## Columns safe to release by default",
        "",
    ] + [f"- {c}" for c in report["safe_to_release_columns"]] + [
        "",
        "## Methodology/internal columns withheld from the default release bundle",
        "",
    ] + [f"- {c}" for c in report["methodology_internal_columns_withheld_by_default"]] + [
        "",
        "## Fields requiring a separate licensing/attribution review before inclusion",
        "",
    ] + [f"- {c}" for c in report["requires_separate_review_columns"]] + [
        "",
        f"## Result: {report['release_readiness']}",
        "",
        f"Public release performed: {report['public_release_performed']}",
    ]
    (STRENGTHENING_ROOT / "reports" / "BIOMEDICAL_RELEASE_READINESS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
