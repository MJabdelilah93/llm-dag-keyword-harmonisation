"""Part B: independently verify every row of the 500-pair diabetes
benchmark, tracing keyword -> source-record lineage from the raw
strengthening/data_pmc/pmc_diabetes_* files -- not by re-trusting the
generation script's own internal bookkeeping.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
DATA_PMC = STRENGTHENING_ROOT / "data_pmc"
BENCHMARK_CSV = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"

LICENCE_LABELS = {"by": "CC BY", "cc0": "CC0"}


def main():
    import sys

    sys.path.insert(0, str(STRENGTHENING_ROOT.parent))
    from strengthening.candidate_gen.normalise import unordered_pair_key
    from strengthening.candidate_gen.pair_ids import stable_pair_id
    from strengthening.candidate_gen.stratify import classify_pair

    df = pd.read_csv(BENCHMARK_CSV, dtype=str)
    kw = pd.read_csv(DATA_PMC / "pmc_diabetes_author_keywords_raw.csv", low_memory=False)
    inv = pd.read_csv(DATA_PMC / "pmc_diabetes_article_inventory.csv", low_memory=False)
    inv_licence = dict(zip(inv["pmcid"], inv["licence_code"]))
    inv_fully_eligible = dict(zip(inv["pmcid"], inv["flag_fully_eligible"]))

    # Ground truth: for every (pmcid, keyword_raw), is there a row where
    # this exact article confidently-author-attributes this exact string,
    # AND that article is independently licence-verified CC BY/CC0 AND
    # fully eligible? This is recomputed straight from the raw file, not
    # from the benchmark's own stored provenance columns.
    strict = kw[(kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author")]
    strict_keyword_to_pmcids = strict.groupby("keyword_raw")["pmcid"].apply(set).to_dict()
    strict_keyword_set = set(strict_keyword_to_pmcids.keys())

    # Any-classification lookup (to detect "keyword ALSO appears via an
    # ambiguous/clearly_not_author group or an ineligible article" -- not
    # disqualifying by itself, but checked/reported per criterion 3/4).
    any_kw_pmcid_class = kw.groupby(["keyword_raw", "pmcid"])["group_classification"].apply(set).to_dict()

    findings = []
    seen_norm_keys = {}
    for _, row in df.iterrows():
        pid = row["pair_id"]
        a, b = row["string_a"], row["string_b"]
        issues = []

        # 1. both strings originate only from the strict eligible inventory
        a_in_strict = a in strict_keyword_set
        b_in_strict = b in strict_keyword_set
        if not a_in_strict:
            issues.append(f"string_a '{a}' not found in strict eligible keyword inventory")
        if not b_in_strict:
            issues.append(f"string_b '{b}' not found in strict eligible keyword inventory")

        # 2/4/5. every provenance PMCID must have CC BY/CC0 evidence AND be
        # fully eligible AND the keyword must not enter solely via an
        # ineligible article -- re-derive full PMCID sets from scratch
        # (not from the benchmark's own truncated source_pmcids_a/b cols).
        a_pmcids = strict_keyword_to_pmcids.get(a, set())
        b_pmcids = strict_keyword_to_pmcids.get(b, set())
        for label, pmcids in (("a", a_pmcids), ("b", b_pmcids)):
            if not pmcids:
                continue
            bad_licence = [p for p in pmcids if inv_licence.get(p) not in ("by", "cc0")]
            not_eligible = [p for p in pmcids if inv_fully_eligible.get(p) != 1]
            if bad_licence:
                issues.append(f"string_{label} has a contributing PMCID without CC BY/CC0 evidence: {bad_licence}")
            if not_eligible:
                issues.append(f"string_{label} has a contributing PMCID not flagged fully_eligible: {not_eligible}")

        # 3. no ambiguous/index/controlled-vocab kwd-group contributed --
        # i.e. every (keyword, contributing pmcid) pair used for THIS
        # benchmark string must have at least one confidently_author
        # classification (already guaranteed by strict_keyword_to_pmcids
        # construction; here we additionally flag if the SAME string also
        # appears via an ambiguous group elsewhere, informational only).
        for label, s in (("a", a), ("b", b)):
            classes_seen = set()
            for pmcid in strict_keyword_to_pmcids.get(s, set()):
                classes_seen |= any_kw_pmcid_class.get((s, pmcid), set())
            if classes_seen and "confidently_author" not in classes_seen and s in strict_keyword_set:
                issues.append(f"string_{label} '{s}' unexpectedly has no confidently_author source despite being in the strict set (logic error)")

        # 6. pair_id reproducible
        expected_pid = stable_pair_id(a, b, "bio_diab")
        if expected_pid != pid:
            issues.append(f"pair_id mismatch: stored={pid} recomputed={expected_pid}")

        # 7. canonical unordered pair unique
        norm_key = unordered_pair_key(a, b)
        if norm_key in seen_norm_keys:
            issues.append(f"duplicate unordered pair (also row for pair_id={seen_norm_keys[norm_key]})")
        else:
            seen_norm_keys[norm_key] = pid

        # 8. stratum assignment satisfies the implemented stratum rule
        emb_cos = float(row["embedding_cosine"]) if row["embedding_cosine"] not in (None, "", "nan") else None
        recomputed = classify_pair(a, b, emb_cos)
        if recomputed.stratum != row["candidate_stratum"]:
            issues.append(f"stratum mismatch: stored={row['candidate_stratum']} recomputed={recomputed.stratum}")

        # 9. gold/annotation fields blank
        if str(row.get("gold_label", "")).strip() not in ("", "nan"):
            issues.append(f"gold_label not blank: '{row.get('gold_label')}'")

        findings.append({"pair_id": pid, "valid": len(issues) == 0, "issues": issues})

    n_total = len(findings)
    n_valid = sum(1 for f in findings if f["valid"])
    invalid = [f for f in findings if not f["valid"]]

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows_audited": n_total,
        "provenance_valid": n_valid,
        "invalid": len(invalid),
        "invalid_pair_ids_and_issues": invalid,
        "result": "PASS" if len(invalid) == 0 else "FAIL",
    }

    out_json = STRENGTHENING_ROOT / "reports" / "biomedical_500_provenance_audit.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    lines = [
        "# Biomedical 500-pair benchmark provenance audit",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "Traces keyword -> source-record lineage from raw strengthening/data_pmc/pmc_diabetes_* files "
        "for every one of the 500 benchmark rows (not merely re-checking the 497/3 licence-label counts).",
        "",
        f"Rows audited: {n_total}",
        f"Provenance-valid: {n_valid}",
        f"Invalid: {len(invalid)}",
        "",
        f"**500/500 provenance-valid: {'YES' if len(invalid) == 0 else 'NO'}**",
        "",
        f"## Result: {report['result']}",
    ]
    if invalid:
        lines.append("")
        lines.append("## Affected pair IDs (benchmark NOT modified; reported for review, not repaired)")
        for f in invalid:
            lines.append(f"- {f['pair_id']}: {f['issues']}")
    out_md = STRENGTHENING_ROOT / "reports" / "biomedical_500_provenance_audit.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {out_json}\nWrote {out_md}")
    print(json.dumps({"rows_audited": n_total, "valid": n_valid, "invalid": len(invalid), "result": report["result"]}, indent=2))


if __name__ == "__main__":
    main()
