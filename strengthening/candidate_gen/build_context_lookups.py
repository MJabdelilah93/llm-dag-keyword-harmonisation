"""Optional bounded context: up to 3 representative article titles per
keyword/string appearing anywhere in the primary benchmarks or the
Scenario-E retrieval audit. CE context is derived read-only from the
local Scopus corpus (restricted, kept under restricted_local); diabetes
context is derived from the already-licence-verified PMC source records
(open, but still written to the same restricted package directory for
simplicity -- nothing about the diabetes context itself is sensitive).
Never includes abstracts. Deterministic selection (sorted title order).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
ARTICLE7_ROOT = STRENGTHENING_ROOT.parent.parent
CE_CORPUS = ARTICLE7_ROOT / "concept_harmonisation" / "data" / "interim" / "scopus_ce_merged_deduped.csv"

OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "_intermediate"
MAX_TITLES = 3


def collect_strings(*csvs_and_cols: tuple[Path, list[str]]) -> set[str]:
    strings: set[str] = set()
    for path, cols in csvs_and_cols:
        df = pd.read_csv(path, low_memory=False)
        for c in cols:
            strings.update(df[c].dropna().astype(str).tolist())
    return strings


def build_ce_context(strings: set[str]) -> pd.DataFrame:
    corpus = pd.read_csv(CE_CORPUS, low_memory=False, usecols=["Title", "Author Keywords"])
    corpus = corpus.dropna(subset=["Author Keywords", "Title"])

    # keyword (as it appears in the CE benchmark/retrieval, i.e. author-keyword
    # casing) -> sorted list of titles whose Author Keywords field contains it
    # as one semicolon-separated entry (exact match, not substring, to avoid
    # false hits like "recycling" matching "electronic waste recycling").
    kw_to_titles: dict[str, list[str]] = {s: [] for s in strings}
    for _, row in corpus.iterrows():
        entries = [e.strip() for e in str(row["Author Keywords"]).split(";")]
        title = str(row["Title"])
        for kw in entries:
            if kw in kw_to_titles:
                kw_to_titles[kw].append(title)

    rows = []
    for s in sorted(strings):
        titles = sorted(set(kw_to_titles.get(s, [])))[:MAX_TITLES]
        rows.append(
            {
                "keyword_string": s,
                "title_1": titles[0] if len(titles) > 0 else "",
                "title_2": titles[1] if len(titles) > 1 else "",
                "title_3": titles[2] if len(titles) > 2 else "",
            }
        )
    return pd.DataFrame(rows)


def build_diabetes_context(strings: set[str]) -> pd.DataFrame:
    kw = pd.read_csv(STRENGTHENING_ROOT / "data_pmc" / "pmc_diabetes_author_keywords_raw.csv", low_memory=False)
    inv = pd.read_csv(STRENGTHENING_ROOT / "data_pmc" / "pmc_diabetes_article_inventory.csv", low_memory=False)
    pmcid_to_title = dict(zip(inv["pmcid"], inv["title"]))

    strict = kw[(kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author")]
    kw_to_titles: dict[str, list[str]] = {s: [] for s in strings}
    for _, row in strict.iterrows():
        s = row["keyword_raw"]
        if s in kw_to_titles:
            title = pmcid_to_title.get(row["pmcid"])
            if isinstance(title, str) and title.strip():
                kw_to_titles[s].append(title)

    rows = []
    for s in sorted(strings):
        titles = sorted(set(kw_to_titles.get(s, [])))[:MAX_TITLES]
        rows.append(
            {
                "keyword_string": s,
                "title_1": titles[0] if len(titles) > 0 else "",
                "title_2": titles[1] if len(titles) > 1 else "",
                "title_3": titles[2] if len(titles) > 2 else "",
            }
        )
    return pd.DataFrame(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ce_benchmark = STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv"
    ce_retrieval = OUT_DIR / "scenario_e_ce_master.csv"
    ce_strings = collect_strings(
        (ce_benchmark, ["string_a", "string_b"]),
        (ce_retrieval, ["seed_string", "candidate_string"]),
    )
    ce_context = build_ce_context(ce_strings)
    ce_context.to_csv(OUT_DIR / "context_lookup_ce.csv", index=False, encoding="utf-8")
    ce_found = int((ce_context["title_1"] != "").sum())
    print(f"CE context: {len(ce_strings)} unique strings, {ce_found} with >=1 title found")

    bio_benchmark = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
    bio_retrieval = OUT_DIR / "scenario_e_bio_master.csv"
    bio_strings = collect_strings(
        (bio_benchmark, ["string_a", "string_b"]),
        (bio_retrieval, ["seed_string", "candidate_string"]),
    )
    bio_context = build_diabetes_context(bio_strings)
    bio_context.to_csv(OUT_DIR / "context_lookup_diabetes.csv", index=False, encoding="utf-8")
    bio_found = int((bio_context["title_1"] != "").sum())
    print(f"Diabetes context: {len(bio_strings)} unique strings, {bio_found} with >=1 title found")


if __name__ == "__main__":
    main()
