"""C1 Task 12: observed transitive contradiction diagnostic.

REPLACES the invalid full-cluster-gold plan: this benchmark's 900 pairs
are a sampled subset, not an exhaustive pairwise-labelled partition, so
B-cubed / exact-cluster-recovery / full over-under-merge evaluation
against a "gold partition" manufactured from this sparse sample would be
misleading (see strengthening/reports/MINIMUM_SUFFICIENT_EXPERIMENT_PLAN.md).
That is NOT run here.

Instead, for each evaluated method:

  1. take its predicted match edges among benchmark keyword strings;
  2. build deterministic connected components from those predicted edges
     (reusing the same union-find utility already used by B8's own
     clustering stage);
  3. for every benchmark pair explicitly gold-labelled NON-MATCH, check
     whether the two strings end up in the same predicted component --
     via a DIRECT predicted-match edge between exactly those two strings
     (a plain pairwise false positive), or only TRANSITIVELY, through a
     chain of other predicted-match edges elsewhere in the graph (the
     genuinely interesting case: a contradiction the pairwise metrics
     alone would never surface).

This is a LOWER-BOUND SAFETY DIAGNOSTIC, not complete cluster precision/
recall: the gold graph is incomplete (only 900 sampled pairs are
labelled at all), so it can only detect contradictions among pairs that
happen to both be in the benchmark and reachable through other benchmark
pairs' predicted edges -- it cannot see everything a full pairwise
universe would.

Also counts fully-observed gold "closed triangles" -- triples of
keywords where all three pairwise gold judgments happen to exist within
the 900-pair sample. If this count is too small to support a stable
estimate, that is reported explicitly and no consistency analysis is
forced on it.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ..baselines.b8_retrieve_then_prompt.clustering import connected_components
from .frozen_inputs import GOLD_CSV, verify_gold_hash

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
MIN_TRIANGLES_FOR_ANALYSIS = 10


def load_gold_full() -> pd.DataFrame:
    verify_gold_hash()
    return pd.read_csv(GOLD_CSV, dtype=str)


def count_closed_triangles(gold: pd.DataFrame) -> dict:
    """Triples of strings where all three pairwise gold judgments exist
    within the 900-pair sample (regardless of label)."""
    adjacency: dict[str, set[str]] = defaultdict(set)
    edge_pair_id: dict[frozenset, str] = {}
    for _, row in gold.iterrows():
        a, b = row["string_a"], row["string_b"]
        adjacency[a].add(b)
        adjacency[b].add(a)
        edge_pair_id[frozenset((a, b))] = row["pair_id"]

    triangles = set()
    for key in list(edge_pair_id.keys()):
        a, b = tuple(key)
        common = adjacency[a] & adjacency[b]
        for c in common:
            triangle = frozenset((a, b, c))
            if len(triangle) == 3:
                triangles.add(triangle)
    return {"n_closed_triangles": len(triangles), "triangles": triangles}


def build_predicted_match_edges(predictions: pd.DataFrame, method_col: str) -> list[tuple[str, str]]:
    matched = predictions[predictions[method_col] == "match"]
    return list(zip(matched["string_a"], matched["string_b"]))


def diagnose_method(gold: pd.DataFrame, predictions: pd.DataFrame, method_col: str) -> dict:
    merged = gold.merge(predictions[["pair_id", method_col]], on="pair_id", how="inner", validate="one_to_one")
    edges = build_predicted_match_edges(merged, method_col)
    all_nodes = set(merged["string_a"]) | set(merged["string_b"])
    clustering = connected_components(edges, nodes=all_nodes)

    non_match = merged[merged["final_gold_label"] == "non-match"]
    n_evaluated = len(non_match)
    n_connected = 0
    n_direct = 0
    n_transitive_only = 0
    component_sizes_involved = []
    direct_match_pairs = {frozenset((a, b)) for a, b in edges}

    for _, row in non_match.iterrows():
        a, b = row["string_a"], row["string_b"]
        comp_a, comp_b = clustering.assignments.get(a), clustering.assignments.get(b)
        if comp_a is not None and comp_a == comp_b:
            n_connected += 1
            if frozenset((a, b)) in direct_match_pairs:
                n_direct += 1
            else:
                n_transitive_only += 1
            comp_size = sum(1 for v in clustering.assignments.values() if v == comp_a)
            component_sizes_involved.append(comp_size)

    return {
        "method": method_col,
        "n_gold_non_match_evaluated": n_evaluated,
        "n_connected_incorrectly": n_connected,
        "proportion_connected_incorrectly": (n_connected / n_evaluated if n_evaluated else None),
        "n_direct_error": n_direct,
        "n_transitive_only_contradiction": n_transitive_only,
        "component_sizes_involved": sorted(component_sizes_involved, reverse=True)[:20],
        "n_predicted_clusters": clustering.n_clusters,
        "n_predicted_singletons": clustering.n_singletons,
        "is_lower_bound_safety_diagnostic_not_complete_cluster_metric": True,
    }


def run(predictions_by_method: dict[str, tuple[pd.DataFrame, str]]) -> dict:
    """predictions_by_method: {display_name: (predictions_df, method_col)}
    where predictions_df has pair_id + method_col columns."""
    gold = load_gold_full()
    triangle_info = count_closed_triangles(gold)
    n_triangles = triangle_info["n_closed_triangles"]

    method_results = {}
    for display_name, (predictions_df, method_col) in predictions_by_method.items():
        method_results[display_name] = diagnose_method(gold, predictions_df, method_col)

    result = {
        "n_closed_triangles_observed": n_triangles,
        "min_triangles_for_consistency_analysis": MIN_TRIANGLES_FOR_ANALYSIS,
        "closed_triangle_consistency_analysis_performed": n_triangles >= MIN_TRIANGLES_FOR_ANALYSIS,
        "methods": method_results,
    }
    with open(REPORTS_DIR / "OBSERVED_TRANSITIVE_CONTRADICTION_DIAGNOSTIC.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    _write_markdown(result)
    return result


def _write_markdown(result: dict) -> None:
    lines = [
        "# Observed transitive contradiction diagnostic",
        "",
        "LOWER-BOUND SAFETY DIAGNOSTIC ONLY -- not complete cluster precision/recall "
        "(the gold graph is an incomplete, sampled 900-pair subset, not an exhaustive partition).",
        "",
        f"- Closed gold triangles observed (all 3 pairwise judgments present in the sample): {result['n_closed_triangles_observed']}",
        f"- Consistency analysis performed on those triangles: {result['closed_triangle_consistency_analysis_performed']} "
        f"(requires >= {result['min_triangles_for_consistency_analysis']})",
        "",
        "| Method | Gold non-match evaluated | Connected incorrectly | Proportion | Direct | Transitive-only |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, m in result["methods"].items():
        prop = f"{m['proportion_connected_incorrectly']:.4f}" if m["proportion_connected_incorrectly"] is not None else "n/a"
        lines.append(
            f"| {name} | {m['n_gold_non_match_evaluated']} | {m['n_connected_incorrectly']} | {prop} | "
            f"{m['n_direct_error']} | {m['n_transitive_only_contradiction']} |"
        )
    (REPORTS_DIR / "OBSERVED_TRANSITIVE_CONTRADICTION_DIAGNOSTIC.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    import pandas as pd

    from .b1_b5_baselines import OUT_DIR as B1_B5_DIR

    predictions_by_method = {}
    for partition_marker, method_col in (("pooled900", "B1_Exact"), ("pooled900", "B2_Normalised"),
                                          ("pooled900", "B3_JaroWinkler"), ("pooled900", "B4_TFIDF"),
                                          ("pooled900", "B5_Embedding")):
        df = pd.read_csv(B1_B5_DIR / f"{partition_marker}_b1_b5_predictions.csv", dtype=str)
        predictions_by_method[method_col] = (df, method_col)
    run(predictions_by_method)
