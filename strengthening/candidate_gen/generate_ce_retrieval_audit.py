"""Stage 6 (circular-economy half): candidate-retrieval audit tooling.

Distinct from the 400-pair benchmark: this selects 50 seed concepts
spanning frequency/difficulty (not just the most-frequent terms) and, for
each, builds a high-recall candidate union across the lexical / Jaro-
Winkler / TF-IDF / embedding / acronym routes, plus a small deterministic
outside-pool comparison sample for later hidden-miss checking.

No labels are assigned here -- human_label/context_used/manual_missing_
candidate/notes are always left blank. Pair/candidate "completeness"
metrics are NOT computed here (Stage 9's retrieval metrics module handles
that, and explicitly returns None until gold retrieval annotations exist).
"""
from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .features import EmbeddingIndex, TfidfIndex, jaro_winkler_score
from .generate_ce_candidates import build_universe
from .legacy_access import load_keyword_frequencies, sha256_of
from .normalise import normalise

HERE = Path(__file__).resolve()
STRENGTHENING_ROOT = HERE.parents[1]
CONFIG_PATH = STRENGTHENING_ROOT / "config" / "protocol_v1.yaml"

RESTRICTED_OUT = STRENGTHENING_ROOT / "restricted_local" / "ce" / "retrieval_audit_ce_seeds_candidates.csv"
MANIFEST_OUT = STRENGTHENING_ROOT / "retrieval_audit" / "ce_retrieval_audit_manifest.json"

N_SEEDS = 50
N_DECILES = 10
SEEDS_PER_DECILE = N_SEEDS // N_DECILES
TOP_K_PER_ROUTE = 50
JW_FLOOR = 0.70
OUTSIDE_POOL_PER_SEED = 5


def select_seeds(freq_df: pd.DataFrame, seed: int) -> list[str]:
    """Deterministic stratified selection across frequency-rank deciles."""
    df = freq_df.dropna(subset=["keyword"]).copy()
    df["keyword"] = df["keyword"].astype(str)
    df = df.drop_duplicates(subset=["keyword"]).sort_values(by=["frequency", "keyword"], ascending=[True, True])
    df = df.reset_index(drop=True)
    n = len(df)
    bucket_size = n // N_DECILES
    rng = random.Random(seed)
    seeds: list[str] = []
    for decile in range(N_DECILES):
        start = decile * bucket_size
        end = (decile + 1) * bucket_size if decile < N_DECILES - 1 else n
        bucket = df.iloc[start:end]["keyword"].tolist()
        take = min(SEEDS_PER_DECILE, len(bucket))
        seeds.extend(rng.sample(bucket, take))
    return seeds[:N_SEEDS]


def acronym_route_candidates(seed_str: str, universe: list[str]) -> list[str]:
    from .features import _initials, _is_acronym_like
    import re

    out = []
    if _is_acronym_like(seed_str):
        letters = re.sub(r"[^A-Za-z]", "", seed_str).upper()
        for u in universe:
            if _initials(u) == letters and normalise(u) != normalise(seed_str):
                out.append(u)
    else:
        seed_initials = _initials(seed_str)
        if len(seed_initials) >= 2:
            for u in universe:
                if _is_acronym_like(u) and re.sub(r"[^A-Za-z]", "", u).upper() == seed_initials:
                    out.append(u)
    return out


def build_audit(seed: int = 42) -> dict:
    freq_df, freq_path = load_keyword_frequencies()
    freq_hash = sha256_of(freq_path)
    freq_lookup = dict(zip(freq_df["keyword"].astype(str), freq_df["frequency"]))

    seeds = select_seeds(freq_df, seed)
    universe = build_universe(freq_df, seed)
    idx_of = {s: i for i, s in enumerate(universe)}

    tfidf_index = TfidfIndex(universe)
    embedding_index = EmbeddingIndex(universe)

    rows = []
    rng = random.Random(seed)

    for seed_id, seed_str in enumerate(seeds, start=1):
        candidates: dict[str, dict] = defaultdict(lambda: {"routes": set(), "ranks": {}, "jw": None, "tfidf": None, "emb": None})

        # Jaro-Winkler route (full scan over the tractable universe).
        jw_scores = [(u, jaro_winkler_score(seed_str, u)) for u in universe if u != seed_str]
        jw_scores = [t for t in jw_scores if t[1] >= JW_FLOOR]
        jw_scores.sort(key=lambda t: -t[1])
        for rank, (u, score) in enumerate(jw_scores[:TOP_K_PER_ROUTE], start=1):
            c = candidates[u]
            c["routes"].add("jaro_winkler")
            c["ranks"]["jaro_winkler"] = rank
            c["jw"] = score

        # TF-IDF route: vectorise the seed against the fitted vocabulary.
        seed_vec = tfidf_index.vectorizer.transform([normalise(seed_str)])
        sims = np.asarray((tfidf_index.matrix @ seed_vec.T).todense()).ravel()
        order = np.argsort(-sims)
        rank = 0
        for i in order:
            if universe[i] == seed_str or sims[i] <= 0:
                continue
            rank += 1
            if rank > TOP_K_PER_ROUTE:
                break
            c = candidates[universe[i]]
            c["routes"].add("tfidf")
            c["ranks"]["tfidf"] = rank
            c["tfidf"] = float(sims[i])

        # Embedding route: encode the seed and compare to the universe matrix.
        seed_emb = embedding_index.model.encode([seed_str], normalize_embeddings=True)[0]
        emb_sims = embedding_index.embeddings @ seed_emb
        order = np.argsort(-emb_sims)
        rank = 0
        for i in order:
            if universe[i] == seed_str:
                continue
            rank += 1
            if rank > TOP_K_PER_ROUTE:
                break
            c = candidates[universe[i]]
            c["routes"].add("embedding")
            c["ranks"]["embedding"] = rank
            c["emb"] = float(emb_sims[i])

        # Acronym heuristic route (not rank-ordered, small and exact).
        for u in acronym_route_candidates(seed_str, universe):
            c = candidates[u]
            c["routes"].add("acronym_heuristic")

        # Lexical/normalised-exact route.
        for u in universe:
            if u != seed_str and normalise(u) == normalise(seed_str):
                c = candidates[u]
                c["routes"].add("lexical_normalised_exact")

        for cand_str, info in candidates.items():
            rows.append(
                {
                    "seed_id": f"ce_seed_{seed_id:03d}",
                    "seed_string": seed_str,
                    "candidate_string": cand_str,
                    "domain": "circular_economy",
                    "routes": ";".join(sorted(info["routes"])),
                    "ranks": json.dumps(info["ranks"], sort_keys=True),
                    "jaro_winkler_score": round(info["jw"], 6) if info["jw"] is not None else "",
                    "tfidf_cosine": round(info["tfidf"], 6) if info["tfidf"] is not None else "",
                    "embedding_cosine": round(info["emb"], 6) if info["emb"] is not None else "",
                    "outside_pool_sample": False,
                    "human_label": "",
                    "context_used": "",
                    "manual_missing_candidate": "",
                    "notes": "",
                }
            )

        # Deterministic small outside-pool comparison sample: universe
        # members NOT retrieved by any route for this seed.
        retrieved = set(candidates.keys()) | {seed_str}
        pool_complement = [u for u in universe if u not in retrieved]
        outside_sample = rng.sample(pool_complement, min(OUTSIDE_POOL_PER_SEED, len(pool_complement)))
        for cand_str in outside_sample:
            rows.append(
                {
                    "seed_id": f"ce_seed_{seed_id:03d}",
                    "seed_string": seed_str,
                    "candidate_string": cand_str,
                    "domain": "circular_economy",
                    "routes": "",
                    "ranks": "{}",
                    "jaro_winkler_score": round(jaro_winkler_score(seed_str, cand_str), 6),
                    "tfidf_cosine": "",
                    "embedding_cosine": "",
                    "outside_pool_sample": True,
                    "human_label": "",
                    "context_used": "",
                    "manual_missing_candidate": "",
                    "notes": "",
                }
            )

    return {
        "rows": rows,
        "seeds": seeds,
        "universe_size": len(universe),
        "freq_path": str(freq_path),
        "freq_hash": freq_hash,
    }


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    seed = config["random_seed"]

    result = build_audit(seed=seed)
    df = pd.DataFrame(result["rows"])

    RESTRICTED_OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RESTRICTED_OUT, index=False, encoding="utf-8")

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "generated_at_utc": now,
        "random_seed": seed,
        "n_seeds": len(result["seeds"]),
        "universe_size": result["universe_size"],
        "legacy_frequency_source": {"path": result["freq_path"], "sha256": result["freq_hash"]},
        "total_rows": len(df),
        "in_pool_rows": int((~df["outside_pool_sample"]).sum()),
        "outside_pool_rows": int(df["outside_pool_sample"].sum()),
        "rows_per_seed": df.groupby("seed_id").size().to_dict(),
        "seed_ids": sorted(df["seed_id"].unique().tolist()),
        "restricted_file_relative_path": "strengthening/restricted_local/ce/retrieval_audit_ce_seeds_candidates.csv",
    }
    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(json.dumps({k: v for k, v in manifest.items() if k not in ("rows_per_seed",)}, indent=2, default=str))


if __name__ == "__main__":
    main()
