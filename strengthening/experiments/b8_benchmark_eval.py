"""C1 Task 7: corrected B8 benchmark-evaluation adapter.

For every one of the 900 frozen benchmark pairs:

  1. run B8's existing lexical + dense candidate-generation logic
     (strengthening.baselines.b8_retrieve_then_prompt.pipeline.
     retrieve_candidates) WITHOUT using the pair's gold label -- the
     "universe" for a domain is simply the set of unique strings
     appearing in that domain's frozen benchmark pairs;
  2. test whether the unordered benchmark pair would be captured by B8's
     candidate generation (i.e. whether querying with either string as
     seed returns the other as a candidate);
  3. if captured: the benchmark pair's B8 prediction is WHATEVER B7
     prediction already exists for that exact pair from the separate,
     standalone B7-over-900-pairs run (see b7_runner.py) -- B8 NEVER
     issues its own additional classify() call for a pair that coincides
     with the benchmark, because that would duplicate an LLM call B7 has
     already made for the same pair;
  4. if not captured: B8 predicts non-match, because no same_as match
     edge would ever be generated for that pair operationally.

B8's own retrieve-then-classify machinery (relation_classification.
classify_pair, which DOES call client.classify() once per surviving
CANDIDATE pair) is used only when reproducing B8's ordinary standalone
behaviour on a candidate pool -- NOT here. This benchmark-evaluation path
adds ZERO additional LLM calls beyond whatever B7 already made over the
900 pairs.

Gold-independent structural statistics (candidate counts, exhaustive
comparisons, reduction ratio, lexical/dense overlap) are computed here
directly from B8's retrieval stage and require no gold and no LLM call.

"Benchmark capture rate" (gold-match pairs captured / gold-match pairs)
is computed only AFTER gold is joined, strictly as an evaluation-time
statistic (gold selects the denominator; it never influences the
retrieval decision itself). This benchmark was NOT built as an
exhaustive retrieval-gold universe, so this figure must never be called
"pair completeness", "domain-wide retrieval recall", "global candidate
recall", or an unbiased estimate of unseen equivalences -- see the
explicit caveat carried alongside every reported value below.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from ..baselines.b8_retrieve_then_prompt.pipeline import retrieve_candidates
from ..metrics.retrieval import candidate_count, exhaustive_comparisons, reduction_ratio
from .frozen_inputs import load_gold_stringonly, verify_gold_hash

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
RESTRICTED_OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "experiments" / "b8_benchmark_eval"

BENCHMARK_CAPTURE_RATE_CAVEAT = (
    "'benchmark capture rate' measures only whether B8's retrieval stage would surface each "
    "GOLD-MATCH BENCHMARK pair among its own candidates -- it is NOT pair completeness, NOT "
    "domain-wide retrieval recall, NOT global candidate recall, and NOT an unbiased estimate of "
    "unseen equivalences. The 900-pair benchmark was not built as an exhaustive retrieval-gold "
    "universe; this statistic is scoped strictly to the benchmark's own pairs."
)


def build_domain_universes(gold_stringonly: pd.DataFrame) -> dict[str, list[str]]:
    universes = {}
    for domain, group in gold_stringonly.groupby("domain"):
        universes[domain] = sorted(set(group["string_a"]) | set(group["string_b"]))
    return universes


def compute_candidate_sets(universes: dict[str, list[str]], *, top_k: int = 5, use_dense: bool = True) -> dict[str, list]:
    return {
        domain: retrieve_candidates(seeds=universe, universe=universe, top_k=top_k, use_dense=use_dense)
        for domain, universe in universes.items()
    }


def candidate_pairs_by_domain(candidate_sets: dict[str, list]) -> dict[str, set[frozenset]]:
    out = {}
    for domain, csets in candidate_sets.items():
        pairs = set()
        for cs in csets:
            for cand in cs.candidates:
                pairs.add(frozenset((cs.seed, cand.candidate)))
        out[domain] = pairs
    return out


def structural_stats(universes: dict[str, list[str]], candidate_sets: dict[str, list]) -> dict:
    stats = {}
    for domain, universe in universes.items():
        csets = candidate_sets[domain]
        all_candidate_pairs = [(cs.seed, cand.candidate) for cs in csets for cand in cs.candidates]
        n_candidates = candidate_count(all_candidate_pairs)
        n_exhaustive = exhaustive_comparisons(len(universe))
        route_counter = Counter()
        dense_available = True
        dense_unavailable_reason = None
        for cs in csets:
            if not cs.dense_available:
                dense_available = False
                dense_unavailable_reason = cs.dense_unavailable_reason
            for cand in cs.candidates:
                route_counter[cand.routes] += 1
        lexical_exclusive = sum(v for routes, v in route_counter.items() if routes == ("lexical_exact",))
        dense_exclusive = sum(v for routes, v in route_counter.items() if routes == ("dense_embedding",))
        both_routes = sum(v for routes, v in route_counter.items() if len(routes) > 1)
        stats[domain] = {
            "universe_size": len(universe),
            "total_candidate_count_distinct_pairs": n_candidates,
            "exhaustive_comparison_count": n_exhaustive,
            "reduction_ratio": reduction_ratio(n_candidates, len(universe)),
            "lexical_exclusive_candidates": lexical_exclusive,
            "dense_exclusive_candidates": dense_exclusive,
            "lexical_and_dense_overlap_candidates": both_routes,
            "dense_retrieval_available": dense_available,
            "dense_unavailable_reason": dense_unavailable_reason,
        }
    return stats


def determine_capture(gold_stringonly: pd.DataFrame, cand_pairs_by_domain: dict[str, set[frozenset]]) -> pd.DataFrame:
    captured = []
    for _, row in gold_stringonly.iterrows():
        pair_key = frozenset((row["string_a"], row["string_b"]))
        domain_pairs = cand_pairs_by_domain.get(row["domain"], set())
        captured.append(pair_key in domain_pairs)
    out = gold_stringonly[["pair_id", "domain"]].copy()
    out["b8_captured"] = captured
    return out


def compute_benchmark_capture_rate(capture_df: pd.DataFrame, gold_labels: pd.DataFrame) -> dict:
    merged = capture_df.merge(gold_labels, on="pair_id", how="inner", validate="one_to_one")
    gold_match = merged[merged["final_gold_label"] == "match"]
    n_gold_match = len(gold_match)
    n_captured = int(gold_match["b8_captured"].sum())
    rate = n_captured / n_gold_match if n_gold_match else None
    by_domain = {}
    for domain, group in gold_match.groupby("domain"):
        n = len(group)
        c = int(group["b8_captured"].sum())
        by_domain[domain] = {"n_gold_match": n, "n_captured": c, "benchmark_capture_rate": (c / n if n else None)}
    return {
        "term": "benchmark capture rate",
        "caveat": BENCHMARK_CAPTURE_RATE_CAVEAT,
        "overall": {"n_gold_match": n_gold_match, "n_captured": n_captured, "benchmark_capture_rate": rate},
        "by_domain": by_domain,
    }


def predict_b8_for_benchmark(capture_df: pd.DataFrame, b7_predictions_by_pair_id: dict[str, str] | None) -> pd.DataFrame:
    """b7_predictions_by_pair_id: pair_id -> M7-binary label ("match"/
    "non-match"), from a SEPARATE, already-run B7-over-900 pass. If None
    (no real B7 run exists yet in this phase), captured pairs are left
    unlabelled (pending) rather than fabricated."""
    predictions = []
    for _, row in capture_df.iterrows():
        if not row["b8_captured"]:
            predictions.append("non-match")
        elif b7_predictions_by_pair_id is not None and row["pair_id"] in b7_predictions_by_pair_id:
            predictions.append(b7_predictions_by_pair_id[row["pair_id"]])
        else:
            predictions.append(None)  # pending a real B7 run -- never fabricated
    out = capture_df.copy()
    out["b8_predicted_label"] = predictions
    return out


def run(*, top_k: int = 5, use_dense: bool = True, b7_predictions_by_pair_id: dict[str, str] | None = None) -> dict:
    verify_gold_hash()
    gold_stringonly = load_gold_stringonly()
    universes = build_domain_universes(gold_stringonly)
    candidate_sets = compute_candidate_sets(universes, top_k=top_k, use_dense=use_dense)
    cand_pairs = candidate_pairs_by_domain(candidate_sets)
    stats = structural_stats(universes, candidate_sets)
    capture_df = determine_capture(gold_stringonly, cand_pairs)
    predicted_df = predict_b8_for_benchmark(capture_df, b7_predictions_by_pair_id)

    RESTRICTED_OUT_DIR.mkdir(parents=True, exist_ok=True)
    predicted_df.to_csv(RESTRICTED_OUT_DIR / "b8_benchmark_predictions.csv", index=False, encoding="utf-8")

    result = {
        "top_k": top_k,
        "use_dense": use_dense,
        "performance_note": (
            "use_dense=False in the run that produced this report: B8's dense_retrieval.py re-encodes "
            "the full domain universe (~700-800 strings) on EVERY seed query rather than batch-encoding "
            "once, which was found to be impractically slow (many minutes, not completed within this "
            "session) at this benchmark's universe size (it was designed for smaller retrieval-audit "
            "seed sets). This is a real, actionable performance limitation of the existing module, not "
            "a data unavailability -- flagged here rather than silently worked around. Lexical-exact "
            "anchoring alone was used to produce the real capture/structural numbers below; a batched "
            "dense-retrieval pass is a valid follow-up given more running time, not attempted in this phase."
            if not use_dense else "dense retrieval was enabled for this run."
        ),
        "structural_stats_by_domain": stats,
        "n_pairs_captured": int(capture_df["b8_captured"].sum()),
        "n_pairs_total": len(capture_df),
        "n_pending_prediction": int(predicted_df["b8_predicted_label"].isna().sum()),
        "zero_additional_llm_calls_confirmation": (
            "B8's benchmark-evaluation predictions are either 'non-match' (structural, not captured) "
            "or a REUSE of an existing B7 prediction for the same pair_id -- classify_pair()/client.classify() "
            "is never invoked by this module."
        ),
    }
    with open(REPORTS_DIR / "B8_BENCHMARK_EVALUATION_STRUCTURAL_STATS.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    _write_markdown(result)
    return result


def _write_markdown(result: dict) -> None:
    lines = [
        "# B8 corrected benchmark-evaluation: structural statistics (gold-independent)",
        "",
        f"top_k={result['top_k']}, use_dense={result['use_dense']}",
        "",
        f"**Performance note:** {result['performance_note']}",
        "",
        "| Domain | Universe | Candidates | Exhaustive | Reduction ratio | Lexical-only | Dense-only | Both routes | Dense available |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for domain, s in result["structural_stats_by_domain"].items():
        lines.append(
            f"| {domain} | {s['universe_size']} | {s['total_candidate_count_distinct_pairs']} | "
            f"{s['exhaustive_comparison_count']} | {s['reduction_ratio']} | {s['lexical_exclusive_candidates']} | "
            f"{s['dense_exclusive_candidates']} | {s['lexical_and_dense_overlap_candidates']} | {s['dense_retrieval_available']} |"
        )
    lines += [
        "",
        f"- Benchmark pairs captured by B8 retrieval: {result['n_pairs_captured']} / {result['n_pairs_total']}",
        f"- Pairs pending a real B7 prediction (not fabricated): {result['n_pending_prediction']}",
        "",
        result["zero_additional_llm_calls_confirmation"],
    ]
    (REPORTS_DIR / "B8_BENCHMARK_EVALUATION_STRUCTURAL_STATS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
