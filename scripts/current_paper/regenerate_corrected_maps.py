"""
regenerate_corrected_maps.py
==============================
PHASE 0B / TASK 5 — regenerate corrected harmonisation maps from ONLY the
frozen historical decision logs and the verified v1 execution logic
(union-find clustering + frequency-only canonicalisation, exactly as
scripts/rebuild_downstream.py implements them — verified byte-for-count
identical to that script's own vocab/edge/density output during the 2026-08
audit).

Reads the historical evidence tree read-only. Writes corrected map CSVs
(which contain real Scopus-derived keyword strings) to a local-only,
git-ignored restricted artefact area — never into the repair branch. Writes
a public, aggregate-only manifest (hashes, row counts, verification numbers,
no keyword strings) into the repair branch.

Does NOT overwrite outputs/harmonisation_maps/*.csv or
results/downstream_harmonisation_maps/*.csv anywhere. Those stale originals
are left untouched as historical evidence of the defect.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CODE_VERSION = "v1_corrected_maps_1.0.0"


def normalise(s):
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"\s+", " ", s.lower().strip())


def cpair(a, b):
    return (min(a, b), max(a, b))


def union_find_clusters(all_kws, match_edges, kw_to_eids):
    parent = {}
    def find(x):
        if x not in parent: parent[x] = x
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        px, py = find(x), find(y)
        if px != py: parent[px] = py
    for (a, b) in match_edges:
        if a in kw_to_eids and b in kw_to_eids: union(a, b)
    clusters = defaultdict(list)
    for k in all_kws: clusters[find(k)].append(k)
    return clusters


def make_canon_map(clusters, kw_freq):
    kw_to_canon = {}
    for root, members in clusters.items():
        canon = max(members, key=lambda k: kw_freq.get(k, 0))
        for m in members: kw_to_canon[m] = canon
    return kw_to_canon


def active_vocab_count(kw_to_canon, kw_to_eids, article_to_kws, freq_thresh=5):
    """Node count in the f>=5 co-word network, WITHOUT building the edges
    (edges/density/Q are Task 7-8's concern; this is the map/vocab layer)."""
    canon_to_eids = defaultdict(set)
    for eid, kws in article_to_kws.items():
        for k in kws:
            canon_to_eids[kw_to_canon.get(k, k)].add(eid)
    c_freq = {c: len(e) for c, e in canon_to_eids.items()}
    return sum(1 for f in c_freq.values() if f >= freq_thresh)


def family_clusters(substring, kw_to_canon, kw_to_eids, kw_freq, freq_thresh=2):
    matching = [k for k in kw_to_eids if substring.lower() in k.lower() and kw_freq.get(k, 0) >= freq_thresh]
    c2m = defaultdict(list)
    for k in matching: c2m[kw_to_canon.get(k, k)].append(k)
    return dict(c2m)


def true_cluster_size(clusters, kw_freq, target_label):
    for root, members in clusters.items():
        canon = max(members, key=lambda k: kw_freq.get(k, 0))
        if canon.strip().lower() == target_label.lower():
            return canon, len(members)
    return None, 0


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", default=os.environ.get("V1_EVIDENCE_ROOT"))
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()
    if not args.evidence_root:
        sys.exit("ERROR: --evidence-root not given and V1_EVIDENCE_ROOT not set.")

    evidence_root = Path(args.evidence_root)
    intern = evidence_root / "data" / "interim" / "scopus_ce_merged_deduped.csv"
    logs = evidence_root / "results" / "llm_logs"
    for p in [intern, logs / "downstream_raw_outputs.jsonl", logs / "downstream_fix_raw_outputs.jsonl",
              logs / "downstream_deterministic_completions.jsonl"]:
        if not p.exists():
            sys.exit(f"ERROR: expected evidence not found: {p}")

    input_hashes = {str(p.name): sha256_file(p) for p in [
        intern, logs / "downstream_raw_outputs.jsonl", logs / "downstream_fix_raw_outputs.jsonl",
        logs / "downstream_deterministic_completions.jsonl"]}

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.output_dir) if args.output_dir else repo_root / "restricted_local" / "corrected_maps"
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- load corpus (column order forced explicitly — read_csv(usecols=) keeps FILE order) ---
    df_c = pd.read_csv(intern, usecols=["EID", "Author Keywords"], encoding="utf-8")
    df_c = df_c[["EID", "Author Keywords"]]
    kw_to_eids = defaultdict(set)
    article_to_kws = {}
    for row in df_c.itertuples(index=False):
        eid, cell = str(row[0]), row[1]
        if pd.isna(cell) or not str(cell).strip():
            article_to_kws[eid] = []
            continue
        kws = [k.strip() for k in str(cell).split(";") if k.strip()]
        article_to_kws[eid] = kws
        for k in kws: kw_to_eids[k].add(eid)
    all_kws = list(kw_to_eids.keys())
    kw_freq = {k: len(v) for k, v in kw_to_eids.items()}
    assert len(all_kws) == 55425, f"SANITY FAIL: expected 55425 keywords, got {len(all_kws)}"

    # --- load pair decisions (identical merge/discard logic to rebuild_downstream.py) ---
    pair_decisions = {}
    with open(logs / "downstream_raw_outputs.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                if e.get("prompt_hash", "") in ("auto_accept_high_jw", "auto_reject_low_jw"): continue
                ka, kb = e.get("keyword_a", ""), e.get("keyword_b", "")
                if ka and kb: pair_decisions[cpair(ka, kb)] = e.get("decision", "uncertain")
            except Exception: pass
    with open(logs / "downstream_fix_raw_outputs.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                if e.get("error") == "api_failed": continue
                ka, kb = e.get("keyword_a", ""), e.get("keyword_b", "")
                if ka and kb: pair_decisions[cpair(ka, kb)] = e.get("decision", "uncertain")
            except Exception: pass
    with open(logs / "downstream_deterministic_completions.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                ka, kb = e.get("keyword_a", ""), e.get("keyword_b", "")
                if ka and kb:
                    p = cpair(ka, kb)
                    if p not in pair_decisions: pair_decisions[p] = e.get("decision", "match")
            except Exception: pass
    match_pairs = {k for k, d in pair_decisions.items() if d == "match"}

    # --- B3 (deterministic, no LLM dependency) ---
    import jellyfish
    import itertools
    B3_THRESH = 0.92
    norm_map = {k: normalise(k) for k in all_kws}
    n2first = {}
    for k in all_kws:
        n = norm_map[k]
        if n not in n2first: n2first[n] = k
    b3_match = set()
    norm_to_grp = defaultdict(list)
    for k in all_kws: norm_to_grp[norm_map[k]].append(k)
    for n, grp in norm_to_grp.items():
        if len(grp) < 2: continue
        for a, b in itertools.combinations(grp, 2): b3_match.add(cpair(a, b))
    freq2_kws = [k for k in all_kws if kw_freq.get(k, 0) >= 2]
    prefix_grp = defaultdict(list)
    for k in freq2_kws:
        n = norm_map[k]
        if len(n) >= 3: prefix_grp[n[:3]].append((k, n))
    for pfx, grp in prefix_grp.items():
        for i, (ka, na) in enumerate(grp):
            for kb, nb in grp[i+1:]:
                if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH: b3_match.add(cpair(ka, kb))
    PUNCT = re.compile(r"[-/(). ]")
    pmap = defaultdict(list)
    for k in all_kws:
        pn = PUNCT.sub("", norm_map[k])
        if len(pn) >= 3: pmap[pn].append(k)
    for pn, grp in pmap.items():
        if len(grp) < 2: continue
        for a, b in itertools.combinations(grp, 2):
            na, nb = norm_map[a], norm_map[b]
            if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH: b3_match.add(cpair(a, b))
    for na, ka in n2first.items():
        for suf in ["s", "es"]:
            nb = na + suf
            if nb in n2first and nb != na:
                if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH: b3_match.add(cpair(ka, n2first[nb]))
        if na.endswith("ies") and len(na) > 4:
            nb = na[:-3] + "y"
            if nb in n2first:
                if jellyfish.jaro_winkler_similarity(na, nb) >= B3_THRESH: b3_match.add(cpair(ka, n2first[nb]))

    # --- clusters + canon maps, all 3 conditions ---
    kw_to_canon_raw = {k: k for k in all_kws}
    clusters_b3 = union_find_clusters(all_kws, b3_match, kw_to_eids)
    kw_to_canon_b3 = make_canon_map(clusters_b3, kw_freq)
    clusters_llm = union_find_clusters(all_kws, match_pairs, kw_to_eids)
    kw_to_canon_llm = make_canon_map(clusters_llm, kw_freq)

    # --- write corrected map CSVs (restricted, local only) ---
    ts = datetime.now(timezone.utc).isoformat()
    outputs = {}
    for name, canon_map in [("raw_map_v1_verified.csv", kw_to_canon_raw),
                             ("b3_map_v1_verified.csv", kw_to_canon_b3),
                             ("full_llm_dag_map_v1_corrected.csv", kw_to_canon_llm)]:
        out_path = out_dir / name
        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["keyword", "canonical_form", "cluster_id", "freq"])
            for k in all_kws:
                c = canon_map.get(k, k)
                w.writerow([k, c, c, kw_freq.get(k, 0)])
        outputs[name] = {"path": str(out_path), "sha256": sha256_file(out_path), "rows": len(all_kws)}

    # --- verification numbers (public, aggregate only) ---
    vocab_raw = active_vocab_count(kw_to_canon_raw, kw_to_eids, article_to_kws)
    vocab_b3 = active_vocab_count(kw_to_canon_b3, kw_to_eids, article_to_kws)
    vocab_llm = active_vocab_count(kw_to_canon_llm, kw_to_eids, article_to_kws)

    sust_b3 = family_clusters("sustain", kw_to_canon_b3, kw_to_eids, kw_freq)
    sust_llm = family_clusters("sustain", kw_to_canon_llm, kw_to_eids, kw_freq)

    split_examples = 0
    for root_b3, members_b3 in clusters_b3.items():
        if len(members_b3) < 2: continue
        llm_roots = {kw_to_canon_llm.get(m, m) for m in members_b3 if m in kw_to_eids}
        if len(llm_roots) > 1 and all(kw_freq.get(m, 0) >= 2 for m in members_b3):
            split_examples += 1

    ce_canon_llm, ce_size_llm = true_cluster_size(clusters_llm, kw_freq, "Circular economy")
    ce_canon_b3, ce_size_b3 = true_cluster_size(clusters_b3, kw_freq, "Circular economy")

    verification = {
        "code_version": CODE_VERSION,
        "generated_utc": ts,
        "input_hashes": input_hashes,
        "output_files": outputs,
        "keyword_universe": len(all_kws),
        "active_vocab_freq_ge_5": {"raw": vocab_raw, "b3": vocab_b3, "llm_dag": vocab_llm},
        "expected_active_vocab": {"raw": 3646, "b3": 2880, "llm_dag": 3464},
        "circular_economy_true_cluster_size": {"b3": ce_size_b3, "llm_dag": ce_size_llm},
        "expected_circular_economy": {"b3": 214, "llm_dag": 57},
        "sustainability_family_groups": {"b3": len(sust_b3), "llm_dag": len(sust_llm)},
        "expected_sustainability_family": {"b3": 56, "llm_dag": 216},
        "b3_clusters_fragmented_by_llm_dag": split_examples,
        "expected_fragmented": 194,
        "total_clusters": {"b3": len(clusters_b3), "llm_dag": len(clusters_llm)},
    }
    verification["all_checks_pass"] = (
        vocab_raw == 3646 and vocab_b3 == 2880 and vocab_llm == 3464
        and ce_size_b3 == 214 and ce_size_llm == 57
        and len(sust_b3) == 56 and len(sust_llm) == 216
        and split_examples == 194
    )

    manifest_path = repo_root / "docs" / "provenance" / "corrected_maps_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(verification, f, indent=2)

    print(json.dumps(verification, indent=2))
    print(f"\nManifest written to: {manifest_path}")
    print(f"Corrected maps (restricted, local only) written to: {out_dir}")


if __name__ == "__main__":
    main()
