"""Builds the SAFE, tracked strengthening/provenance/final_annotation_
package_manifest.json. Contains no restricted strings -- only hashes,
counts, and already-release-safe pair IDs (as established for the CE 400
and biomedical 500 benchmarks' own public manifests)."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1"
CSV_DIR = PKG_DIR / "csv_backups"
INTER_DIR = PKG_DIR / "_intermediate"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=STRENGTHENING_ROOT.parent, capture_output=True, text=True).stdout.strip()


def id_list_hash(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


def main():
    ce_bench = STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv"
    bio_bench = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
    selection_manifest = json.load(open(STRENGTHENING_ROOT / "provenance" / "retrieval_audit_scenario_e_selection_manifest.json"))

    p1 = pd.read_csv(INTER_DIR / "primary_annotator_1.csv", dtype=str)
    p2 = pd.read_csv(INTER_DIR / "primary_annotator_2.csv", dtype=str)
    r1 = pd.read_csv(INTER_DIR / "retrieval_annotator_1.csv", dtype=str)
    r2 = pd.read_csv(INTER_DIR / "retrieval_annotator_2.csv", dtype=str)

    seed_ids_ce = pd.read_csv(INTER_DIR / "scenario_e_ce_master.csv")["seed_id"].unique().tolist()
    seed_ids_bio = pd.read_csv(INTER_DIR / "scenario_e_bio_master.csv")["seed_id"].unique().tolist()

    package_files = {}
    for f in sorted(PKG_DIR.glob("*.xlsx")):
        package_files[f.name] = sha256_of(f)
    for f in sorted(CSV_DIR.glob("*.csv")):
        package_files[f"csv_backups/{f.name}"] = sha256_of(f)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "current_commit": git_head(),
        "primary_ce_source_file": {"path": "strengthening/restricted_local/ce/ce_400_annotation_candidates_unlabelled.csv", "sha256": sha256_of(ce_bench)},
        "primary_biomedical_source_file": {"path": "strengthening/benchmark/biomedical_500_annotation_candidates_unlabelled.csv", "sha256": sha256_of(bio_bench)},
        "retrieval_configuration": {
            "scenario": "E_SEEDS30_DEPTH50",
            "seeds_per_domain": 30,
            "top_k_per_route": 50,
            "domains": ["circular_economy", "biomedical_diabetes_mellitus"],
        },
        "seed_ids": {"circular_economy": sorted(seed_ids_ce), "biomedical_diabetes_mellitus": sorted(seed_ids_bio)},
        "counts": {
            "primary_ce_pairs": int((p1["domain"] == "circular_economy").sum()),
            "primary_biomedical_pairs": int((p1["domain"] == "biomedical_diabetes_mellitus").sum()),
            "primary_total_pairs": len(p1),
            "annotator_1_retrieval_rows": len(r1),
            "annotator_2_retrieval_rows": len(r2),
            "outside_pool_rows": selection_manifest["circular_economy"]["outside_pool_rows"] + selection_manifest["biomedical_diabetes_mellitus"]["outside_pool_rows"],
            "audit_sample_30pct_rows": selection_manifest["circular_economy"]["audit_sample_in_pool_rows"] + selection_manifest["biomedical_diabetes_mellitus"]["audit_sample_in_pool_rows"],
        },
        "selection_random_seed": selection_manifest["selection_random_seed"],
        "annotator_row_order_seeds": {"annotator_1": 42, "annotator_2": 43},
        "package_file_hashes": package_files,
        "context_construction_rule": "up to 3 representative article titles per keyword/string, deterministically selected (sorted title order), CE from the local Scopus corpus (read-only), diabetes from the licence-verified PMC source records; no abstracts; blank if unavailable, never fabricated",
        "annotation_labels": ["match", "non-match", "uncertain"],
        "escalation_rule": "per domain: after the initial 30% blinded in-pool audit is adjudicated, if the adjudicated positive-miss rate (Ann1=non-match/uncertain, Ann2=match, Adjudicator=match) exceeds 2%, expand Annotator-2 coverage to 40% for that domain only (pre-selected deterministically, excluding already-double-coded rows); if still >2% after 40%, expand to full double annotation for that domain. Cohen's kappa and raw agreement are reported descriptively but are not themselves the escalation trigger.",
        "primary_pair_ids_sha256": id_list_hash(list(p1["pair_id"])),
        "retrieval_pair_ids_annotator_1_sha256": id_list_hash(list(r1["retrieval_pair_id"])),
        "retrieval_pair_ids_annotator_2_sha256": id_list_hash(list(r2["retrieval_pair_id"])),
        "software_versions": {
            "python": sys.version,
            "os": platform.platform(),
            "pandas": pd.__version__,
        },
    }

    out = STRENGTHENING_ROOT / "provenance" / "final_annotation_package_manifest.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    print(f"Wrote {out}")
    print(json.dumps(manifest["counts"], indent=2))


if __name__ == "__main__":
    main()
