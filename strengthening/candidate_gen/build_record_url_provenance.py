"""Optional (per Step "IMPORTANT -- SCOPUS/PMC LINKS"): preserve REAL,
non-fabricated source-record URLs for future QA use, WITHOUT wiring them
into the annotator GUI's normal path (the GUI's More Context popup shows
only the frozen up-to-three titles, never a record URL).

CE: uses the corpus's own "Link" column (a real Scopus record.uri URL
already present in the source export -- not constructed/guessed).
Diabetes: constructs the official NCBI PMC article URL from the verified
PMCID (https://pmc.ncbi.nlm.nih.gov/articles/<PMCID>/ is NCBI's own,
documented URL scheme, not a fabricated pattern).

Output is restricted (kept under restricted_local, gitignored) and is not
read by strengthening/human_annotation/gui/*.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
ARTICLE7_ROOT = STRENGTHENING_ROOT.parent.parent
CE_CORPUS = ARTICLE7_ROOT / "concept_harmonisation" / "data" / "interim" / "scopus_ce_merged_deduped.csv"

OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "_provenance_only"
MAX_RECORDS = 3


def build_ce_urls(strings: set[str]) -> pd.DataFrame:
    corpus = pd.read_csv(CE_CORPUS, low_memory=False, usecols=["Title", "Author Keywords", "Link"])
    corpus = corpus.dropna(subset=["Author Keywords", "Link"])

    kw_to_records: dict[str, list[tuple[str, str]]] = {s: [] for s in strings}
    for _, row in corpus.iterrows():
        entries = [e.strip() for e in str(row["Author Keywords"]).split(";")]
        for kw in entries:
            if kw in kw_to_records:
                kw_to_records[kw].append((str(row["Title"]), str(row["Link"])))

    rows = []
    for s in sorted(strings):
        recs = sorted(set(kw_to_records.get(s, [])))[:MAX_RECORDS]
        row = {"keyword_string": s}
        for i in range(MAX_RECORDS):
            row[f"title_{i+1}"] = recs[i][0] if i < len(recs) else ""
            row[f"scopus_link_{i+1}"] = recs[i][1] if i < len(recs) else ""
        rows.append(row)
    return pd.DataFrame(rows)


def build_diabetes_urls(strings: set[str]) -> pd.DataFrame:
    kw = pd.read_csv(STRENGTHENING_ROOT / "data_pmc" / "pmc_diabetes_author_keywords_raw.csv", low_memory=False)
    inv = pd.read_csv(STRENGTHENING_ROOT / "data_pmc" / "pmc_diabetes_article_inventory.csv", low_memory=False)
    pmcid_to_title = dict(zip(inv["pmcid"], inv["title"]))

    strict = kw[(kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author")]
    kw_to_records: dict[str, list[tuple[str, str, str]]] = {s: [] for s in strings}
    for _, row in strict.iterrows():
        s = row["keyword_raw"]
        if s in kw_to_records:
            pmcid = row["pmcid"]
            title = pmcid_to_title.get(pmcid)
            if isinstance(title, str) and title.strip():
                url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
                kw_to_records[s].append((title, pmcid, url))

    rows = []
    for s in sorted(strings):
        recs = sorted(set(kw_to_records.get(s, [])))[:MAX_RECORDS]
        row = {"keyword_string": s}
        for i in range(MAX_RECORDS):
            row[f"title_{i+1}"] = recs[i][0] if i < len(recs) else ""
            row[f"pmcid_{i+1}"] = recs[i][1] if i < len(recs) else ""
            row[f"pmc_url_{i+1}"] = recs[i][2] if i < len(recs) else ""
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    context_dir = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "_intermediate"

    ce_ctx = pd.read_csv(context_dir / "context_lookup_ce.csv")
    ce_urls = build_ce_urls(set(ce_ctx["keyword_string"]))
    ce_urls.to_csv(OUT_DIR / "record_urls_ce.csv", index=False, encoding="utf-8")
    print(f"CE record URLs: {(ce_urls['scopus_link_1'] != '').sum()} / {len(ce_urls)} strings have >=1 real Scopus link")

    bio_ctx = pd.read_csv(context_dir / "context_lookup_diabetes.csv")
    bio_urls = build_diabetes_urls(set(bio_ctx["keyword_string"]))
    bio_urls.to_csv(OUT_DIR / "record_urls_diabetes.csv", index=False, encoding="utf-8")
    print(f"Diabetes record URLs: {(bio_urls['pmc_url_1'] != '').sum()} / {len(bio_urls)} strings have >=1 real PMC URL")


if __name__ == "__main__":
    main()
