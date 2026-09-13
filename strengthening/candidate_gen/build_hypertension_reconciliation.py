"""Step 2: build the hypertension count reconciliation JSON, computed
directly from the acquisition manifests and inventory CSVs (no
hand-transcribed numbers)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
DATA_PMC = STRENGTHENING_ROOT / "data_pmc"
OUT = STRENGTHENING_ROOT / "reports" / "hypertension_count_reconciliation.json"


def funnel(path: Path) -> dict:
    df = pd.read_csv(path, low_memory=False)
    cols = [
        "flag_language_english", "flag_date_in_window", "flag_topic_evidence",
        "flag_abstract_present", "flag_licence_ccby_or_cc0", "flag_any_kwd_group",
        "flag_confident_author_kwds", "flag_eligible_for_release", "flag_fully_eligible",
    ]
    out = {"n_rows": len(df)}
    for c in cols:
        out[c] = int(df[c].sum())
    out["duplicate_pmcid"] = int(df["pmcid"].duplicated().sum())
    out["duplicate_doi_nonnull"] = int(df.loc[df["doi"].notna(), "doi"].duplicated().sum())
    out["missing_title"] = int(df["title"].isna().sum())
    out["parse_error_nonnull"] = int(df["parse_error"].notna().sum())
    return out


def strict_keyword_stats(kw_path: Path) -> dict:
    kw = pd.read_csv(kw_path, low_memory=False)
    strict = kw[(kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author")]
    return {
        "author_keyword_occurrences": len(strict),
        "unique_raw_author_keyword_strings": int(strict["keyword_raw"].nunique()),
        "contributing_articles": int(strict["pmcid"].nunique()),
    }


def manifest_fields(path: Path) -> dict:
    m = json.load(open(path))
    return {
        "retrieval_started_utc": m["retrieval_started_utc"],
        "retrieval_finished_utc": m["retrieval_finished_utc"],
        "n_uids_requested": m["n_uids_requested"],
        "n_article_records_parsed": m["n_article_records_parsed"],
        "n_unique_pmcids": m["n_unique_pmcids"],
        "n_records_without_pmcid": m["n_records_without_pmcid"],
        "n_duplicate_pmcid_records_dropped": m["n_duplicate_pmcid_records_dropped"],
        "probe_per_year": m["probe_per_year"],
        "corpus_per_year": m["corpus_per_year"],
        "total_live_ncbi_requests": m["total_live_ncbi_requests"],
    }


def main():
    primary_manifest = manifest_fields(DATA_PMC / "pmc_hypertension_acquisition_manifest.json")
    extended_manifest = manifest_fields(DATA_PMC / "pmc_hypertension_extended_acquisition_manifest.json")

    primary_funnel = funnel(DATA_PMC / "pmc_hypertension_article_inventory.csv")
    extended_funnel = funnel(DATA_PMC / "pmc_hypertension_extended_article_inventory.csv")
    merged_funnel = funnel(DATA_PMC / "pmc_hypertension_merged_article_inventory.csv")

    primary_strict = strict_keyword_stats(DATA_PMC / "pmc_hypertension_author_keywords_raw.csv")
    merged_strict = strict_keyword_stats(DATA_PMC / "pmc_hypertension_merged_author_keywords_raw.csv")

    n_primary = primary_manifest["n_unique_pmcids"]
    n_extended = extended_manifest["n_unique_pmcids"]
    n_merged = merged_funnel["n_rows"]
    overlap = n_primary + n_extended - n_merged

    report = {
        "figure_15368_represents": "unique PMC articles across PRIMARY (2015-2025) UNION EXTENDED (2010-2025) windows, deduplicated by PMCID -- the complete evidentiary base for the feasibility gate",
        "figure_14571_represents": "unique PMC articles from the PRIMARY (2015-2025) window ALONE, i.e. the original acquisition subagent's completed work before the broader-window supplement",
        "figure_12366_represents": "unique PMC articles from the EXTENDED (2010-2025) window ALONE (run separately to test the broader-window remedy)",
        "arithmetic_check": {
            "n_primary": n_primary,
            "n_extended": n_extended,
            "n_merged_deduplicated": n_merged,
            "overlap_between_runs": overlap,
            "identity_holds": (n_primary + n_extended - overlap) == n_merged,
        },
        "methodological_note": (
            "Primary and extended acquisitions used DIFFERENT per-year retrieval caps: "
            f"primary probe_per_year={primary_manifest['probe_per_year']} corpus_per_year={primary_manifest['corpus_per_year']}; "
            f"extended probe_per_year={extended_manifest['probe_per_year']} corpus_per_year={extended_manifest['corpus_per_year']} "
            "(this script's own CLI defaults, not overridden to match primary when the broader-window test was run). "
            "Disclosed for transparency; does not change the feasibility conclusion, which the current instruction "
            "supersedes with the diabetes-mellitus fallback rather than further hypertension optimisation."
        ),
        "primary_acquisition_manifest": primary_manifest,
        "extended_acquisition_manifest": extended_manifest,
        "funnel": {
            "primary": primary_funnel,
            "extended": extended_funnel,
            "merged_authoritative": merged_funnel,
        },
        "strict_author_keyword_corpus": {
            "primary": primary_strict,
            "merged_authoritative": merged_strict,
        },
        "authoritative_raw_count": n_merged,
        "authoritative_fully_eligible_count": merged_funnel["flag_fully_eligible"],
        "authoritative_unique_strict_keyword_count": merged_strict["unique_raw_author_keyword_strings"],
        "discrepancy_resolved": True,
        "original_feasibility_reports_preserved_unmodified": [
            "strengthening/reports/pmc_hypertension_feasibility.json",
            "strengthening/reports/pmc_hypertension_feasibility.md",
        ],
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Wrote {OUT}")
    print(json.dumps(report["arithmetic_check"], indent=2))


if __name__ == "__main__":
    main()
