"""
export_vosviewer.py
===================
Exports co-word network data for all three downstream conditions
in VOSviewer-compatible format. No API calls.
"""

import io, sys, itertools, pathlib
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np

SEED        = 42
FREQ_THRESH = 5
TOP_N       = 100

BASE   = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
INTERN = BASE / "data" / "interim"
MAPS   = BASE / "results" / "downstream_harmonisation_maps"
OUTDIR = BASE / "results" / "figures" / "vosviewer_exports"
OUTDIR.mkdir(parents=True, exist_ok=True)

# ── Load corpus ───────────────────────────────────────────────────────────────
print("Loading corpus...")
df_c = pd.read_csv(INTERN / "scopus_ce_merged_deduped.csv",
                   usecols=["EID", "Author Keywords"], encoding="utf-8")
article_to_kws = {}
for _, row in df_c.iterrows():
    eid  = str(row["EID"])
    cell = row["Author Keywords"]
    if pd.isna(cell) or not str(cell).strip():
        article_to_kws[eid] = []
        continue
    article_to_kws[eid] = [k.strip() for k in str(cell).split(";") if k.strip()]
print(f"  Articles: {len(article_to_kws):,}")

# ── Conditions ────────────────────────────────────────────────────────────────
conditions = [
    ("raw",     "raw_map.csv",         "Raw (unharmonised)"),
    ("b3",      "b3_map.csv",          "B3 Jaro-Winkler"),
    ("llm_dag", "full_llm_dag_map.csv","Full LLM-DAG"),
]

all_summaries = []

for key, fname, label in conditions:
    print(f"\n{'='*60}")
    print(f"Processing: {label}")
    print(f"{'='*60}")

    # Load harmonisation map
    df_map   = pd.read_csv(MAPS / fname)
    kw_to_canon = dict(zip(df_map["keyword"], df_map["canonical_form"]))

    # Build canonical frequency and article mapping
    canon_to_eids = defaultdict(set)
    for eid, kws in article_to_kws.items():
        for k in kws:
            c = kw_to_canon.get(k, k)
            canon_to_eids[c].add(eid)

    canon_freq = {c: len(e) for c, e in canon_to_eids.items()}
    freq5      = {c for c, f in canon_freq.items() if f >= FREQ_THRESH}

    # Top-N keywords
    top_kws = sorted(freq5, key=lambda k: -canon_freq[k])[:TOP_N]
    top_set  = set(top_kws)
    print(f"  f >= {FREQ_THRESH}: {len(freq5):,} canonical keywords")
    print(f"  Top {TOP_N} selected: {len(top_kws)}")

    # Build co-occurrence matrix (articles × keywords)
    print("  Building co-occurrence counts...")
    edge_count = defaultdict(int)
    for eid, kws in article_to_kws.items():
        canons_in_top = {kw_to_canon.get(k, k) for k in kws} & top_set
        for a, b in itertools.combinations(sorted(canons_in_top), 2):
            edge_count[(a, b)] += 1

    n_edges = len(edge_count)
    print(f"  Co-occurrence edges (non-zero pairs): {n_edges:,}")

    # ── File 1: Co-occurrence matrix (.txt, tab-separated) ────────────────────
    matrix_path = OUTDIR / f"{key}_cooccurrence_matrix.txt"
    print(f"  Writing matrix -> {matrix_path.name}")
    with open(matrix_path, "w", encoding="utf-8") as f:
        # Header row
        f.write("\t" + "\t".join(top_kws) + "\n")
        for row_kw in top_kws:
            row_vals = []
            for col_kw in top_kws:
                if row_kw == col_kw:
                    row_vals.append("0")
                else:
                    pair = (min(row_kw, col_kw), max(row_kw, col_kw))
                    row_vals.append(str(edge_count.get(pair, 0)))
            f.write(row_kw + "\t" + "\t".join(row_vals) + "\n")

    # ── File 2: Keyword frequencies (.csv) ────────────────────────────────────
    freq_path = OUTDIR / f"{key}_keyword_frequencies.csv"
    df_freq = pd.DataFrame([
        {"keyword": k, "frequency": canon_freq[k], "condition": label}
        for k in top_kws
    ])
    df_freq.to_csv(freq_path, index=False, encoding="utf-8-sig")
    print(f"  Written freq  -> {freq_path.name}")

    # ── File 3: Edge list (.txt, tab-separated) ───────────────────────────────
    edge_path = OUTDIR / f"{key}_edge_list.txt"
    print(f"  Writing edges -> {edge_path.name}")
    with open(edge_path, "w", encoding="utf-8") as f:
        f.write("keyword_a\tkeyword_b\tweight\n")
        for (a, b), w in sorted(edge_count.items(), key=lambda x: -x[1]):
            f.write(f"{a}\t{b}\t{w}\n")

    # ── Summary stats ─────────────────────────────────────────────────────────
    top10 = top_kws[:10]
    sust_nodes = [k for k in top_kws if "sustain" in k.lower()]
    is_mega    = any(canon_freq.get(k, 0) > 5000 for k in sust_nodes)

    print(f"\n  Top 10 keywords by frequency:")
    for k in top10:
        print(f"    {canon_freq[k]:>7,}  {k}")

    print(f"\n  Sustainability nodes in top {TOP_N}: {len(sust_nodes)}")
    for k in sust_nodes[:8]:
        print(f"    {canon_freq[k]:>7,}  {k}")
    if is_mega:
        print(f"  *** MEGA-NODE detected: sustainability absorbed into single high-freq node ***")

    all_summaries.append({
        "condition":    label,
        "top_n":        len(top_kws),
        "edges":        n_edges,
        "sust_nodes":   len(sust_nodes),
        "is_mega_sust": is_mega,
        "top10":        top10,
    })

# ── VOSviewer instructions ────────────────────────────────────────────────────
instructions = f"""
=== HOW TO OPEN IN VOSVIEWER ===

Export folder: {OUTDIR}

1. Download VOSviewer from https://www.vosviewer.com/ (free, if not installed)

2. Open VOSviewer

3. Click "Create" -> "Create a map based on network data"

4. Select "Tab-delimited file with network data"

5. Browse to:
     {OUTDIR}
   Select the edge_list file for the condition you want:
     raw_edge_list.txt         <- Panel A: Raw (unharmonised)
     b3_edge_list.txt          <- Panel B: B3 Jaro-Winkler
     llm_dag_edge_list.txt     <- Panel C: Full LLM-DAG

6. In the next dialog:
     - "Minimum number of occurrences": leave at 0
       (frequency filtering already applied — all {TOP_N} keywords have f >= {FREQ_THRESH})
     - Click "Next" -> "Finish"

7. VOSviewer settings (use IDENTICAL values for all three maps):
     Layout tab:
       Attraction:       2
       Repulsion:       -1
       Max iterations:  1000
     Clustering tab:
       Resolution:       1.0
       Min cluster size: 5
     Visualization tab:
       Scale:            1.0
       Node size by:     "Total link strength" or "Occurrences"
       Labels: show all

8. To set node sizes by publication frequency:
     - Click the "Items" tab -> import {key}_keyword_frequencies.csv
       (or manually note frequencies from the {key}_keyword_frequencies.csv files)

9. Export the map from VOSviewer:
     File -> Screenshot (PNG) or
     File -> Save as image (SVG/PDF)

10. Repeat for all three edge list files using IDENTICAL settings.

For the manuscript figure:
  - Arrange three maps side by side (A, B, C)
  - Label: (A) Raw | (B) B3 Jaro-Winkler | (C) Full LLM-DAG
  - Add below each panel:
      (A) Vocab: 3,646  Q = 0.413
      (B) Vocab: 2,880  Q = 0.220
      (C) Vocab: 3,464  Q = 0.237
  - Highlight the Sustainability node in (B) with a red border annotation
  - Save at 300 DPI

=== CONDITION SUMMARY ===

{"Condition":<22} {"Keywords":>9} {"Edges":>9} {"Sust. nodes":>12} {"Mega-node?":>11}
{"-"*67}
"""

for s in all_summaries:
    instructions += (f"{s['condition']:<22} {s['top_n']:>9} {s['edges']:>9} "
                     f"{s['sust_nodes']:>12} {'YES ***' if s['is_mega_sust'] else 'no':>11}\n")

instructions += f"""
=== FILES WRITTEN ===

{str(OUTDIR)}
"""
for key, _, _ in conditions:
    instructions += f"  {key}_cooccurrence_matrix.txt\n"
    instructions += f"  {key}_keyword_frequencies.csv\n"
    instructions += f"  {key}_edge_list.txt\n"

inst_path = OUTDIR / "vosviewer_instructions.txt"
inst_path.write_text(instructions, encoding="utf-8")

print("\n" + "=" * 60)
print(instructions)
print(f"Instructions also saved to: {inst_path}")
print("\nAll VOSviewer export files written to:")
print(f"  {OUTDIR}")
