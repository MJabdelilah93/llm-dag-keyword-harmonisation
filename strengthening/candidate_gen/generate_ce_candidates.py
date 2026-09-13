"""Stage 2 + Stage 4 + Stage 5(CE): generate the new, UNLABELLED 400-pair
circular-economy candidate set for the M7 strengthening phase.

Reads the legacy CE keyword-frequency universe and legacy dev/test pair
sets READ-ONLY from the legacy data root (never writes there). Writes the
restricted (string-bearing) candidate file under
strengthening/restricted_local/ce/ (gitignored) and a public-safe,
string-free manifest under strengthening/benchmark/.

Deterministic: every stage seeded from protocol_v1.yaml's random_seed (42).
Pair IDs are content-hash derived (see pair_ids.py) so they are identical
across reruns regardless of any nondeterminism in intermediate ordering.
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from .features import EmbeddingIndex, TfidfIndex, top_k_per_row
from .legacy_access import legacy_excluded_pair_keys, load_keyword_frequencies, sha256_of
from .normalise import normalise, unordered_pair_key
from .pair_ids import stable_pair_id
from .stratify import classify_pair

HERE = Path(__file__).resolve()
STRENGTHENING_ROOT = HERE.parents[1]  # .../strengthening
CONFIG_PATH = STRENGTHENING_ROOT / "config" / "protocol_v1.yaml"

RESTRICTED_OUT = STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv"
MANIFEST_OUT = STRENGTHENING_ROOT / "benchmark" / "ce_400_manifest.json"

# Universe sizing: deterministic top-frequency slice + a seeded random
# low-frequency slice for stratum diversity (malformed/short-form/rare
# acronym patterns cluster in the long tail). Full O(n^2) over the entire
# ~55k-keyword legacy universe is intractable for a single-pass run; this
# subsample is a documented scoping decision, not a silent shortcut.
N_TOP_BY_FREQUENCY = 3500
N_RANDOM_LOW_FREQUENCY = 500
LOW_FREQUENCY_THRESHOLD = 3  # keywords with frequency < this are "low-freq" pool

TOP_K_TFIDF = 15
TOP_K_EMBEDDING = 15
TFIDF_MIN_SCORE = 0.30
EMBEDDING_MIN_SCORE = 0.45


def _punctuation_stripped_for_grouping(s: str) -> str:
    from .features import punctuation_stripped

    return punctuation_stripped(s)


def _singularised_for_grouping(s: str) -> str:
    from .features import _singularise

    return _singularise(normalise(s))


def _initials_for_grouping(s: str) -> str:
    words = re.findall(r"[A-Za-z]+", s)
    return "".join(w[0].upper() for w in words if w)


def build_universe(freq_df: pd.DataFrame, seed: int) -> list[str]:
    freq_df = freq_df.dropna(subset=["keyword"]).copy()
    freq_df["keyword"] = freq_df["keyword"].astype(str)
    freq_df = freq_df.drop_duplicates(subset=["keyword"])
    freq_df = freq_df.sort_values(by=["frequency", "keyword"], ascending=[False, True])

    top = freq_df.head(N_TOP_BY_FREQUENCY)["keyword"].tolist()
    low_pool = freq_df[freq_df["frequency"] < LOW_FREQUENCY_THRESHOLD].sort_values("keyword")
    low_pool_list = low_pool["keyword"].tolist()
    rng = random.Random(seed)
    low_sample = rng.sample(low_pool_list, k=min(N_RANDOM_LOW_FREQUENCY, len(low_pool_list)))

    universe = list(dict.fromkeys(top + low_sample))  # preserve order, de-dup
    return universe


def _add_structural_groups(universe: list[str], pool: dict[tuple[str, str], dict]):
    # Stratum i seed: group by full normalisation (identical normalised form).
    by_norm: dict[str, list[str]] = defaultdict(list)
    for s in universe:
        by_norm[normalise(s)].append(s)
    for group in by_norm.values():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    _add_candidate(pool, group[i], group[j], route="structural_normalised_group")

    # Stratum iv seed: group by punctuation-stripped normalised form.
    by_punct: dict[str, list[str]] = defaultdict(list)
    for s in universe:
        by_punct[_punctuation_stripped_for_grouping(s)].append(s)
    for group in by_punct.values():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    _add_candidate(pool, group[i], group[j], route="structural_punctuation_group")

    # Stratum v seed: group by singularised normalised form.
    by_sing: dict[str, list[str]] = defaultdict(list)
    for s in universe:
        by_sing[_singularised_for_grouping(s)].append(s)
    for group in by_sing.values():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    _add_candidate(pool, group[i], group[j], route="structural_plural_group")

    # Stratum iii seed: acronym-like keywords matched to full-form keywords
    # sharing the same initials.
    by_initials: dict[str, list[str]] = defaultdict(list)
    for s in universe:
        ini = _initials_for_grouping(s)
        if len(ini) >= 2:
            by_initials[ini].append(s)
    from .features import _is_acronym_like

    for s in universe:
        if _is_acronym_like(s):
            letters = re.sub(r"[^A-Za-z]", "", s).upper()
            for full in by_initials.get(letters, []):
                if normalise(full) != normalise(s):
                    _add_candidate(pool, s, full, route="structural_acronym_initials")


def _add_candidate(pool: dict, a: str, b: str, route: str, embedding_cosine: float | None = None, rank: int | None = None):
    # Pool key is the RAW (unnormalised) unordered pair. This deliberately
    # does NOT collapse on normalised form: two different raw strings that
    # share the same normalised form (e.g. "Circular economy" /
    # "circular economy") are exactly what stratum i candidates are, and
    # must not be treated as a self-pair. Only a truly identical raw string
    # against itself is rejected here.
    if a == b:
        return
    key = (a, b) if a <= b else (b, a)
    entry = pool.setdefault(key, {"a": a, "b": b, "routes": set(), "ranks": {}, "embedding_cosine": None})
    entry["routes"].add(route)
    if rank is not None:
        entry["ranks"][route] = rank
    if embedding_cosine is not None:
        entry["embedding_cosine"] = embedding_cosine


def generate(seed: int = 42) -> dict:
    freq_df, freq_path = load_keyword_frequencies()
    freq_hash = sha256_of(freq_path)
    excluded_keys = legacy_excluded_pair_keys()

    universe = build_universe(freq_df, seed)
    freq_lookup = dict(zip(freq_df["keyword"].astype(str), freq_df["frequency"]))

    # Structural routes (i: case/whitespace, iii: acronym-initials, iv:
    # punctuation/hyphenation, v: singular/plural) are O(n) groupby
    # operations -- cheap enough to run over the FULL ~55k-keyword legacy
    # universe rather than the tractability-driven embedding/TF-IDF
    # subsample below. Running them over the small subsample only starved
    # stratum i in particular: the corpus's few "obvious" case-variant
    # duplicates (e.g. "Circular economy" / "circular economy") are
    # disproportionately already consumed by the legacy 500-pair benchmark,
    # so a small subsample can easily contain zero surviving candidates
    # even though the full corpus has many more (this was observed and
    # diagnosed in a first run of this script; the fix is this full-corpus
    # pass, not a quota reallocation).
    full_universe = freq_df.dropna(subset=["keyword"])["keyword"].astype(str).drop_duplicates().tolist()

    pool: dict[tuple[str, str], dict] = {}
    _add_structural_groups(full_universe, pool)

    tfidf_index = TfidfIndex(universe)
    tfidf_sim = tfidf_index.similarity_matrix()
    tfidf_neighbours = top_k_per_row(tfidf_sim, TOP_K_TFIDF, TFIDF_MIN_SCORE)
    for i, neighbours in tfidf_neighbours.items():
        for rank, (j, score) in enumerate(neighbours, start=1):
            _add_candidate(pool, universe[i], universe[j], route="tfidf_topk", rank=rank)

    embedding_index = EmbeddingIndex(universe)
    emb_sim = embedding_index.similarity_matrix()
    emb_neighbours = top_k_per_row(emb_sim, TOP_K_EMBEDDING, EMBEDDING_MIN_SCORE)
    for i, neighbours in emb_neighbours.items():
        for rank, (j, score) in enumerate(neighbours, start=1):
            _add_candidate(pool, universe[i], universe[j], route="embedding_topk", embedding_cosine=score, rank=rank)

    # Malformed strings paired with their nearest structurally-similar
    # neighbour (their realistic annotation difficulty is "which correct
    # keyword does this garbled string correspond to").
    from .features import malformed_feature

    idx_of = {s: i for i, s in enumerate(universe)}
    for s in universe:
        if malformed_feature(s):
            i = idx_of[s]
            for j, score in (tfidf_neighbours.get(i, [])[:1] + emb_neighbours.get(i, [])[:1]):
                _add_candidate(pool, s, universe[j], route="malformed_nearest_neighbour")

    # Classify every candidate pair; compute embedding cosine for any pair
    # that did not already surface one via the embedding-neighbour route.
    stratified: dict[str, list[dict]] = defaultdict(list)
    seen_norm_keys: set[tuple[str, str]] = set()
    for raw_key in sorted(pool.keys()):
        entry = pool[raw_key]
        a, b = entry["a"], entry["b"]
        norm_key = unordered_pair_key(a, b)
        if norm_key in excluded_keys:
            continue
        if norm_key in seen_norm_keys:
            continue  # a different raw pair already represents this normalised pair identity
        seen_norm_keys.add(norm_key)
        emb_cos = entry["embedding_cosine"]
        if emb_cos is None and a in idx_of and b in idx_of:
            emb_cos = embedding_index.cosine(idx_of[a], idx_of[b])
        result = classify_pair(a, b, emb_cos)
        if result.stratum is None:
            continue
        pair_id = stable_pair_id(a, b, "ce")
        record = {
            "pair_id": pair_id,
            "domain": "circular_economy",
            "string_a": a,
            "string_b": b,
            "frequency_a": int(freq_lookup.get(a, 0)),
            "frequency_b": int(freq_lookup.get(b, 0)),
            "canonical_unordered_pair_key": "|".join(norm_key),
            "candidate_stratum": result.stratum,
            "proposing_routes": ";".join(sorted(entry["routes"])),
            "route_specific_ranks": json.dumps(entry["ranks"], sort_keys=True),
            "jaro_winkler_score": round(result.jw_score, 6),
            "tfidf_cosine": round(
                tfidf_index.cosine(idx_of[a], idx_of[b]) if a in idx_of and b in idx_of else 0.0, 6
            ),
            "embedding_cosine": round(emb_cos, 6) if emb_cos is not None else "",
            "acronym_feature": result.acronym,
            "punctuation_feature": result.punctuation,
            "plural_feature": result.plural,
            "malformed_feature": result.malformed,
            "short_form_feature": result.short_form,
            "generation_seed": seed,
            "generation_timestamp_utc": None,  # filled in by caller (excluded from determinism hash)
            "source_provenance": f"legacy_ce_author_keyword_frequencies(sha256={freq_hash[:16]})",
            "gold_label": "",
        }
        stratified[result.stratum].append(record)

    return {
        "stratified": stratified,
        "universe_size": len(universe),
        "freq_path": str(freq_path),
        "freq_hash": freq_hash,
        "excluded_legacy_pair_count": len(excluded_keys),
        "pool_size_before_stratification": len(pool),
    }


def sample_quota(stratified: dict[str, list[dict]], quotas: dict[str, int], seed: int) -> tuple[list[dict], dict[str, dict]]:
    rng = random.Random(seed)
    selected: list[dict] = []
    shortfall_report: dict[str, dict] = {}
    for stratum, quota in quotas.items():
        if stratum == "total":
            continue
        pool = sorted(stratified.get(stratum, []), key=lambda r: r["pair_id"])
        available = len(pool)
        if available >= quota:
            chosen = rng.sample(pool, quota)
        else:
            chosen = pool
        shortfall_report[stratum] = {"quota": quota, "available": available, "selected": len(chosen), "shortfall": max(0, quota - available)}
        selected.extend(chosen)
    return selected, shortfall_report


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    seed = config["random_seed"]
    quotas = config["stratum_quotas"]["circular_economy_400"]

    result = generate(seed=seed)
    selected, shortfall_report = sample_quota(result["stratified"], quotas, seed)

    now = datetime.now(timezone.utc).isoformat()
    for rec in selected:
        rec["generation_timestamp_utc"] = now

    RESTRICTED_OUT.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(selected)
    df.to_csv(RESTRICTED_OUT, index=False, encoding="utf-8")

    # Determinism check material: hash of pair_id+stratum+scores only,
    # excluding the wall-clock timestamp column (which necessarily differs
    # across reruns even though the sampling itself is fully deterministic).
    import hashlib

    det_cols = [c for c in df.columns if c not in ("generation_timestamp_utc",)]
    det_payload = df[det_cols].sort_values("pair_id").to_csv(index=False).encode("utf-8")
    determinism_hash = hashlib.sha256(det_payload).hexdigest()

    manifest = {
        "generated_at_utc": now,
        "random_seed": seed,
        "universe_size": result["universe_size"],
        "legacy_frequency_source": {"path": result["freq_path"], "sha256": result["freq_hash"]},
        "excluded_legacy_pair_count": result["excluded_legacy_pair_count"],
        "pool_size_before_stratification": result["pool_size_before_stratification"],
        "quotas": quotas,
        "shortfall_report": shortfall_report,
        "total_selected": len(selected),
        "stratum_counts": {s: sum(1 for r in selected if r["candidate_stratum"] == s) for s in quotas if s != "total"},
        "score_distributions": {
            "jaro_winkler_score": _dist([r["jaro_winkler_score"] for r in selected]),
            "tfidf_cosine": _dist([r["tfidf_cosine"] for r in selected]),
            "embedding_cosine": _dist([r["embedding_cosine"] for r in selected if r["embedding_cosine"] != ""]),
        },
        "pair_ids": sorted(r["pair_id"] for r in selected),
        "determinism_hash_excl_timestamp": determinism_hash,
        "restricted_file_relative_path": "strengthening/restricted_local/ce/ce_400_annotation_candidates_unlabelled.csv",
    }
    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(json.dumps({k: v for k, v in manifest.items() if k != "pair_ids"}, indent=2))


def _dist(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    values = sorted(values)
    n = len(values)
    return {
        "n": n,
        "min": values[0],
        "max": values[-1],
        "mean": round(sum(values) / n, 6),
        "median": values[n // 2],
    }


if __name__ == "__main__":
    main()
