"""
ingest_profile.py
-----------------
Steps 1-6: Inspect, merge, deduplicate, and profile the two Scopus CSV batches.
Outputs written to data/interim/ and data/derived/ (data/raw/ is never modified).
"""

import sys, io, pathlib, pandas as pd

# Force UTF-8 output on Windows terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---- Paths -------------------------------------------------------------------
ROOT    = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
RAW     = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
DERIVED = ROOT / "data" / "derived"
INTERIM.mkdir(parents=True, exist_ok=True)
DERIVED.mkdir(parents=True, exist_ok=True)

BATCH1_PATH = RAW / "scopus_ce_batch1_2017_2021.csv"
BATCH2_PATH = RAW / "export_62ecbf9b-a296-49ba-b98e-e70c1b160370_2026-04-02T223857.46602659.csv"

# ── Helper ─────────────────────────────────────────────────────────────────────
def load_csv(path: pathlib.Path) -> pd.DataFrame:
    """Try utf-8-sig first (handles BOM), fall back to latin-1."""
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc, low_memory=False)
            print(f"  Loaded {path.name!r} with encoding={enc!r}")
            return df
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not decode {path}")


def keyword_counts(series: pd.Series):
    """Split semicolon-separated keyword cells; return Counter of individual kws."""
    from collections import Counter
    counter: Counter = Counter()
    for cell in series.dropna():
        for kw in str(cell).split(";"):
            kw = kw.strip()
            if kw:
                counter[kw] += 1
    return counter


def freq_band(counter, lo, hi):
    """Count unique keywords whose frequency is in [lo, hi] (hi=None means >=lo)."""
    if hi is None:
        return sum(1 for v in counter.values() if v >= lo)
    return sum(1 for v in counter.values() if lo <= v <= hi)


def pct(n, total):
    return f"{n / total * 100:.1f}%" if total else "N/A"


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Inspect both CSVs
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 1 — INSPECT BOTH CSVs")
print("=" * 70)

print("\nNOTE: 'scopus_ce_batch2_2022_2024.csv' was not present in data/raw/.")
print("The file 'export_62ecbf9b-..._2026-04-02T223857.csv' has the identical")
print("column structure as batch1 and its first records match the batch2 RIS")
print("export (same EIDs, Year=2022–2024). It is used as the batch2 CSV.\n")

df1 = load_csv(BATCH1_PATH)
df2 = load_csv(BATCH2_PATH)

for label, df in (("Batch 1 (2017–2021)", df1), ("Batch 2 (2022–2024)", df2)):
    print(f"\n--- {label} ---")
    print(f"  Shape:   {df.shape[0]} rows × {df.shape[1]} columns")
    print(f"  Columns: {list(df.columns)}")
    print(f"  First 3 rows (selected columns):")
    preview_cols = ["EID", "Title", "Year", "Document Type", "Author Keywords"]
    available = [c for c in preview_cols if c in df.columns]
    print(df[available].head(3).to_string(index=False))

same_cols = list(df1.columns) == list(df2.columns)
print(f"\nColumn structure identical: {same_cols}")
if not same_cols:
    only1 = set(df1.columns) - set(df2.columns)
    only2 = set(df2.columns) - set(df1.columns)
    if only1: print(f"  Only in batch1: {only1}")
    if only2: print(f"  Only in batch2: {only2}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Merge and deduplicate
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 2 — MERGE AND DEDUPLICATE")
print("=" * 70)

df_merged = pd.concat([df1, df2], ignore_index=True)
n_before = len(df_merged)
print(f"\nTotal rows before deduplication: {n_before}")

# Identify EID column
eid_col = next((c for c in df_merged.columns if c.strip().upper() == "EID"), None)
if eid_col is None:
    # fallback: look for column containing '2-s2.0-' values
    for c in df_merged.columns:
        if df_merged[c].astype(str).str.contains("2-s2.0-", na=False).mean() > 0.5:
            eid_col = c
            break
print(f"EID column identified: {eid_col!r}")

df_deduped = df_merged.drop_duplicates(subset=[eid_col]).reset_index(drop=True)
n_after   = len(df_deduped)
n_dupes   = n_before - n_after
print(f"Total rows after deduplication:  {n_after}")
print(f"Duplicates removed:              {n_dupes}")

out_merged = INTERIM / "scopus_ce_merged_deduped.csv"
df_deduped.to_csv(out_merged, index=False, encoding="utf-8-sig")
print(f"\nSaved merged file → {out_merged}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Field inventory
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 3 — FIELD INVENTORY")
print("=" * 70)

n_total = len(df_deduped)
print(f"\nAll columns in merged file ({df_deduped.shape[1]} total):\n")
print(f"  {'#':<4} {'Column':<40} {'dtype':<12} {'Non-null':>10} {'%':>8}")
print(f"  {'-'*4} {'-'*40} {'-'*12} {'-'*10} {'-'*8}")
for i, col in enumerate(df_deduped.columns, 1):
    nn  = df_deduped[col].notna().sum()
    pct_nn = f"{nn / n_total * 100:.1f}%"
    print(f"  {i:<4} {col:<40} {str(df_deduped[col].dtype):<12} {nn:>10} {pct_nn:>8}")

# Identify key columns
def find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    # case-insensitive fallback
    cl = {x.lower(): x for x in df.columns}
    for c in candidates:
        if c.lower() in cl:
            return cl[c.lower()]
    return None

ak_col   = find_col(df_deduped, ["Author Keywords", "author keywords", "DE"])
ik_col   = find_col(df_deduped, ["Index Keywords", "index keywords", "ID"])
title_col= find_col(df_deduped, ["Title", "title", "TI"])
abs_col  = find_col(df_deduped, ["Abstract", "abstract", "AB"])
doi_col  = find_col(df_deduped, ["DOI", "doi"])
year_col = find_col(df_deduped, ["Year", "year", "PY"])
src_col  = find_col(df_deduped, ["Source title", "source title", "SO"])
doctype_col = find_col(df_deduped, ["Document Type", "document type", "DT"])
lang_col = find_col(df_deduped, ["Language of Original Document", "Language", "LA"])

print(f"\nKey column mapping:")
print(f"  Author Keywords  → {ak_col!r}")
print(f"  Index Keywords   → {ik_col!r}")
print(f"  Title            → {title_col!r}")
print(f"  Abstract         → {abs_col!r}")
print(f"  DOI              → {doi_col!r}")
print(f"  Year             → {year_col!r}")
print(f"  Source title     → {src_col!r}")
print(f"  Document type    → {doctype_col!r}")
print(f"  Language         → {lang_col!r}")

print(f"\n5 sample AUTHOR KEYWORD cells:")
for v in df_deduped[ak_col].dropna().head(5):
    print(f"  {str(v)[:120]}")

print(f"\n5 sample INDEX KEYWORD cells:")
for v in df_deduped[ik_col].dropna().head(5):
    print(f"  {str(v)[:120]}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Keyword inventory and frequency distribution
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 4 — KEYWORD INVENTORY AND FREQUENCY DISTRIBUTION")
print("=" * 70)

def profile_keywords(df, col, label):
    n_total = len(df)
    has_kw   = df[col].notna() & (df[col].astype(str).str.strip() != "")
    n_with   = has_kw.sum()
    n_miss   = n_total - n_with
    counter  = keyword_counts(df[col])
    n_occ    = sum(counter.values())
    n_unique = len(counter)

    print(f"\n  {label}")
    print(f"    Records with keywords:     {n_with:>7}  ({pct(n_with, n_total)} of total)")
    print(f"    Records missing keywords:  {n_miss:>7}")
    print(f"    Total occurrences:         {n_occ:>7}")
    print(f"    Unique strings:            {n_unique:>7}")
    return counter, n_with, n_miss, n_occ, n_unique

print()
ak_counter, ak_with, ak_miss, ak_occ, ak_unique = profile_keywords(df_deduped, ak_col, "AUTHOR KEYWORDS")
ik_counter, ik_with, ik_miss, ik_occ, ik_unique = profile_keywords(df_deduped, ik_col, "INDEX KEYWORDS")

# Frequency distribution for author keywords
print("\n  AUTHOR KEYWORD frequency bands:")
bands = [
    ("f = 1  (singletons)",   1,  1),
    ("f = 2–4",               2,  4),
    ("f = 5–9",               5,  9),
    ("f = 10–49",            10, 49),
    ("f = 50–99",            50, 99),
    ("f >= 100",            100, None),
]
ak_ge5  = freq_band(ak_counter, 5,  None)
ak_ge10 = freq_band(ak_counter, 10, None)
ak_f1   = freq_band(ak_counter, 1, 1)

for desc, lo, hi in bands:
    n = freq_band(ak_counter, lo, hi)
    print(f"    {desc:<28} {n:>6}  ({pct(n, ak_unique)} of unique)")

print(f"\n  Top 20 most frequent AUTHOR KEYWORDS:")
print(f"    {'Rank':<6} {'Keyword':<50} {'Count':>6}")
print(f"    {'-'*6} {'-'*50} {'-'*6}")
for rank, (kw, cnt) in enumerate(ak_counter.most_common(20), 1):
    print(f"    {rank:<6} {kw:<50} {cnt:>6}")

print(f"\n  Bottom 20 AUTHOR KEYWORDS (lowest frequency, singletons sample):")
bottom20 = sorted(ak_counter.items(), key=lambda x: (x[1], x[0]))[:20]
print(f"    {'Keyword':<50} {'Count':>6}")
print(f"    {'-'*50} {'-'*6}")
for kw, cnt in bottom20:
    print(f"    {kw:<50} {cnt:>6}")

# Save frequency tables
ak_freq_df = pd.DataFrame(
    sorted(ak_counter.items(), key=lambda x: -x[1]),
    columns=["keyword", "frequency"]
)
ik_freq_df = pd.DataFrame(
    sorted(ik_counter.items(), key=lambda x: -x[1]),
    columns=["keyword", "frequency"]
)

ak_out = DERIVED / "author_keyword_frequencies.csv"
ik_out = DERIVED / "index_keyword_frequencies.csv"
ak_freq_df.to_csv(ak_out, index=False, encoding="utf-8-sig")
ik_freq_df.to_csv(ik_out, index=False, encoding="utf-8-sig")
print(f"\n  Saved author keyword frequencies → {ak_out}")
print(f"  Saved index  keyword frequencies → {ik_out}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Summary report (Table 2)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 5 — CORPUS SUMMARY FOR TABLE 2")
print("=" * 70)

n_with_abs   = df_deduped[abs_col].notna().sum()  if abs_col  else 0
n_with_title = df_deduped[title_col].notna().sum() if title_col else 0
ik_f1 = freq_band(ik_counter, 1, 1)

summary = f"""
=== CORPUS SUMMARY FOR TABLE 2 ===
Source database:                Scopus
Search query:                   TITLE-ABS-KEY("circular economy" OR "circular economies")
Date filters:                   PUBYEAR > 2016 AND PUBYEAR < 2025
Document types:                 Articles and reviews
Language:                       English
Retrieval date:                 3 April 2026
Batch 1 records:                {len(df1)}
Batch 2 records:                {len(df2)}
Merged records (pre-dedup):     {n_before}
Final records (post-dedup):     {n_after}
Duplicates removed:             {n_dupes}

--- AUTHOR KEYWORDS ---
Records with author keywords:   {ak_with} ({pct(ak_with, n_after)} of total)
Records missing author keywords:{ak_miss}
Total AK occurrences:           {ak_occ}
Unique AK strings:              {ak_unique}
Singletons (f=1):               {ak_f1} ({pct(ak_f1, ak_unique)} of unique)
AK with f >= 5:                 {ak_ge5} ({pct(ak_ge5, ak_unique)} of unique)
AK with f >= 10:                {ak_ge10} ({pct(ak_ge10, ak_unique)} of unique)

--- INDEX KEYWORDS ---
Records with index keywords:    {ik_with} ({pct(ik_with, n_after)} of total)
Records missing index keywords: {ik_miss}
Total IK occurrences:           {ik_occ}
Unique IK strings:              {ik_unique}
Singletons (f=1):               {ik_f1} ({pct(ik_f1, ik_unique)} of unique)

--- AUXILIARY FIELDS ---
Records with abstracts:         {n_with_abs} ({pct(n_with_abs, n_after)} of total)
Records with titles:            {n_with_title} ({pct(n_with_title, n_after)} of total)
"""

print(summary)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Save summary report
# ══════════════════════════════════════════════════════════════════════════════
report_path = DERIVED / "corpus_summary_report.txt"
report_path.write_text(summary, encoding="utf-8")
print(f"Saved summary report → {report_path}")
print("\nDone.\n")
