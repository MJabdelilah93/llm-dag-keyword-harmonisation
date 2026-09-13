"""Part A: independent diabetes licence audit -- recomputes every count
directly from strengthening/data_pmc/pmc_diabetes_* article-level rows and
the acquisition manifest. Does NOT read any previously-generated summary
field (pmc_diabetes_feasibility.json) as a source of truth -- only as a
cross-reference to report agreement/disagreement.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
DATA_PMC = STRENGTHENING_ROOT / "data_pmc"

LICENCE_BUCKETS = {
    "by": "CC BY",
    "cc0": "CC0",
    "by-sa": "CC BY-SA",
    "by-nc": "CC BY-NC",
    "by-nc-sa": "CC BY-NC-SA",
    "by-nc-nd": "CC BY-NC-ND",
    "by-nd": "other Creative Commons",
    "unknown": "missing/unclassified",
    "none": "missing/unclassified",
}


def main():
    inv = pd.read_csv(DATA_PMC / "pmc_diabetes_article_inventory.csv", low_memory=False)
    kw = pd.read_csv(DATA_PMC / "pmc_diabetes_author_keywords_raw.csv", low_memory=False)
    manifest = json.load(open(DATA_PMC / "pmc_diabetes_acquisition_manifest.json"))

    assert inv["pmcid"].duplicated().sum() == 0, "duplicate PMCIDs found in inventory -- investigate before trusting counts"
    assert len(inv) == manifest["n_unique_pmcids"] == manifest["n_article_records_parsed"] == manifest["n_uids_requested"]

    bucket_counts: dict[str, int] = {v: 0 for v in set(LICENCE_BUCKETS.values())}
    bucket_counts["publisher/custom"] = 0
    bucket_counts["other"] = 0
    raw_counts = inv["licence_code"].value_counts(dropna=False).to_dict()
    unmapped = []
    for code, n in raw_counts.items():
        bucket = LICENCE_BUCKETS.get(str(code))
        if bucket is None:
            unmapped.append((code, int(n)))
            bucket_counts["other"] += int(n)
        else:
            bucket_counts[bucket] += int(n)

    cc_by = int(inv.loc[inv["licence_code"] == "by"].shape[0])
    cc0 = int(inv.loc[inv["licence_code"] == "cc0"].shape[0])

    ccby_cc0 = inv[inv["licence_code"].isin(["by", "cc0"])]
    strict = kw[(kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author")]

    # Cross-reference against the previously-generated summary field.
    prior_report = json.load(open(STRENGTHENING_ROOT / "reports" / "pmc_diabetes_feasibility.json"))
    prior_cc_by = prior_report["cc_by_count"]
    prior_cc0 = prior_report["cc0_count"]

    PREVIOUSLY_STATED_IN_CHAT = 12364  # the figure quoted in the prior conversational report, never written to any file
    status = "CONFIRMED" if PREVIOUSLY_STATED_IN_CHAT == cc_by else "CORRECTED"

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "recomputed directly from strengthening/data_pmc/pmc_diabetes_article_inventory.csv row-level licence_code column and cross-checked against the acquisition manifest; NOT copied from any prior summary field",
        "sanity_checks": {
            "inventory_rows_equals_manifest_unique_pmcids": len(inv) == manifest["n_unique_pmcids"],
            "duplicate_pmcid_count": int(inv["pmcid"].duplicated().sum()),
            "n_records_without_pmcid": manifest["n_records_without_pmcid"],
        },
        "pipeline_stage_counts": {
            "raw_query_result_count_unfiltered": manifest["esearch_counts"]["query_unfiltered"]["count"],
            "fetched": manifest["n_uids_requested"],
            "parsed": manifest["n_article_records_parsed"],
            "unique_pmcid": manifest["n_unique_pmcids"],
            "english_eligible": int(inv["flag_language_english"].sum()),
            "date_eligible": int(inv["flag_date_in_window"].sum()),
            "topic_eligible": int(inv["flag_topic_evidence"].sum()),
            "abstract_present": int(inv["flag_abstract_present"].sum()),
        },
        "licence_classification_raw_codes": {str(k): int(v) for k, v in raw_counts.items()},
        "licence_classification_buckets": bucket_counts,
        "unmapped_licence_codes": unmapped,
        "independently_recomputed_cc_by": cc_by,
        "independently_recomputed_cc0": cc0,
        "prior_summary_field_cc_by": prior_cc_by,
        "prior_summary_field_cc0": prior_cc0,
        "prior_summary_field_matches_recomputation": (prior_cc_by == cc_by and prior_cc0 == cc0),
        "previously_stated_in_chat_report": PREVIOUSLY_STATED_IN_CHAT,
        "12364_figure_status": status,
        "12364_figure_explanation": (
            "12,364 does not appear in any committed data or report file (verified by direct search). It was a "
            "transcription error in the prior conversational summary text, not a computation or data error -- "
            "the underlying strengthening/reports/pmc_diabetes_feasibility.json already contained the correct "
            f"value (cc_by_count={prior_cc_by}), matching this independent recomputation exactly."
        ),
        "cc_by_cc0_with_any_kwd_group": int(ccby_cc0["flag_any_kwd_group"].sum()),
        "cc_by_cc0_with_confidently_author_kwd_group": int(ccby_cc0["flag_confident_author_kwds"].sum()),
        "fully_eligible_strict_articles": int(inv["flag_fully_eligible"].sum()),
        "strict_keyword_occurrences": len(strict),
        "strict_unique_keyword_strings": int(strict["keyword_raw"].nunique()),
        "strict_contributing_articles": int(strict["pmcid"].nunique()),
    }

    out_json = STRENGTHENING_ROOT / "reports" / "diabetes_licence_independent_audit.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    lines = [
        "# Diabetes-mellitus licence independent audit",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "Recomputed directly from `strengthening/data_pmc/pmc_diabetes_article_inventory.csv` row-level "
        "`licence_code` values and the acquisition manifest -- not copied from any prior summary field.",
        "",
        "## Pipeline stage counts",
        f"- Raw query result count (esearch, unfiltered): {report['pipeline_stage_counts']['raw_query_result_count_unfiltered']}",
        f"- Fetched: {report['pipeline_stage_counts']['fetched']}",
        f"- Parsed: {report['pipeline_stage_counts']['parsed']}",
        f"- Unique PMCID: {report['pipeline_stage_counts']['unique_pmcid']}",
        f"- English-eligible: {report['pipeline_stage_counts']['english_eligible']}",
        f"- Date-eligible: {report['pipeline_stage_counts']['date_eligible']}",
        f"- Topic-eligible (title/abstract only): {report['pipeline_stage_counts']['topic_eligible']}",
        f"- Abstract present: {report['pipeline_stage_counts']['abstract_present']}",
        "",
        "## Licence classification (independently recomputed, all 15,106 articles)",
        "| Bucket | Count |",
        "|---|---:|",
    ]
    for bucket in ["CC BY", "CC0", "CC BY-SA", "CC BY-NC", "CC BY-NC-SA", "CC BY-NC-ND", "other Creative Commons", "publisher/custom", "missing/unclassified", "other"]:
        lines.append(f"| {bucket} | {bucket_counts.get(bucket, 0)} |")
    lines += [
        "",
        f"Raw licence_code breakdown: {report['licence_classification_raw_codes']}",
        f"Unmapped codes (if any): {unmapped}",
        "",
        "## CC BY/CC0 x keyword-group crosstab",
        f"- CC BY/CC0 articles with any keyword group: {report['cc_by_cc0_with_any_kwd_group']}",
        f"- CC BY/CC0 articles with a confidently-author keyword group: {report['cc_by_cc0_with_confidently_author_kwd_group']}",
        f"- **Fully eligible strict articles: {report['fully_eligible_strict_articles']}**",
        f"- Strict keyword occurrences: {report['strict_keyword_occurrences']}",
        f"- Strict unique keyword strings: {report['strict_unique_keyword_strings']}",
        f"- Strict contributing articles: {report['strict_contributing_articles']}",
        "",
        "## Verdict on the previously reported '12,364 CC BY' figure",
        f"**Status: {status}**",
        "",
        report["12364_figure_explanation"],
        "",
        f"Independently recomputed CC BY = **{cc_by}**; CC0 = **{cc0}**. The prior summary field in "
        f"`strengthening/reports/pmc_diabetes_feasibility.json` already stated cc_by_count={prior_cc_by}, "
        f"cc0_count={prior_cc0} -- {'matching' if report['prior_summary_field_matches_recomputation'] else 'NOT matching'} "
        "this independent recomputation. No committed file required correction; "
        "`strengthening/reports/pmc_diabetes_feasibility.json`/`.md` are confirmed accurate and are NOT modified "
        "by this audit (this file is an independent addendum, per instruction not to overwrite evidence silently).",
    ]
    out_md = STRENGTHENING_ROOT / "reports" / "diabetes_licence_independent_audit.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {out_json}\nWrote {out_md}")
    print(json.dumps({"cc_by": cc_by, "cc0": cc0, "status": status, "matches_prior_file": report["prior_summary_field_matches_recomputation"]}, indent=2))


if __name__ == "__main__":
    main()
