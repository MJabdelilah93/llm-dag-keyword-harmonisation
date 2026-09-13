"""Step 8: biomedical (diabetes-mellitus) retrieval-audit tooling.

Only run once the diabetes 500-pair benchmark has passed its feasibility
gate (Step 5/6). Mirrors strengthening/candidate_gen/generate_ce_
retrieval_audit.py's design (50 seeds spanning frequency/difficulty
deciles, high-recall candidate union across routes, deterministic
outside-pool sample) but sources from the strict diabetes keyword
universe. Since this content is CC BY/CC0 (open, redistributable), the
output is written directly under strengthening/retrieval_audit/, not
restricted_local/.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .features import EmbeddingIndex, TfidfIndex, jaro_winkler_score
from .generate_diabetes_candidates import (
    DOMAIN_LABEL,
    build_frequency_and_provenance,
    load_strict_eligible_keywords,
)
from .normalise import normalise

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = STRENGTHENING_ROOT / "config" / "protocol_v1.yaml"

OUT_CSV = STRENGTHENING_ROOT / "retrieval_audit" / "biomedical_diabetes_retrieval_audit_seeds_candidates.csv"
MANIFEST_OUT = STRENGTHENING_ROOT / "retrieval_audit" / "biomedical_diabetes_retrieval_audit_manifest.json"

N_SEEDS = 50
N_DECILES = 10
SEEDS_PER_DECILE = N_SEEDS // N_DECILES
TOP_K_PER_ROUTE = 50
JW_FLOOR = 0.70
OUTSIDE_POOL_PER_SEED = 5


def select_seeds(freq_df: pd.DataFrame, seed: int) -> list[str]:
    df = freq_df.sort_values(by=["frequency", "keyword_raw"], ascending=[True, True]).reset_index(drop=True)
    n = len(df)
    bucket_size = max(n // N_DECILES, 1)
    rng = random.Random(seed)
    seeds: list[str] = []
    for decile in range(N_DECILES):
        start = decile * bucket_size
        end = (decile + 1) * bucket_size if decile < N_DECILES - 1 else n
        bucket = df.iloc[start:end]["keyword_raw"].tolist()
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


def build_audit(keywords_csv: Path, seed: int = 42) -> dict:
    strict = load_strict_eligible_keywords(keywords_csv)
    freq_df, provenance = build_frequency_and_provenance(strict)

    seeds = select_seeds(freq_df, seed)
    universe = freq_df.sort_values(by=["frequency", "keyword_raw"], ascending=[False, True])["keyword_raw"].tolist()
    idx_of = {s: i for i, s in enumerate(universe)}

    tfidf_index = TfidfIndex(universe)
    embedding_index = EmbeddingIndex(universe)

    rows = []
    rng = random.Random(seed)

    for seed_id, seed_str in enumerate(seeds, start=1):
        candidates: dict[str, dict] = defaultdict(lambda: {"routes": set(), "ranks": {}, "jw": None, "tfidf": None, "emb": None})

        jw_scores = [(u, jaro_winkler_score(seed_str, u)) for u in universe if u != seed_str]
        jw_scores = [t for t in jw_scores if t[1] >= JW_FLOOR]
        jw_scores.sort(key=lambda t: -t[1])
        for rank, (u, score) in enumerate(jw_scores[:TOP_K_PER_ROUTE], start=1):
            c = candidates[u]
            c["routes"].add("jaro_winkler")
            c["ranks"]["jaro_winkler"] = rank
            c["jw"] = score

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

        for u in acronym_route_candidates(seed_str, universe):
            candidates[u]["routes"].add("acronym_heuristic")

        for u in universe:
            if u != seed_str and normalise(u) == normalise(seed_str):
                candidates[u]["routes"].add("lexical_normalised_exact")

        for cand_str, info in candidates.items():
            rows.append(
                {
                    "seed_id": f"bio_seed_{seed_id:03d}",
                    "seed_string": seed_str,
                    "candidate_string": cand_str,
                    "domain": DOMAIN_LABEL,
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

        retrieved = set(candidates.keys()) | {seed_str}
        pool_complement = [u for u in universe if u not in retrieved]
        outside_sample = rng.sample(pool_complement, min(OUTSIDE_POOL_PER_SEED, len(pool_complement)))
        for cand_str in outside_sample:
            rows.append(
                {
                    "seed_id": f"bio_seed_{seed_id:03d}",
                    "seed_string": seed_str,
                    "candidate_string": cand_str,
                    "domain": DOMAIN_LABEL,
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

    return {"rows": rows, "seeds": seeds, "universe_size": len(universe)}


def main():
    from .generate_diabetes_candidates import _paths

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    seed = config["random_seed"]

    keywords_csv = _paths("pmc_diabetes")["keywords"]
    result = build_audit(keywords_csv, seed=seed)
    df = pd.DataFrame(result["rows"])

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "generated_at_utc": now,
        "random_seed": seed,
        "n_seeds": len(result["seeds"]),
        "universe_size": result["universe_size"],
        "total_rows": len(df),
        "in_pool_rows": int((~df["outside_pool_sample"]).sum()),
        "outside_pool_rows": int(df["outside_pool_sample"].sum()),
        "seed_ids": sorted(df["seed_id"].unique().tolist()),
        "output_file_relative_path": "strengthening/retrieval_audit/biomedical_diabetes_retrieval_audit_seeds_candidates.csv",
    }
    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(json.dumps({k: v for k, v in manifest.items() if k != "seed_ids"}, indent=2, default=str))


if __name__ == "__main__":
    main()
