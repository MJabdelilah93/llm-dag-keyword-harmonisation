"""Stage 3 (gate) + Stage 5(biomedical): generate the new, UNLABELLED
500-pair PMC-hypertension candidate set for the M7 strengthening phase.

Reads the PMC acquisition/extraction output produced under
strengthening/data_pmc/ (built from official NCBI/PMC endpoints only; see
strengthening/data_pmc/pmc_hypertension_acquisition_manifest.json for the
exact query/services/timestamps). This module performs the STRICT final
eligibility filter and the stratified sampling gate; it does not re-touch
the network.

Eligibility (all required, matching protocol_v1.yaml + the task's
Stage 3 rules):
  - article_fully_eligible == 1  (English, in-window, topic-evidenced from
    title/abstract only, abstract present, licence CC BY/CC0 verified)
  - group_classification == 'confidently_author' (conservative: MeSH/
    indexing-term groups and ambiguous groups are excluded here, not just
    at the article level)

Unlike the circular-economy track, there is no legacy overlap constraint
here (this is a brand-new domain) and the resulting file is NOT restricted
-- CC BY/CC0 content is redistributable by definition, so it is written
directly under strengthening/benchmark/, not restricted_local/.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from .features import EmbeddingIndex, TfidfIndex, top_k_per_row
from .generate_ce_candidates import _add_candidate, _add_structural_groups
from .normalise import unordered_pair_key
from .pair_ids import stable_pair_id
from .stratify import classify_pair

HERE = Path(__file__).resolve()
STRENGTHENING_ROOT = HERE.parents[1]
CONFIG_PATH = STRENGTHENING_ROOT / "config" / "protocol_v1.yaml"

PMC_KEYWORDS_PATH = STRENGTHENING_ROOT / "data_pmc" / "pmc_hypertension_merged_author_keywords_raw.csv"
PMC_INVENTORY_PATH = STRENGTHENING_ROOT / "data_pmc" / "pmc_hypertension_merged_article_inventory.csv"
PMC_KWD_GROUPS_PATH = STRENGTHENING_ROOT / "data_pmc" / "pmc_hypertension_merged_kwd_groups.csv"
# Provenance note: the 2015-2025 primary window (config: biomedical.primary_start_date)
# was insufficient by itself for stratum iv (35 available vs 40 required, out
# of 500 total). Per protocol, ONE broader pre-specified time window was
# tested (2010-2025, i.e. primary_start_date moved back 5 years, every other
# eligibility rule held fixed) via strengthening/scripts_pmc/01_acquire.py
# --years 2010-2025 --out-prefix pmc_hypertension_extended, and the result
# was merged with the original acquisition (dedup by PMCID) rather than
# replacing it, so no previously-acquired evidence is discarded. The
# diabetes-mellitus fallback was NOT activated.

OUT_CSV = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
MANIFEST_OUT = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_manifest.json"
FEASIBILITY_JSON_OUT = STRENGTHENING_ROOT / "reports" / "pmc_hypertension_feasibility.json"
FEASIBILITY_MD_OUT = STRENGTHENING_ROOT / "reports" / "pmc_hypertension_feasibility.md"

TOP_K_TFIDF = 15
TOP_K_EMBEDDING = 15
TFIDF_MIN_SCORE = 0.30
EMBEDDING_MIN_SCORE = 0.45

LICENCE_LABELS = {"by": "CC BY", "cc0": "CC0"}


def load_strict_eligible_keywords() -> pd.DataFrame:
    kw = pd.read_csv(PMC_KEYWORDS_PATH, low_memory=False)
    strict = kw[(kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author")].copy()
    strict["source_licence"] = strict["licence_code"].map(LICENCE_LABELS)
    return strict


def build_frequency_and_provenance(strict: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    freq = strict.groupby("keyword_raw").size().reset_index(name="frequency")
    provenance: dict[str, list[str]] = defaultdict(list)
    for _, row in strict.iterrows():
        provenance[row["keyword_raw"]].append(row["pmcid"])
    return freq, provenance


def generate(seed: int = 42) -> dict:
    strict = load_strict_eligible_keywords()
    freq_df, provenance = build_frequency_and_provenance(strict)
    freq_lookup = dict(zip(freq_df["keyword_raw"], freq_df["frequency"]))
    licence_lookup = dict(zip(strict["keyword_raw"], strict["source_licence"]))

    universe = freq_df.sort_values(by=["frequency", "keyword_raw"], ascending=[False, True])["keyword_raw"].tolist()

    pool: dict[tuple[str, str], dict] = {}
    _add_structural_groups(universe, pool)

    tfidf_index = TfidfIndex(universe)
    tfidf_sim = tfidf_index.similarity_matrix()
    tfidf_neighbours = top_k_per_row(tfidf_sim, TOP_K_TFIDF, TFIDF_MIN_SCORE)
    for i, neighbours in tfidf_neighbours.items():
        for rank, (j, score) in enumerate(neighbours, start=1):
            _add_candidate(pool, universe[i], universe[j], route="tfidf_topk", rank=rank)

    embedding_index = EmbeddingIndex(universe)
    emb_sim = embedding_index.similarity_matrix()
    emb_neighbours = top_k_per_row(emb_sim, TOP_K_EMBEDDING, EMBEDDING_MIN_SCORE)
    for i, neighbours in emb_neighbours.items():
        for rank, (j, score) in enumerate(neighbours, start=1):
            _add_candidate(pool, universe[i], universe[j], route="embedding_topk", embedding_cosine=score, rank=rank)

    from .features import malformed_feature

    idx_of = {s: i for i, s in enumerate(universe)}
    for s in universe:
        if malformed_feature(s):
            i = idx_of[s]
            for j, score in (tfidf_neighbours.get(i, [])[:1] + emb_neighbours.get(i, [])[:1]):
                _add_candidate(pool, s, universe[j], route="malformed_nearest_neighbour")

    stratified: dict[str, list[dict]] = defaultdict(list)
    seen_norm_keys: set[tuple[str, str]] = set()
    for raw_key in sorted(pool.keys()):
        entry = pool[raw_key]
        a, b = entry["a"], entry["b"]
        norm_key = unordered_pair_key(a, b)
        if norm_key in seen_norm_keys:
            continue
        seen_norm_keys.add(norm_key)
        emb_cos = entry["embedding_cosine"]
        if emb_cos is None and a in idx_of and b in idx_of:
            emb_cos = embedding_index.cosine(idx_of[a], idx_of[b])
        result = classify_pair(a, b, emb_cos)
        if result.stratum is None:
            continue
        pair_id = stable_pair_id(a, b, "bio")
        record = {
            "pair_id": pair_id,
            "domain": "biomedical_hypertension",
            "string_a": a,
            "string_b": b,
            "frequency_a": int(freq_lookup.get(a, 0)),
            "frequency_b": int(freq_lookup.get(b, 0)),
            "canonical_unordered_pair_key": "|".join(norm_key),
            "candidate_stratum": result.stratum,
            "proposing_routes": ";".join(sorted(entry["routes"])),
            "route_specific_ranks": json.dumps(entry["ranks"], sort_keys=True),
            "jaro_winkler_score": round(result.jw_score, 6),
            "tfidf_cosine": round(tfidf_index.cosine(idx_of[a], idx_of[b]) if a in idx_of and b in idx_of else 0.0, 6),
            "embedding_cosine": round(emb_cos, 6) if emb_cos is not None else "",
            "acronym_feature": result.acronym,
            "punctuation_feature": result.punctuation,
            "plural_feature": result.plural,
            "malformed_feature": result.malformed,
            "short_form_feature": result.short_form,
            "generation_seed": seed,
            "generation_timestamp_utc": None,
            "source_licence": licence_lookup.get(a) or licence_lookup.get(b) or "",
            "source_pmcids_a": ";".join(sorted(set(provenance.get(a, [])))[:5]),
            "source_pmcids_b": ";".join(sorted(set(provenance.get(b, [])))[:5]),
            "gold_label": "",
        }
        stratified[result.stratum].append(record)

    return {
        "stratified": stratified,
        "universe_size": len(universe),
        "pool_size_before_stratification": len(pool),
        "n_strict_eligible_keyword_rows": len(strict),
        "n_contributing_articles": strict["pmcid"].nunique(),
    }


def sample_quota(stratified: dict[str, list[dict]], quotas: dict[str, int], seed: int) -> tuple[list[dict], dict[str, dict]]:
    rng = random.Random(seed)
    selected: list[dict] = []
    shortfall_report: dict[str, dict] = {}
    for stratum, quota in quotas.items():
        if stratum == "total":
            continue
        pool = sorted(stratified.get(stratum, []), key=lambda r: r["pair_id"])
        available = len(pool)
        chosen = rng.sample(pool, quota) if available >= quota else pool
        shortfall_report[stratum] = {
            "quota": quota,
            "available": available,
            "selected": len(chosen),
            "shortfall": max(0, quota - available),
        }
        selected.extend(chosen)
    return selected, shortfall_report


def build_feasibility_report() -> dict:
    inv = pd.read_csv(PMC_INVENTORY_PATH, low_memory=False)
    kw = pd.read_csv(PMC_KEYWORDS_PATH, low_memory=False)
    with open(STRENGTHENING_ROOT / "data_pmc" / "pmc_hypertension_acquisition_manifest.json") as f:
        acq_manifest_primary = json.load(f)
    with open(STRENGTHENING_ROOT / "data_pmc" / "pmc_hypertension_extended_acquisition_manifest.json") as f:
        acq_manifest_extended = json.load(f)
    acq_manifest = acq_manifest_primary  # for services_used / rate_limit fields shared by both runs

    strict = load_strict_eligible_keywords()
    gen_result = generate(seed=42)
    stratum_pool_counts = {s: len(v) for s, v in gen_result["stratified"].items()}

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    quotas = config["stratum_quotas"]["biomedical_500"]
    gate_pass = all(stratum_pool_counts.get(s, 0) >= q for s, q in quotas.items() if s != "total")

    import re

    def char_flags(series: pd.Series) -> dict:
        s = series.dropna().astype(str)
        return {
            "punctuation": int(s.str.contains(r"[.,;:()\[\]/]").sum()),
            "hyphen": int(s.str.contains("-").sum()),
            "uppercase_acronym_like": int(s.str.fullmatch(r"[A-Z0-9\-]{2,10}").sum()),
            "digits": int(s.str.contains(r"\d").sum()),
            "parentheses": int(s.str.contains(r"[()]").sum()),
        }

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "api_service": [s["name"] for s in acq_manifest["services_used"]],
        "exact_query_topic_evidence": config["topic_inclusion_evidence"]["hypertension"],
        "retrieval_window_primary": [acq_manifest_primary["retrieval_started_utc"], acq_manifest_primary["retrieval_finished_utc"]],
        "retrieval_window_extended": [acq_manifest_extended["retrieval_started_utc"], acq_manifest_extended["retrieval_finished_utc"]],
        "date_range_primary": [config["biomedical"]["primary_start_date"], config["biomedical"]["primary_end_date"]],
        "date_range_extended_tested": ["2010-01-01", config["biomedical"]["primary_end_date"]],
        "start_date_override_used": "2010-01-01 (primary 2015-01-01 was insufficient for stratum iv alone; merged with primary rather than replacing it)",
        "total_records_found": len(inv),
        "records_passing_language_filter": int(inv["flag_language_english"].sum()),
        "records_passing_date_filter": int(inv["flag_date_in_window"].sum()),
        "records_passing_topic_filter": int(inv["flag_topic_evidence"].sum()),
        "records_with_abstract": int(inv["flag_abstract_present"].sum()),
        "licence_counts": inv["licence_code"].value_counts().to_dict(),
        "cc_by_count": int((inv["licence_code"] == "by").sum()),
        "cc0_count": int((inv["licence_code"] == "cc0").sum()),
        "excluded_licence_counts_by_reason": inv.loc[inv["flag_licence_ccby_or_cc0"] == 0, "licence_exclusion_reason"].value_counts().to_dict(),
        "records_with_any_keyword_group": int(inv["flag_any_kwd_group"].sum()),
        "records_with_confident_author_keywords": int(inv["flag_confident_author_kwds"].sum()),
        "ambiguous_keyword_group_count": int((pd.read_csv(PMC_KWD_GROUPS_PATH)["classification"] == "ambiguous").sum()),
        "records_fully_eligible": int(inv["flag_fully_eligible"].sum()),
        "total_author_keyword_occurrences_strict": len(strict),
        "unique_raw_author_keyword_strings_strict": strict["keyword_raw"].nunique(),
        "keywords_per_article_distribution_strict": strict.groupby("pmcid").size().describe().to_dict(),
        "duplicate_pmcid_check": int(inv["pmcid"].duplicated().sum()),
        "duplicate_doi_check": int(inv.loc[inv["doi"].notna(), "doi"].duplicated().sum()),
        "missing_title_count": int(inv["title"].isna().sum()),
        "missing_abstract_count": int((~inv["flag_abstract_present"].astype(bool)).sum()),
        "top_20_keyword_frequencies_strict": strict["keyword_raw"].value_counts().head(20).to_dict(),
        "keyword_string_character_flags_strict": char_flags(strict["keyword_raw"].drop_duplicates()),
        "candidate_pool_size_per_stratum": stratum_pool_counts,
        "stratum_quotas_biomedical_500": {k: v for k, v in quotas.items() if k != "total"},
        "all_ten_strata_quotas_achievable": gate_pass,
        "diabetes_fallback_activated": False,
        "broader_time_window_tested": True,
        "n_contributing_articles_strict": int(strict["pmcid"].nunique()),
        "ncbi_rate_limit_policy": acq_manifest["rate_limit_policy"],
        "total_live_ncbi_requests": acq_manifest["total_live_ncbi_requests"],
    }
    return report


def write_feasibility_report(report: dict):
    FEASIBILITY_JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(FEASIBILITY_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    lines = [
        "# PMC hypertension feasibility report",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "## API/service and query",
        f"- Services: {', '.join(report['api_service'])}",
        f"- Topic-evidence terms (title/abstract only): {report['exact_query_topic_evidence']}",
        f"- Primary date range: {report['date_range_primary'][0]} to {report['date_range_primary'][1]}",
        f"- Extended date range tested: {report['date_range_extended_tested'][0]} to {report['date_range_extended_tested'][1]}",
        f"- Primary retrieval window (UTC): {report['retrieval_window_primary'][0]} to {report['retrieval_window_primary'][1]}",
        f"- Extended retrieval window (UTC): {report['retrieval_window_extended'][0]} to {report['retrieval_window_extended'][1]}",
        f"- Broader time window tested: {report['broader_time_window_tested']} ({report['start_date_override_used']})",
        f"- Diabetes fallback activated: {report['diabetes_fallback_activated']}",
        "",
        "## Filter funnel",
        f"- Total records found (raw esearch): {report['total_records_found']}",
        f"- Passing language filter: {report['records_passing_language_filter']}",
        f"- Passing date filter: {report['records_passing_date_filter']}",
        f"- Passing topic filter (title/abstract only): {report['records_passing_topic_filter']}",
        f"- With abstract present: {report['records_with_abstract']}",
        f"- CC BY: {report['cc_by_count']}, CC0: {report['cc0_count']}",
        f"- Excluded-licence counts by reason: {report['excluded_licence_counts_by_reason']}",
        f"- With any keyword group: {report['records_with_any_keyword_group']}",
        f"- With confident author keywords: {report['records_with_confident_author_keywords']}",
        f"- Ambiguous keyword-group count (excluded from benchmark): {report['ambiguous_keyword_group_count']}",
        f"- **Fully eligible articles: {report['records_fully_eligible']}**",
        "",
        "## Keyword statistics (strict: fully-eligible articles, confidently-author groups only)",
        f"- Total author-keyword occurrences: {report['total_author_keyword_occurrences_strict']}",
        f"- Unique raw author-keyword strings: {report['unique_raw_author_keyword_strings_strict']}",
        f"- Contributing articles: {report['n_contributing_articles_strict']}",
        f"- Keywords-per-article distribution: {report['keywords_per_article_distribution_strict']}",
        f"- Duplicate PMCID check: {report['duplicate_pmcid_check']}",
        f"- Duplicate DOI check: {report['duplicate_doi_check']}",
        f"- Character-pattern flags on unique keywords: {report['keyword_string_character_flags_strict']}",
        "",
        "## Ten-stratum candidate pool sizes (target: strengthening/config/protocol_v1.yaml stratum_quotas.biomedical_500)",
    ]
    for s, q in report["stratum_quotas_biomedical_500"].items():
        avail = report["candidate_pool_size_per_stratum"].get(s, 0)
        lines.append(f"- stratum {s}: available={avail}, quota={q}, {'OK' if avail >= q else 'SHORTFALL of ' + str(q - avail)}")
    lines.append("")
    lines.append(f"## Gate result: all ten strata achievable = **{report['all_ten_strata_quotas_achievable']}**")
    lines.append("")
    lines.append(f"NCBI rate-limit policy: {report['ncbi_rate_limit_policy']}; total live requests: {report['total_live_ncbi_requests']}")

    FEASIBILITY_MD_OUT.write_text("\n".join(lines), encoding="utf-8")


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    seed = config["random_seed"]
    quotas = config["stratum_quotas"]["biomedical_500"]

    report = build_feasibility_report()
    write_feasibility_report(report)

    if not report["all_ten_strata_quotas_achievable"]:
        print("GATE FAILED: not all ten biomedical strata can meet their quota from the hypertension corpus.")
        print(json.dumps(report["candidate_pool_size_per_stratum"], indent=2))
        print("Per Stage 3 protocol: STOPPING before writing the 500-pair file. See feasibility report for shortfall detail.")
        return 1

    result = generate(seed=seed)
    selected, shortfall_report = sample_quota(result["stratified"], quotas, seed)

    now = datetime.now(timezone.utc).isoformat()
    for rec in selected:
        rec["generation_timestamp_utc"] = now

    # Final licence re-check immediately before writing the redistributable file.
    bad_licence = [r for r in selected if r["source_licence"] not in ("CC BY", "CC0")]
    if bad_licence:
        print(f"ABORT: {len(bad_licence)} selected pairs have unverified licence -- refusing to write.")
        return 1

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(selected)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")

    import hashlib

    det_cols = [c for c in df.columns if c != "generation_timestamp_utc"]
    det_payload = df[det_cols].sort_values("pair_id").to_csv(index=False).encode("utf-8")
    determinism_hash = hashlib.sha256(det_payload).hexdigest()

    manifest = {
        "generated_at_utc": now,
        "random_seed": seed,
        "universe_size": result["universe_size"],
        "n_strict_eligible_keyword_rows": result["n_strict_eligible_keyword_rows"],
        "n_contributing_articles": result["n_contributing_articles"],
        "quotas": quotas,
        "shortfall_report": shortfall_report,
        "total_selected": len(selected),
        "stratum_counts": {s: sum(1 for r in selected if r["candidate_stratum"] == s) for s in quotas if s != "total"},
        "all_licences_verified_cc_by_or_cc0": True,
        "pair_ids": sorted(r["pair_id"] for r in selected),
        "determinism_hash_excl_timestamp": determinism_hash,
        "output_file_relative_path": "strengthening/benchmark/biomedical_500_annotation_candidates_unlabelled.csv",
    }
    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Wrote {len(selected)} biomedical candidate pairs to {OUT_CSV}")
    print(json.dumps({k: v for k, v in manifest.items() if k != "pair_ids"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
