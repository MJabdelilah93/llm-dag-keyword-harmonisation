"""
prepare_annotation_sheets.py  (Phase 1 — Task 1B)
---------------------------------------------------
Generates all annotation spreadsheets from candidate_pairs.csv.

Outputs (data/benchmark/):
    annotation_sheet_annotator1.csv
    annotation_sheet_annotator2.csv
    pilot_pairs.csv
    pilot_annotator1.csv
    pilot_annotator2.csv
"""

import io, sys, pathlib
import pandas as pd
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SEED = 42
ROOT  = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
BENCH = ROOT / "data" / "benchmark"

# ── Load candidate pairs ───────────────────────────────────────────────────────
df = pd.read_csv(BENCH / "candidate_pairs.csv", encoding="utf-8-sig")
print(f"Loaded {len(df)} candidate pairs")

STRATA = ["i","ii","iii","iv","v","vi","vii","viii","ix","x"]
TARGETS = {"i":40,"ii":45,"iii":55,"iv":40,"v":35,"vi":75,"vii":75,"viii":60,"ix":35,"x":40}

# ── Full annotation sheets ─────────────────────────────────────────────────────
base_cols = ["pair_id","keyword_a","keyword_b","freq_a","freq_b","stratum"]

for ann in [1, 2]:
    label_col = f"annotator{ann}_label"
    notes_col = f"annotator{ann}_notes"
    df_out = df[base_cols].copy()
    df_out[label_col] = ""
    df_out[notes_col] = ""
    out_path = BENCH / f"annotation_sheet_annotator{ann}.csv"
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved: {out_path}  ({len(df_out)} pairs)")

# ── Pilot pairs: proportional stratified sample ────────────────────────────────
PILOT_TOTAL = 50
stratum_counts = {s: TARGETS[s] for s in STRATA}
total_pairs = sum(stratum_counts.values())

pilot_rows = []
np.random.seed(SEED)

for s in STRATA:
    pool = df[df["stratum"] == s]
    # Proportional share: round, min 1
    share = max(1, round(TARGETS[s] / total_pairs * PILOT_TOTAL))
    n_take = min(share, len(pool))
    sampled = pool.sample(n=n_take, random_state=SEED)
    pilot_rows.append(sampled)
    print(f"  Stratum {s}: {n_take} pilot pairs (from {len(pool)} available)")

df_pilot = pd.concat(pilot_rows, ignore_index=True).sort_values("stratum")
print(f"\nPilot total: {len(df_pilot)} pairs")

pilot_path = BENCH / "pilot_pairs.csv"
df_pilot[base_cols + ["retrieval_method","similarity_score"]].to_csv(
    pilot_path, index=False, encoding="utf-8-sig"
)
print(f"Saved: {pilot_path}")

# ── Pilot annotator sheets ─────────────────────────────────────────────────────
for ann in [1, 2]:
    label_col = f"annotator{ann}_label"
    notes_col = f"annotator{ann}_notes"
    df_pout = df_pilot[base_cols].copy()
    df_pout[label_col] = ""
    df_pout[notes_col] = ""
    out_path = BENCH / f"pilot_annotator{ann}.csv"
    df_pout.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved: {out_path}")

print("\nAll annotation sheets prepared.")
