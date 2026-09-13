"""Final frozen retrieval audit: derive Scenario E (SEEDS30_DEPTH50) from
the existing, unmodified FULL 50-seed CE and biomedical retrieval
inventories, assign a stable retrieval_pair_id per row, and select the
frozen 30% in-pool stratified audit sample for Annotator 2 -- BEFORE any
human label exists, using only domain/route/difficulty-band as strata.

Never regenerates the candidate universe; only filters/relabels rows
already present in the audited FULL files (which are never modified).
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]

from .retrieval_audit_burden_analysis import (  # noqa: E402
    decile_position,
    difficulty_band,
    route_hit_and_survival,
)

SEEDS_PER_DECILE = 3  # Scenario E: 30 seeds/domain
TOP_K = 50  # Scenario E: full top-50/route depth
RANDOM_SEED = 42  # protocol_v1.yaml random_seed, reused for this deterministic selection
AUDIT_FRACTION = 0.30

CE_FULL = STRENGTHENING_ROOT / "restricted_local" / "ce" / "retrieval_audit_ce_seeds_candidates.csv"
BIO_FULL = STRENGTHENING_ROOT / "retrieval_audit" / "biomedical_diabetes_retrieval_audit_seeds_candidates.csv"

OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1" / "_intermediate"
SELECTION_MANIFEST_OUT = STRENGTHENING_ROOT / "provenance" / "retrieval_audit_scenario_e_selection_manifest.json"


def retrieval_pair_id(domain: str, seed_string: str, candidate_string: str) -> str:
    digest = hashlib.sha256(f"{domain}␟{seed_string}␟{candidate_string}".encode("utf-8")).hexdigest()
    return f"ret_{digest[:12]}"


def derive_scenario_e(csv_path: Path, domain_label: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype={"outside_pool_sample": bool})
    df["_decile"], df["_pos_in_decile"] = zip(*df["seed_id"].map(decile_position))
    kept = df[df["_pos_in_decile"] < SEEDS_PER_DECILE].copy()

    survival = kept.apply(lambda row: route_hit_and_survival(row["routes"], row["ranks"], TOP_K), axis=1)
    kept["_surviving_routes"] = [s[0] for s in survival]
    kept["_survives"] = [s[1] for s in survival]
    # outside-pool rows are unaffected by top-k truncation (never rank-ordered); always kept
    kept = kept[kept["_survives"] | kept["outside_pool_sample"]].copy()

    kept["retrieval_pair_id"] = [
        retrieval_pair_id(domain_label, s, c) for s, c in zip(kept["seed_string"], kept["candidate_string"])
    ]
    kept["route_signature"] = [
        ";".join(sorted(r)) if r else "" for r in kept["_surviving_routes"]
    ]
    kept["difficulty_band"] = kept["embedding_cosine"].map(difficulty_band)
    return kept


def select_audit_sample(scenario_e_df: pd.DataFrame, domain_label: str, seed: int) -> set[str]:
    """Deterministic stratified 30% sample of IN-POOL rows only, stratified
    by (route_signature, difficulty_band). Selection uses ONLY
    retrieval_pair_id/domain/route/difficulty-band -- never any label
    (none exist yet at this point in the pipeline anyway)."""
    in_pool = scenario_e_df[~scenario_e_df["outside_pool_sample"]].copy()
    rng = random.Random(f"{seed}-{domain_label}-audit30")
    selected: set[str] = set()
    strata = in_pool.groupby(["route_signature", "difficulty_band"])
    for _, group in strata:
        ids = sorted(group["retrieval_pair_id"].tolist())  # sort for determinism before sampling
        k = round(len(ids) * AUDIT_FRACTION)
        selected.update(rng.sample(ids, k))
    return selected


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ce_e = derive_scenario_e(CE_FULL, "circular_economy")
    bio_e = derive_scenario_e(BIO_FULL, "biomedical_diabetes_mellitus")

    ce_audit_ids = select_audit_sample(ce_e, "circular_economy", RANDOM_SEED)
    bio_audit_ids = select_audit_sample(bio_e, "biomedical_diabetes_mellitus", RANDOM_SEED)

    ce_e["audit_sample_selected"] = ce_e["retrieval_pair_id"].isin(ce_audit_ids)
    bio_e["audit_sample_selected"] = bio_e["retrieval_pair_id"].isin(bio_audit_ids)

    # duplicate-id sanity check
    assert ce_e["retrieval_pair_id"].duplicated().sum() == 0, "duplicate retrieval_pair_id within CE Scenario E"
    assert bio_e["retrieval_pair_id"].duplicated().sum() == 0, "duplicate retrieval_pair_id within biomedical Scenario E"

    ce_e.to_csv(OUT_DIR / "scenario_e_ce_master.csv", index=False, encoding="utf-8")
    bio_e.to_csv(OUT_DIR / "scenario_e_bio_master.csv", index=False, encoding="utf-8")

    def summarize(df: pd.DataFrame, domain_label: str) -> dict:
        in_pool = df[~df["outside_pool_sample"]]
        outside = df[df["outside_pool_sample"]]
        audit = in_pool[in_pool["audit_sample_selected"]]
        return {
            "domain": domain_label,
            "seed_count": df["seed_id"].nunique(),
            "total_rows": len(df),
            "in_pool_rows": len(in_pool),
            "outside_pool_rows": len(outside),
            "audit_sample_in_pool_rows": len(audit),
            "audit_fraction_actual": round(len(audit) / len(in_pool), 4) if len(in_pool) else None,
            "annotator_1_total_rows": len(df),
            "annotator_2_total_rows": len(outside) + len(audit),
        }

    ce_summary = summarize(ce_e, "circular_economy")
    bio_summary = summarize(bio_e, "biomedical_diabetes_mellitus")

    # Safe, hash-only selection manifest (retrieval_pair_id is a one-way
    # hash of domain+seed_string+candidate_string -- no raw restricted
    # strings are included here, consistent with how the CE 400-pair
    # manifest already publishes pair_ids safely).
    def id_list_hash(ids: list[str]) -> str:
        payload = "\n".join(sorted(ids)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "generated_at_utc": now,
        "scenario": "E_SEEDS30_DEPTH50",
        "seeds_per_decile": SEEDS_PER_DECILE,
        "top_k_per_route": TOP_K,
        "audit_fraction_target": AUDIT_FRACTION,
        "selection_random_seed": RANDOM_SEED,
        "selection_method": "stratified by (route_signature, difficulty_band) within each domain; retrieval_pair_id = sha256(domain|seed_string|candidate_string)[:12]; selection made before any human label exists and depends only on domain/route/difficulty-band, never on any label",
        "circular_economy": ce_summary,
        "biomedical_diabetes_mellitus": bio_summary,
        "ce_audit_sample_ids_sha256": id_list_hash(list(ce_audit_ids)),
        "bio_audit_sample_ids_sha256": id_list_hash(list(bio_audit_ids)),
        "ce_audit_sample_ids": sorted(ce_audit_ids),
        "bio_audit_sample_ids": sorted(bio_audit_ids),
    }
    SELECTION_MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(SELECTION_MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(json.dumps({"ce": ce_summary, "bio": bio_summary}, indent=2))
    print(f"Wrote {SELECTION_MANIFEST_OUT}")


if __name__ == "__main__":
    main()
