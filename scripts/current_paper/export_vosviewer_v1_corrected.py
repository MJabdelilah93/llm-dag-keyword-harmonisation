"""
export_vosviewer_v1_corrected.py
===================================
PHASE 0B / TASK 11 — regenerate the DATA INPUTS for Figure 2 and all
VOSviewer exports from the CORRECTED mapping (restricted_local/corrected_maps/),
not the stale results/downstream_harmonisation_maps/ that the original
scripts/export_vosviewer.py reads from.

Same algorithm as scripts/export_vosviewer.py (TOP_N=100 highest-frequency
canonical keywords per condition, FREQ_THRESH=5, co-occurrence matrix +
edge list + keyword frequencies) — only the map source and output location
differ. The original script is left completely untouched.

Outputs contain real Scopus-derived keyword strings and are written to
restricted_local/ only, never committed. Row counts and hashes are recorded
in a public manifest.

This script does NOT open VOSviewer or produce a screenshot — that step is
an unavoidable manual GUI action. See the "MANUAL STEP REQUIRED" section
printed at the end and docs/provenance/figure2_vosviewer_rebuild.md for the
exact instructions.
"""
import argparse
import hashlib
import itertools
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

FREQ_THRESH = 5
TOP_N = 100


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"))
    args = ap.parse_args()
    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")

    evidence_root = Path(args.evidence_root)
    intern = evidence_root / "data" / "interim" / "scopus_ce_merged_deduped.csv"
    repo_root = Path(__file__).resolve().parents[2]
    maps_dir = repo_root / "restricted_local" / "corrected_maps"
    out_dir = repo_root / "restricted_local" / "vosviewer_exports_v1_corrected"
    out_dir.mkdir(parents=True, exist_ok=True)

    conditions = [
        ("raw", "raw_map_v1_verified.csv", "Raw (unharmonised)"),
        ("b3", "b3_map_v1_verified.csv", "B3 Jaro-Winkler"),
        ("llm_dag", "full_llm_dag_map_v1_corrected.csv", "Full LLM-DAG (corrected)"),
    ]
    for _, fname, _ in conditions:
        if not (maps_dir / fname).exists():
            sys.exit(f"ERROR: {maps_dir / fname} not found — run regenerate_corrected_maps.py first")

    df_c = pd.read_csv(intern, usecols=["EID", "Author Keywords"], encoding="utf-8")
    df_c = df_c[["EID", "Author Keywords"]]
    article_to_kws = {}
    for row in df_c.itertuples(index=False):
        eid, cell = str(row[0]), row[1]
        article_to_kws[eid] = [] if pd.isna(cell) or not str(cell).strip() else \
            [k.strip() for k in str(cell).split(";") if k.strip()]

    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(),
                "freq_thresh": FREQ_THRESH, "top_n": TOP_N, "conditions": {}}

    for key, fname, label in conditions:
        df_map = pd.read_csv(maps_dir / fname, encoding="utf-8-sig")
        kw_to_canon = dict(zip(df_map["keyword"], df_map["canonical_form"]))

        canon_to_eids = defaultdict(set)
        for eid, kws in article_to_kws.items():
            for k in kws:
                canon_to_eids[kw_to_canon.get(k, k)].add(eid)
        canon_freq = {c: len(e) for c, e in canon_to_eids.items()}
        freq5 = {c for c, f in canon_freq.items() if f >= FREQ_THRESH}
        top_kws = sorted(freq5, key=lambda k: -canon_freq[k])[:TOP_N]
        top_set = set(top_kws)

        edge_count = defaultdict(int)
        for eid, kws in article_to_kws.items():
            canons_in_top = {kw_to_canon.get(k, k) for k in kws} & top_set
            for a, b in itertools.combinations(sorted(canons_in_top), 2):
                edge_count[(a, b)] += 1

        matrix_path = out_dir / f"{key}_cooccurrence_matrix_v1_corrected.txt"
        with open(matrix_path, "w", encoding="utf-8") as f:
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

        freq_path = out_dir / f"{key}_keyword_frequencies_v1_corrected.csv"
        pd.DataFrame([{"keyword": k, "frequency": canon_freq[k], "condition": label}
                      for k in top_kws]).to_csv(freq_path, index=False, encoding="utf-8-sig")

        edge_path = out_dir / f"{key}_edge_list_v1_corrected.txt"
        with open(edge_path, "w", encoding="utf-8") as f:
            f.write("keyword_a\tkeyword_b\tweight\n")
            for (a, b), w in sorted(edge_count.items(), key=lambda x: -x[1]):
                f.write(f"{a}\t{b}\t{w}\n")

        # headerless variant for direct VOSviewer import, matching the existing convention
        edge_path_vos = out_dir / f"{key}_edge_list_v1_corrected_vos.txt"
        with open(edge_path_vos, "w", encoding="utf-8") as f:
            for (a, b), w in sorted(edge_count.items(), key=lambda x: -x[1]):
                f.write(f"{a}\t{b}\t{w}\n")

        manifest["conditions"][key] = {
            "label": label, "source_map": fname, "source_map_sha256": sha256_file(maps_dir / fname),
            "n_top_keywords": len(top_kws), "n_edges": len(edge_count),
            "cooccurrence_matrix_sha256": sha256_file(matrix_path),
            "keyword_frequencies_sha256": sha256_file(freq_path),
            "edge_list_sha256": sha256_file(edge_path),
            "edge_list_vos_sha256": sha256_file(edge_path_vos),
        }
        print(f"{label}: top_n={len(top_kws)} edges={len(edge_count)}")

    manifest_path = repo_root / "docs" / "provenance" / "figure2_vosviewer_rebuild_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest (public, aggregate only): {manifest_path}")
    print(f"Exports (restricted, local only): {out_dir}")
    print("\n*** MANUAL STEP REQUIRED — see docs/provenance/figure2_vosviewer_rebuild.md ***")


if __name__ == "__main__":
    main()
