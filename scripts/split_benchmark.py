"""
split_benchmark.py  (Phase 3 — Task 3C)
-----------------------------------------
Creates stratified 70/30 dev/test splits of the gold benchmark,
preserving label distribution within each difficulty stratum.

Run AFTER assemble_benchmark.py produces gold_benchmark.csv.

Inputs:
    data/benchmark/gold_benchmark.csv

Outputs:
    data/benchmark/dev_set.csv          (~70%, ~350 pairs)
    data/benchmark/test_set.csv         (~30%, ~150 pairs)
    data/benchmark/split_summary.txt    (distribution report)

Usage:
    python scripts/split_benchmark.py
"""

import io
import pathlib
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

# ── UTF-8 stdout ──────────────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SEED = 42
ROOT  = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
BENCH = ROOT / "data" / "benchmark"

LABELS = ["match", "non-match", "uncertain"]
STRATA = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]


def main():
    gold_path = BENCH / "gold_benchmark.csv"
    if not gold_path.exists():
        print(f"ERROR: {gold_path} not found.")
        print("Run assemble_benchmark.py first.")
        sys.exit(1)

    df = pd.read_csv(gold_path, encoding="utf-8-sig", dtype=str)
    df = df[df["pair_id"] != "INSTRUCTIONS"].copy()
    n_total = len(df)
    print(f"Loaded {n_total} pairs from gold_benchmark.csv")

    # Composite stratification key: stratum + gold_label
    # This preserves both stratum proportions and label distributions within strata
    df["strat_key"] = df["stratum"] + "_" + df["gold_label"]

    # Remove strat_keys with only 1 member (can't split)
    key_counts = df["strat_key"].value_counts()
    singleton_keys = key_counts[key_counts == 1].index.tolist()
    if singleton_keys:
        print(f"WARNING: {len(singleton_keys)} stratum×label cell(s) have only 1 member.")
        print("  These will be assigned to dev set to avoid empty test cells.")
        print(f"  Cells: {singleton_keys}")

    df_singleton = df[df["strat_key"].isin(singleton_keys)].copy()
    df_splittable = df[~df["strat_key"].isin(singleton_keys)].copy()

    # StratifiedShuffleSplit on the splittable subset
    n_test_target = max(1, int(round(len(df_splittable) * 0.30)))
    splitter = StratifiedShuffleSplit(n_splits=1, test_size=n_test_target, random_state=SEED)

    X_dummy = np.zeros(len(df_splittable))
    y_strat = df_splittable["strat_key"].values

    for train_idx, test_idx in splitter.split(X_dummy, y_strat):
        dev_from_split  = df_splittable.iloc[train_idx]
        test_from_split = df_splittable.iloc[test_idx]

    df_dev  = pd.concat([dev_from_split, df_singleton], ignore_index=True)
    df_test = test_from_split.copy()

    n_dev  = len(df_dev)
    n_test = len(df_test)

    print(f"\nSplit: {n_dev} dev ({n_dev/n_total*100:.1f}%) | "
          f"{n_test} test ({n_test/n_total*100:.1f}%)")

    # ── Verification: check proportions within ±5% ────────────────────────────
    print("\nVerification — label distribution:")
    print(f"  {'Label':<15} {'Full%':>8} {'Dev%':>8} {'Test%':>8} {'OK?':>5}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*8} {'-'*5}")
    all_ok = True
    for lbl in LABELS:
        full_pct = (df["gold_label"] == lbl).mean() * 100
        dev_pct  = (df_dev["gold_label"] == lbl).mean() * 100
        test_pct = (df_test["gold_label"] == lbl).mean() * 100
        ok = abs(dev_pct - full_pct) <= 5.0 and abs(test_pct - full_pct) <= 5.0
        if not ok:
            all_ok = False
        print(f"  {lbl:<15} {full_pct:>7.1f}% {dev_pct:>7.1f}% {test_pct:>7.1f}% {'OK' if ok else 'WARN':>5}")

    if all_ok:
        print("  All label proportions within +/-5%. Split quality: GOOD.")
    else:
        print("  WARNING: Some proportions deviate >5%. Check split_summary.txt.")

    # ── Build split summary ───────────────────────────────────────────────────
    lines = [
        "=" * 70,
        "DEV / TEST SPLIT SUMMARY",
        "=" * 70,
        f"Random seed:        {SEED}",
        f"Split ratio:        70% dev / 30% test (stratified by stratum x label)",
        f"Total pairs:        {n_total}",
        f"Dev set:            {n_dev} pairs ({n_dev/n_total*100:.1f}%)",
        f"Test set:           {n_test} pairs ({n_test/n_total*100:.1f}%)",
        "",
        "── LABEL DISTRIBUTION ──────────────────────────────────────────────",
        f"  {'Label':<15} {'Full':>6} {'Dev':>6} {'Test':>6}",
        f"  {'-'*15} {'-'*6} {'-'*6} {'-'*6}",
    ]
    for lbl in LABELS:
        n_f = (df["gold_label"] == lbl).sum()
        n_d = (df_dev["gold_label"] == lbl).sum()
        n_t = (df_test["gold_label"] == lbl).sum()
        lines.append(f"  {lbl:<15} {n_f:>6} {n_d:>6} {n_t:>6}")

    lines += [
        "",
        "── PER-STRATUM DISTRIBUTION ────────────────────────────────────────",
        f"  {'Str':<5} {'Full':>5} {'Dev':>5} {'Test':>5}  "
        f"{'Dev match':>10} {'Dev non-m':>11} {'Dev unc':>9}",
        f"  {'-'*5} {'-'*5} {'-'*5} {'-'*5}  {'-'*10} {'-'*11} {'-'*9}",
    ]
    for s in STRATA:
        sf  = df[df["stratum"] == s]
        sd  = df_dev[df_dev["stratum"] == s]
        st  = df_test[df_test["stratum"] == s]
        dm  = (sd["gold_label"] == "match").sum()
        dnm = (sd["gold_label"] == "non-match").sum()
        du  = (sd["gold_label"] == "uncertain").sum()
        lines.append(
            f"  {s:<5} {len(sf):>5} {len(sd):>5} {len(st):>5}  "
            f"{dm:>10} {dnm:>11} {du:>9}"
        )

    summary_text = "\n".join(lines)
    print("\n" + summary_text)

    # ── Save outputs ──────────────────────────────────────────────────────────
    out_cols = ["pair_id", "keyword_a", "keyword_b", "freq_a", "freq_b",
                "stratum", "gold_label", "agreement_status"]
    dev_path  = BENCH / "dev_set.csv"
    test_path = BENCH / "test_set.csv"
    sum_path  = BENCH / "split_summary.txt"

    df_dev[out_cols].to_csv(dev_path, index=False, encoding="utf-8-sig")
    df_test[out_cols].to_csv(test_path, index=False, encoding="utf-8-sig")
    sum_path.write_text(summary_text, encoding="utf-8")

    print(f"\nSaved: {dev_path}")
    print(f"Saved: {test_path}")
    print(f"Saved: {sum_path}")
    print("\nBenchmark construction complete. Proceed to model evaluation.")


if __name__ == "__main__":
    main()
