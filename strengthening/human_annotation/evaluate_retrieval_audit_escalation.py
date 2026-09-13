"""Compute the adjudicated positive-miss rate on the retrieval audit's
in-pool double-coded rows, per domain, and determine whether the frozen
2%-threshold escalation rule (30% -> 40% -> full double annotation)
triggers for that domain.

A positive miss: Annotator 1 in {non-match, uncertain}, Annotator 2 =
match, final adjudicated label = match (i.e. annotation 1 would have
missed a true match that the audit caught).

DO NOT run against real annotator files until Phase H3's merge and
adjudication are both complete.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from .common import cohens_kappa, raw_agreement

POSITIVE_MISS_THRESHOLD = 0.02


def final_label(row: pd.Series, adjudication_lookup: dict[str, str]) -> str | None:
    if row["agree"]:
        return row["annotator_1_label"]
    return adjudication_lookup.get(row["retrieval_pair_id"])


def evaluate_domain(merged: pd.DataFrame, master: pd.DataFrame, adjudication_lookup: dict[str, str], domain: str) -> dict:
    m = merged[merged["domain"] == domain].merge(
        master[["retrieval_pair_id", "outside_pool_sample", "audit_sample_selected"]], on="retrieval_pair_id", how="left"
    )
    in_pool_double_coded = m[m["double_coded"] & ~m["outside_pool_sample"]].copy()
    in_pool_double_coded["final_label"] = in_pool_double_coded.apply(lambda r: final_label(r, adjudication_lookup), axis=1)

    if in_pool_double_coded["final_label"].isna().any():
        missing = in_pool_double_coded[in_pool_double_coded["final_label"].isna()]["retrieval_pair_id"].tolist()
        raise ValueError(f"{len(missing)} disagreement rows have no adjudicated_label yet: {missing[:5]}")

    positive_miss = (
        in_pool_double_coded["annotator_1_label"].isin(["non-match", "uncertain"])
        & (in_pool_double_coded["annotator_2_label"] == "match")
        & (in_pool_double_coded["final_label"] == "match")
    )
    n = len(in_pool_double_coded)
    rate = positive_miss.sum() / n if n else float("nan")

    return {
        "domain": domain,
        "n_audited_in_pool_rows": n,
        "n_positive_misses": int(positive_miss.sum()),
        "adjudicated_positive_miss_rate": rate,
        "escalation_triggered": (rate > POSITIVE_MISS_THRESHOLD) if n else None,
        "raw_agreement": raw_agreement(in_pool_double_coded["annotator_1_label"].tolist(), in_pool_double_coded["annotator_2_label"].tolist()),
        "cohens_kappa": cohens_kappa(in_pool_double_coded["annotator_1_label"].tolist(), in_pool_double_coded["annotator_2_label"].tolist()),
        "note": "2% is an operational QC threshold, not a statistical standard; kappa/raw agreement are descriptive only and are NOT the escalation trigger",
    }


def select_additional_sample(
    master: pd.DataFrame, domain: str, already_selected_ids: set[str], additional_fraction: float, seed: int
) -> set[str]:
    """Deterministically pre-select an ADDITIONAL stratified sample
    (e.g. the extra 10% for a 30%->40% escalation), excluding rows already
    double-coded, using the same (route_signature, difficulty_band)
    stratification, blind to any label (none are consulted here)."""
    pool = master[
        (master["domain"] == domain) & (~master["outside_pool_sample"]) & (~master["retrieval_pair_id"].isin(already_selected_ids))
    ]
    rng = random.Random(f"{seed}-{domain}-escalation")
    selected: set[str] = set()
    for _, group in pool.groupby(["route_signature", "difficulty_band"]):
        ids = sorted(group["retrieval_pair_id"].tolist())
        k = round(len(ids) * additional_fraction)
        selected.update(rng.sample(ids, k))
    return selected


if __name__ == "__main__":
    raise SystemExit(
        "This script evaluates escalation on REAL merged+adjudicated retrieval annotations and must not be run "
        "until Phase H3 adjudication is complete. Import evaluate_domain()/select_additional_sample() instead."
    )
