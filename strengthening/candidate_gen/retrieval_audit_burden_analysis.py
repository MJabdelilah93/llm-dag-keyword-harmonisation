"""Step 9: retrieval-audit human-burden analysis.

Re-analyses the ALREADY-GENERATED, unmodified retrieval-audit CSV(s) under
four scenarios (FULL / REDUCED-1/2/3) by filtering on seed subset and
per-route rank truncation -- it never regenerates, edits, or deletes the
full 50-seed audit file(s).

Seed subsetting is a genuine nested subset of the full design: seeds were
originally drawn 5 per frequency-rank decile (ce_seed_001-005 = decile 0,
..., 046-050 = decile 9); REDUCED designs keep the first 3 (30 seeds) or
first 2 (20 seeds) of each decile's 5, preserving proportional decile
coverage rather than truncating naively from one end.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]

SCENARIOS = {
    "FULL": {"seeds_per_decile": 5, "top_k": 50},
    "REDUCED-1": {"seeds_per_decile": 3, "top_k": 30},
    "REDUCED-2": {"seeds_per_decile": 2, "top_k": 30},
    "REDUCED-3": {"seeds_per_decile": 2, "top_k": 20},
    # Part D: seed-only reductions at FULL (top-50) or near-full (top-40) depth.
    "E_SEEDS30_DEPTH50": {"seeds_per_decile": 3, "top_k": 50},
    "F_SEEDS20_DEPTH50": {"seeds_per_decile": 2, "top_k": 50},
    "G_SEEDS30_DEPTH40": {"seeds_per_decile": 3, "top_k": 40},
    "H_SEEDS20_DEPTH40": {"seeds_per_decile": 2, "top_k": 40},
}
ANNOTATION_TIME_SECONDS = [15, 30, 45]

DIFFICULTY_BANDS = [
    ("high_similarity_geq_0.85", 0.85, 1.01),
    ("vi_near_synonym_0.75_0.85", 0.75, 0.85),
    ("vii_broader_narrower_0.60_0.75", 0.60, 0.75),
    ("x_weak_semantic_0.50_0.60", 0.50, 0.60),
    ("below_0.50_or_no_embedding_score", -1.0, 0.50),
]


def difficulty_band(embedding_cosine) -> str:
    try:
        v = float(embedding_cosine)
    except (TypeError, ValueError):
        return "below_0.50_or_no_embedding_score"
    for name, lo, hi in DIFFICULTY_BANDS:
        if lo <= v < hi:
            return name
    return "below_0.50_or_no_embedding_score"


def decile_position(seed_id: str) -> tuple[int, int]:
    n = int(seed_id.split("_")[-1])  # e.g. "ce_seed_007" -> 7
    idx = n - 1
    return idx // 5, idx % 5


def route_hit_and_survival(routes: str, ranks_json: str, top_k: int) -> tuple[set[str], bool]:
    """Returns (surviving_routes, row_survives) for a given top-k truncation.
    A route with no rank entry (an unranked heuristic route, e.g. acronym or
    lexical-exact) always counts; a ranked route counts only if rank<=top_k."""
    routes_list = [r for r in routes.split(";") if r] if isinstance(routes, str) else []
    ranks = json.loads(ranks_json) if isinstance(ranks_json, str) and ranks_json else {}
    surviving = set()
    for r in routes_list:
        if r not in ranks:
            surviving.add(r)  # unranked route, unaffected by top-k
        elif ranks[r] <= top_k:
            surviving.add(r)
    return surviving, len(surviving) > 0


def analyse_domain(csv_path: Path, domain_label: str) -> dict:
    df = pd.read_csv(csv_path, dtype={"outside_pool_sample": bool})
    df["_decile"], df["_pos_in_decile"] = zip(*df["seed_id"].map(decile_position))

    results = {}
    for name, cfg in SCENARIOS.items():
        keep_seed_mask = df["_pos_in_decile"] < cfg["seeds_per_decile"]
        scenario_df = df[keep_seed_mask].copy()
        kept_seeds = sorted(scenario_df["seed_id"].unique())

        in_pool = scenario_df[~scenario_df["outside_pool_sample"]].copy()
        outside_pool = scenario_df[scenario_df["outside_pool_sample"]]

        survival = in_pool.apply(
            lambda row: route_hit_and_survival(row["routes"], row["ranks"], cfg["top_k"]), axis=1
        )
        in_pool["_surviving_routes"] = [s[0] for s in survival]
        in_pool["_survives"] = [s[1] for s in survival]
        survivors = in_pool[in_pool["_survives"]]

        raw_hits = int(sum(len(r) for r in in_pool["_surviving_routes"]))  # only counts surviving route-hits
        raw_hits += int(len(outside_pool))  # outside-pool rows are single-route-agnostic "raw" draws too

        dedup_rows = len(survivors)
        outside_rows = len(outside_pool)
        total_rows = dedup_rows + outside_rows

        per_seed_counts = survivors.groupby("seed_id").size()
        # include seeds with zero surviving in-pool candidates for a complete distribution
        per_seed_counts = per_seed_counts.reindex(kept_seeds, fill_value=0)

        # route exclusivity / overlap, computed over surviving in-pool rows only
        route_names = sorted({r for routes in survivors["_surviving_routes"] for r in routes})
        exclusive_counts = {r: 0 for r in route_names}
        multi_route_count = 0
        for routes in survivors["_surviving_routes"]:
            if len(routes) == 1:
                exclusive_counts[next(iter(routes))] += 1
            elif len(routes) > 1:
                multi_route_count += 1
        route_exclusive_share = {
            r: round(c / dedup_rows, 4) if dedup_rows else None for r, c in exclusive_counts.items()
        }
        overlap_share = round(multi_route_count / dedup_rows, 4) if dedup_rows else None

        results[name] = {
            "domain": domain_label,
            "seed_count": len(kept_seeds),
            "raw_retrieved_rows": raw_hits,
            "deduplicated_annotation_rows_in_pool": dedup_rows,
            "outside_pool_rows": outside_rows,
            "total_rows_requiring_judgement": total_rows,
            "two_annotator_judgements": total_rows * 2,
            "candidate_rows_per_seed": {
                "median": float(per_seed_counts.median()) if len(per_seed_counts) else 0.0,
                "iqr": [float(per_seed_counts.quantile(0.25)), float(per_seed_counts.quantile(0.75))] if len(per_seed_counts) else [0.0, 0.0],
                "min": float(per_seed_counts.min()) if len(per_seed_counts) else 0.0,
                "max": float(per_seed_counts.max()) if len(per_seed_counts) else 0.0,
            },
            "route_exclusive_share": route_exclusive_share,
            "route_overlap_share_multi_route_rows": overlap_share,
            "annotation_time_estimates_two_annotators": {
                f"{s}s_per_judgement": round(total_rows * 2 * s / 3600, 2) for s in ANNOTATION_TIME_SECONDS
            },
        }

    # candidate retention relative to FULL, computed by pair identity (seed_id, candidate_string),
    # both overall and broken down by embedding-cosine difficulty band.
    df["_band"] = df["embedding_cosine"].map(difficulty_band)
    full_pairs = None
    full_pairs_by_band: dict[str, set] = {}
    for name in SCENARIOS:
        keep_seed_mask = df["_pos_in_decile"] < SCENARIOS[name]["seeds_per_decile"]
        scenario_df = df[keep_seed_mask & ~df["outside_pool_sample"]].copy()
        survival = scenario_df.apply(lambda row: route_hit_and_survival(row["routes"], row["ranks"], SCENARIOS[name]["top_k"])[1], axis=1)
        surv_df = scenario_df.loc[survival]
        pairs = set(zip(surv_df["seed_id"], surv_df["candidate_string"]))

        pairs_by_band = {}
        for band, _, _ in DIFFICULTY_BANDS:
            band_pairs = set(zip(surv_df.loc[surv_df["_band"] == band, "seed_id"], surv_df.loc[surv_df["_band"] == band, "candidate_string"]))
            pairs_by_band[band] = band_pairs

        if name == "FULL":
            full_pairs = pairs
            full_pairs_by_band = pairs_by_band

        retained_pct = round(100 * len(pairs & full_pairs) / len(full_pairs), 2) if full_pairs else None
        results[name]["candidate_retention_pct_of_full_design"] = retained_pct
        results[name]["candidate_retention_pct_by_difficulty_band"] = {
            band: (round(100 * len(pairs_by_band[band] & full_pairs_by_band[band]) / len(full_pairs_by_band[band]), 2) if full_pairs_by_band.get(band) else None)
            for band, _, _ in DIFFICULTY_BANDS
        }

    return results


def combine(ce: dict, bio: dict | None) -> dict:
    combined = {}
    for name in SCENARIOS:
        c = ce[name]
        if bio is not None:
            b = bio[name]
            combined[name] = {
                "seed_count": c["seed_count"] + b["seed_count"],
                "total_rows_requiring_judgement": c["total_rows_requiring_judgement"] + b["total_rows_requiring_judgement"],
                "two_annotator_judgements": c["two_annotator_judgements"] + b["two_annotator_judgements"],
                "annotation_time_estimates_two_annotators": {
                    f"{s}s_per_judgement": round(
                        (c["total_rows_requiring_judgement"] + b["total_rows_requiring_judgement"]) * 2 * s / 3600, 2
                    )
                    for s in ANNOTATION_TIME_SECONDS
                },
            }
        else:
            combined[name] = {
                "seed_count": c["seed_count"],
                "total_rows_requiring_judgement": c["total_rows_requiring_judgement"],
                "two_annotator_judgements": c["two_annotator_judgements"],
                "annotation_time_estimates_two_annotators": c["annotation_time_estimates_two_annotators"],
                "note": "CE only -- biomedical retrieval audit not yet generated",
            }
    return combined


def main():
    ce_csv = STRENGTHENING_ROOT / "restricted_local" / "ce" / "retrieval_audit_ce_seeds_candidates.csv"
    ce_results = analyse_domain(ce_csv, "circular_economy")

    bio_csv = STRENGTHENING_ROOT / "retrieval_audit" / "biomedical_diabetes_retrieval_audit_seeds_candidates.csv"
    bio_results = None
    if bio_csv.exists():
        bio_results = analyse_domain(bio_csv, "biomedical_diabetes_mellitus")

    combined_results = combine(ce_results, bio_results)

    report = {
        "scenarios_definition": SCENARIOS,
        "circular_economy": ce_results,
        "biomedical": bio_results if bio_results is not None else "NOT YET GENERATED",
        "combined": combined_results,
    }

    out_json = STRENGTHENING_ROOT / "reports" / "retrieval_audit_burden_analysis.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Wrote {out_json}")
    return report


if __name__ == "__main__":
    main()
