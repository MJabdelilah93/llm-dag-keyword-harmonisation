"""
assemble_benchmark.py  (Phase 3 — Task 3B)
--------------------------------------------
Assembles the final gold-standard benchmark from two annotator files
and an adjudication file.

Run AFTER Phase 2 annotation AND adjudication are complete.

Inputs (expected in data/benchmark/):
    annotation_sheet_annotator1_COMPLETED.csv
    annotation_sheet_annotator2_COMPLETED.csv
    adjudication_sheet.csv   (output of adjudicator resolving disagreements)

Outputs (written to data/benchmark/):
    gold_benchmark.csv       — final labelled benchmark
    table3_populated.csv     — Table 3 structure with counts

Usage:
    python scripts/assemble_benchmark.py
"""

import io
import pathlib
import sys

import pandas as pd

# ── UTF-8 stdout ──────────────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT  = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
BENCH = ROOT / "data" / "benchmark"

LABELS  = ["match", "non-match", "uncertain"]
STRATA  = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]

STRATUM_DESC = {
    "i": "Capitalisation / whitespace",
    "ii": "Spelling variants",
    "iii": "Acronym expansion",
    "iv": "Punctuation / hyphenation",
    "v": "Singular / plural",
    "vi": "Near-synonyms",
    "vii": "Broader-narrower",
    "viii": "Ambiguous short forms",
    "ix": "Malformed strings",
    "x": "Weak semantic links",
}


def load_and_clean(path, label_col):
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    df = df[df["pair_id"] != "INSTRUCTIONS"].copy()
    df[label_col] = df[label_col].str.strip().str.lower()
    df[label_col] = df[label_col].replace({"non_match": "non-match", "nonmatch": "non-match"})
    return df


def main():
    # ── Load annotator files ──────────────────────────────────────────────────
    for fname in ["annotation_sheet_annotator1_COMPLETED.csv",
                  "annotation_sheet_annotator2_COMPLETED.csv",
                  "adjudication_sheet.csv"]:
        if not (BENCH / fname).exists():
            print(f"ERROR: {fname} not found in {BENCH}")
            print("Complete Phase 2 annotation and adjudication before running this script.")
            sys.exit(1)

    df1  = load_and_clean(BENCH / "annotation_sheet_annotator1_COMPLETED.csv", "annotator1_label")
    df2  = load_and_clean(BENCH / "annotation_sheet_annotator2_COMPLETED.csv", "annotator2_label")
    dadj = load_and_clean(BENCH / "adjudication_sheet.csv", "adjudicator_label")

    # Merge all three on pair_id
    merged = (
        df1[["pair_id", "keyword_a", "keyword_b", "freq_a", "freq_b", "stratum",
              "annotator1_label", "annotator1_notes"]]
        .merge(df2[["pair_id", "annotator2_label", "annotator2_notes"]], on="pair_id", how="left")
        .merge(dadj[["pair_id", "adjudicator_label"]], on="pair_id", how="left")
    )
    n_total = len(merged)

    # ── Assign gold label ─────────────────────────────────────────────────────
    def gold_label(row):
        l1 = row["annotator1_label"]
        l2 = row["annotator2_label"]
        la = row["adjudicator_label"]

        if l1 == l2 and l1 in LABELS:
            return l1, "agreed"
        elif la in LABELS:
            return la, "adjudicated"
        else:
            # Both uncertain → retain uncertain; otherwise flag for review
            if l1 == "uncertain" and l2 == "uncertain":
                return "uncertain", "both_uncertain"
            return "uncertain", "unresolved"  # should not happen if adjudication is complete

    merged[["gold_label", "agreement_status"]] = merged.apply(
        lambda r: pd.Series(gold_label(r)), axis=1
    )

    # ── Report ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("BENCHMARK ASSEMBLY REPORT")
    print("=" * 65)
    print(f"\nTotal pairs: {n_total}")

    print("\nAgreement status breakdown:")
    for status, count in merged["agreement_status"].value_counts().items():
        print(f"  {status:<20} {count:>5}  ({count/n_total*100:.1f}%)")

    print("\nGold label distribution:")
    for lbl in LABELS:
        n = (merged["gold_label"] == lbl).sum()
        print(f"  {lbl:<15} {n:>5}  ({n/n_total*100:.1f}%)")

    unresolved = (merged["agreement_status"] == "unresolved").sum()
    if unresolved > 0:
        print(f"\nWARNING: {unresolved} pairs have unresolved labels.")
        print("Review adjudication_sheet.csv for completeness.")

    # ── Per-stratum × label counts (Table 3 structure) ────────────────────────
    print("\nPer-stratum gold label distribution:")
    print(f"\n  {'Stratum':<8} {'Description':<28} {'Match':>7} {'Non-match':>11} {'Uncertain':>11} {'Total':>7}")
    print(f"  {'-'*8} {'-'*28} {'-'*7} {'-'*11} {'-'*11} {'-'*7}")

    table3_rows = []
    for s in STRATA:
        sub = merged[merged["stratum"] == s]
        n_m  = (sub["gold_label"] == "match").sum()
        n_nm = (sub["gold_label"] == "non-match").sum()
        n_u  = (sub["gold_label"] == "uncertain").sum()
        n_s  = len(sub)
        desc = STRATUM_DESC.get(s, "")
        print(f"  {s:<8} {desc:<28} {n_m:>7} {n_nm:>11} {n_u:>11} {n_s:>7}")
        table3_rows.append({
            "stratum": s, "description": desc,
            "n_match": n_m, "n_non_match": n_nm, "n_uncertain": n_u, "n_total": n_s,
            "pct_match": round(n_m / n_s * 100, 1) if n_s > 0 else 0,
        })

    totals = merged.agg({"gold_label": lambda x: x.value_counts().to_dict()})
    n_m_t  = (merged["gold_label"] == "match").sum()
    n_nm_t = (merged["gold_label"] == "non-match").sum()
    n_u_t  = (merged["gold_label"] == "uncertain").sum()
    print(f"  {'TOTAL':<8} {'':<28} {n_m_t:>7} {n_nm_t:>11} {n_u_t:>11} {n_total:>7}")

    # ── Save outputs ──────────────────────────────────────────────────────────
    gold_cols = ["pair_id", "keyword_a", "keyword_b", "freq_a", "freq_b",
                 "stratum", "gold_label", "agreement_status"]
    gold_path = BENCH / "gold_benchmark.csv"
    merged[gold_cols].to_csv(gold_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {gold_path}")

    df_t3 = pd.DataFrame(table3_rows)
    t3_path = BENCH / "table3_populated.csv"
    df_t3.to_csv(t3_path, index=False, encoding="utf-8-sig")
    print(f"Saved: {t3_path}")

    print("\nNext step: run split_benchmark.py to create dev/test splits.")


if __name__ == "__main__":
    main()
