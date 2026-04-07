"""
compute_agreement.py  (Phase 3 — Task 3A)
------------------------------------------
Computes inter-annotator agreement between two completed annotation files.

Run AFTER Phase 2 annotation is complete.

Inputs (expected in data/benchmark/):
    annotation_sheet_annotator1_COMPLETED.csv
    annotation_sheet_annotator2_COMPLETED.csv

Outputs (written to data/benchmark/):
    agreement_report.txt        — human-readable summary
    agreement_statistics.csv    — kappa + % agreement per stratum
    disagreement_pairs.csv      — pairs needing adjudication

Usage:
    python scripts/compute_agreement.py
    python scripts/compute_agreement.py --a1 path/to/ann1.csv --a2 path/to/ann2.csv
"""

import argparse
import io
import pathlib
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

# ── UTF-8 stdout (Windows) ────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT  = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
BENCH = ROOT / "data" / "benchmark"

LABELS = ["match", "non-match", "uncertain"]

STRATA = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]

STRATUM_DESC = {
    "i":    "Capitalisation / whitespace variants",
    "ii":   "Spelling variants (JW)",
    "iii":  "Acronym expansion",
    "iv":   "Punctuation / hyphenation variants",
    "v":    "Singular / plural",
    "vi":   "Near-synonyms (embedding)",
    "vii":  "Broader-narrower proxies (embedding)",
    "viii": "Ambiguous short forms",
    "ix":   "Malformed strings",
    "x":    "Weak semantic links (embedding)",
}


def load_annotations(path: pathlib.Path, label_col: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    # Drop instruction row if present
    df = df[df["pair_id"] != "INSTRUCTIONS"].copy()
    df["pair_id"]    = df["pair_id"].str.strip()
    if "stratum" in df.columns:
        df["stratum"] = df["stratum"].str.strip()
    df[label_col]    = df[label_col].str.strip().str.lower()
    # Map "non_match" or "nonmatch" to canonical "non-match"
    df[label_col] = df[label_col].replace({"non_match": "non-match", "nonmatch": "non-match"})
    return df


def safe_kappa(y1, y2, labels=LABELS):
    """Cohen's kappa, returning NaN if computation is impossible (<2 labels present)."""
    try:
        return cohen_kappa_score(y1, y2, labels=labels)
    except Exception:
        return float("nan")


def pct_agree(y1, y2):
    if len(y1) == 0:
        return float("nan")
    return (y1 == y2).mean() * 100


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--a1", default=str(BENCH / "annotation_sheet_annotator1_COMPLETED.csv"))
    parser.add_argument("--a2", default=str(BENCH / "annotation_sheet_annotator2_COMPLETED.csv"))
    args = parser.parse_args()

    # Resolve relative paths against ROOT so the script works regardless of CWD
    def _resolve(p: str) -> pathlib.Path:
        q = pathlib.Path(p)
        return q if q.is_absolute() else ROOT / q

    path_a1 = _resolve(args.a1)
    path_a2 = _resolve(args.a2)

    for p in (path_a1, path_a2):
        if not p.exists():
            print(f"ERROR: File not found: {p}")
            print("Run Phase 2 (annotation campaign) before running this script.")
            sys.exit(1)

    print("Loading annotator files ...")
    df1 = load_annotations(path_a1, "annotator1_label")
    df2 = load_annotations(path_a2, "annotator2_label")

    # If stratum/freq columns are missing (stripped COMPLETED files), backfill from
    # pilot_pairs.csv or candidate_pairs.csv (whichever exists).
    meta_cols = ["pair_id", "keyword_a", "keyword_b", "freq_a", "freq_b", "stratum"]
    if "stratum" not in df1.columns:
        for meta_file in ("pilot_pairs.csv", "candidate_pairs.csv"):
            meta_path = BENCH / meta_file
            if meta_path.exists():
                meta = pd.read_csv(meta_path, encoding="utf-8-sig", dtype=str)[meta_cols]
                df1 = meta.merge(df1[["pair_id", "annotator1_label", "annotator1_notes"]],
                                 on="pair_id", how="inner")
                print(f"  Enriched annotator1 file from {meta_file} ({len(df1)} pairs)")
                break
    if "stratum" not in df2.columns:
        for meta_file in ("pilot_pairs.csv", "candidate_pairs.csv"):
            meta_path = BENCH / meta_file
            if meta_path.exists():
                meta = pd.read_csv(meta_path, encoding="utf-8-sig", dtype=str)[meta_cols]
                df2 = meta.merge(df2[["pair_id", "annotator2_label", "annotator2_notes"]],
                                 on="pair_id", how="inner")
                print(f"  Enriched annotator2 file from {meta_file} ({len(df2)} pairs)")
                break

    # Merge on pair_id
    merged = df1.merge(df2[["pair_id", "annotator2_label", "annotator2_notes"]],
                       on="pair_id", how="inner")
    n_total = len(merged)
    print(f"Matched pairs: {n_total}")

    # Filter to pairs where both annotators provided a valid label
    valid_labels = set(LABELS)
    has_valid = (
        merged["annotator1_label"].isin(valid_labels) &
        merged["annotator2_label"].isin(valid_labels)
    )
    merged_valid = merged[has_valid].copy()
    n_valid = len(merged_valid)
    n_missing = n_total - n_valid
    print(f"Pairs with valid labels from both annotators: {n_valid} (missing/invalid: {n_missing})")

    y1 = merged_valid["annotator1_label"].values
    y2 = merged_valid["annotator2_label"].values

    # ── Global statistics ─────────────────────────────────────────────────────
    kappa_global = safe_kappa(y1, y2)
    pct_ag_global = pct_agree(pd.Series(y1), pd.Series(y2))
    agree_mask = (y1 == y2)
    n_agree = agree_mask.sum()
    n_disagree = (~agree_mask).sum()

    # Confusion matrix
    cm = confusion_matrix(y1, y2, labels=LABELS)

    # Label distribution
    counts1 = pd.Series(y1).value_counts().reindex(LABELS, fill_value=0)
    counts2 = pd.Series(y2).value_counts().reindex(LABELS, fill_value=0)

    # ── Per-stratum statistics ────────────────────────────────────────────────
    stratum_stats = []
    for s in STRATA:
        sub = merged_valid[merged_valid["stratum"] == s]
        n_s = len(sub)
        if n_s == 0:
            stratum_stats.append({
                "stratum": s, "n_pairs": 0,
                "pct_agreement": float("nan"), "cohen_kappa": float("nan"),
                "n_agree": 0, "n_disagree": 0,
            })
            continue
        s_y1 = sub["annotator1_label"].values
        s_y2 = sub["annotator2_label"].values
        stratum_stats.append({
            "stratum":        s,
            "n_pairs":        n_s,
            "pct_agreement":  round(pct_agree(pd.Series(s_y1), pd.Series(s_y2)), 1),
            "cohen_kappa":    round(safe_kappa(s_y1, s_y2), 4),
            "n_agree":        int((s_y1 == s_y2).sum()),
            "n_disagree":     int((s_y1 != s_y2).sum()),
        })
    df_stratum = pd.DataFrame(stratum_stats)

    # ── Disagreement pairs ────────────────────────────────────────────────────
    disagree_df = merged_valid[~agree_mask][
        ["pair_id", "keyword_a", "keyword_b", "freq_a", "freq_b", "stratum",
         "annotator1_label", "annotator1_notes", "annotator2_label", "annotator2_notes"]
    ].copy()
    disagree_df["adjudicator_label"] = ""
    disagree_df["adjudicator_notes"] = ""

    # ── Build human-readable report ───────────────────────────────────────────
    lines = [
        "=" * 72,
        "INTER-ANNOTATOR AGREEMENT REPORT",
        "=" * 72,
        "",
        f"Annotation files:",
        f"  Annotator 1: {path_a1.name}",
        f"  Annotator 2: {path_a2.name}",
        "",
        f"Total pairs in benchmark:          {n_total}",
        f"Pairs with valid labels (both):    {n_valid}",
        f"Pairs with missing/invalid labels: {n_missing}",
        "",
        "── OVERALL AGREEMENT ──────────────────────────────────────────────",
        f"  Percentage agreement:  {pct_ag_global:.1f}%",
        f"  Cohen's kappa (κ):     {kappa_global:.4f}",
        f"  Agreed pairs:          {n_agree}",
        f"  Disagreement pairs:    {n_disagree}",
        "",
        "── LABEL DISTRIBUTION ─────────────────────────────────────────────",
        f"  {'Label':<15} {'Annotator 1':>13} {'Annotator 2':>13}",
        f"  {'-'*15} {'-'*13} {'-'*13}",
    ]
    for lbl in LABELS:
        lines.append(f"  {lbl:<15} {counts1[lbl]:>13} {counts2[lbl]:>13}")

    lines += [
        "",
        "── CONFUSION MATRIX ───────────────────────────────────────────────",
        "  Rows = Annotator 1, Columns = Annotator 2",
        f"  {'':>14} " + "  ".join(f"{l:>12}" for l in LABELS),
        f"  {'-'*14}   " + "  ".join(["-" * 12] * 3),
    ]
    for i, row_label in enumerate(LABELS):
        row_vals = "  ".join(f"{cm[i][j]:>12}" for j in range(len(LABELS)))
        lines.append(f"  {row_label:<14} {row_vals}")

    lines += [
        "",
        "── PER-STRATUM AGREEMENT ──────────────────────────────────────────",
        f"  {'Str':<5} {'Description':<38} {'N':>5} {'Agree%':>8} {'Kappa':>8} {'Disagree':>9}",
        f"  {'-'*5} {'-'*38} {'-'*5} {'-'*8} {'-'*8} {'-'*9}",
    ]
    for _, row in df_stratum.iterrows():
        kappa_s = f"{row['cohen_kappa']:.4f}" if not np.isnan(row["cohen_kappa"]) else "  N/A"
        pct_s   = f"{row['pct_agreement']:.1f}%" if not np.isnan(row["pct_agreement"]) else "  N/A"
        desc    = STRATUM_DESC.get(row["stratum"], "")
        lines.append(
            f"  {row['stratum']:<5} {desc:<38} {int(row['n_pairs']):>5} "
            f"{pct_s:>8} {kappa_s:>8} {int(row['n_disagree']):>9}"
        )

    lines += [
        "",
        "── KAPPA INTERPRETATION ───────────────────────────────────────────",
        "  κ < 0.40  : Poor",
        "  0.40–0.59 : Moderate",
        "  0.60–0.79 : Substantial",
        "  0.80–1.00 : Almost perfect  (Landis & Koch, 1977)",
        "",
        "── NEXT STEPS ─────────────────────────────────────────────────────",
        f"  Adjudicate {n_disagree} disagreement pairs using disagreement_pairs.csv.",
        "  Run assemble_benchmark.py after adjudication is complete.",
        "",
    ]
    report_text = "\n".join(lines)
    print("\n" + report_text)

    # ── Save outputs ──────────────────────────────────────────────────────────
    report_path = BENCH / "agreement_report.txt"
    report_path.write_text(report_text, encoding="utf-8")
    print(f"Saved: {report_path}")

    stats_path = BENCH / "agreement_statistics.csv"
    df_stratum.to_csv(stats_path, index=False, encoding="utf-8-sig")
    print(f"Saved: {stats_path}")

    disagree_path = BENCH / "disagreement_pairs.csv"
    disagree_df.to_csv(disagree_path, index=False, encoding="utf-8-sig")
    print(f"Saved: {disagree_path}  ({len(disagree_df)} pairs needing adjudication)")


if __name__ == "__main__":
    main()
