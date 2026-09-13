"""Tests for strengthening.metrics.cluster.

The B-cubed and pairwise numbers below are worked out item by item and pair
by pair in comments before being asserted.
"""

from __future__ import annotations

import pytest

from strengthening.metrics.cluster import (
    assignment_to_clusters,
    bcubed_scores,
    clusters_to_assignment,
    component_size_summary,
    exact_cluster_recovery_rate,
    overmerge_diagnostics,
    pairwise_scores,
    to_assignment,
    undermerge_diagnostics,
)

# ---------------------------------------------------------------------------
# Hand-constructed gold vs predicted example (6 items: a b c d e f)
# ---------------------------------------------------------------------------
#   GOLD:       G1 = {a, b, c}   G2 = {d, e}   G3 = {f}
#   PREDICTED:  P1 = {a, b, c, d}  P2 = {e}    P3 = {f}
#
# So P1 wrongly absorbs d (an overmerge of G1 with G2) and consequently
# splits G2 across P1 and P2 (an undermerge of G2).
#
# ---- B-cubed, per item: precision_i = |P&G| / |P| , recall_i = |P&G| / |G|
#   a: P = {a,b,c,d} (4), G = {a,b,c} (3), |P&G| = 3 -> Pi = 3/4, Ri = 3/3 = 1
#   b: same as a                                     -> Pi = 3/4, Ri = 1
#   c: same as a                                     -> Pi = 3/4, Ri = 1
#   d: P = {a,b,c,d} (4), G = {d,e} (2),   |P&G| = 1 -> Pi = 1/4, Ri = 1/2
#   e: P = {e} (1),       G = {d,e} (2),   |P&G| = 1 -> Pi = 1/1 = 1, Ri = 1/2
#   f: P = {f} (1),       G = {f} (1),     |P&G| = 1 -> Pi = 1, Ri = 1
#
#   B3 precision = (3/4 + 3/4 + 3/4 + 1/4 + 1 + 1) / 6
#                = (2.25 + 0.25 + 2) / 6 = 4.5 / 6 = 0.75  (= 3/4)
#   B3 recall    = (1 + 1 + 1 + 1/2 + 1/2 + 1) / 6
#                = 5 / 6 = 0.8333...
#   B3 F1        = 2 * (3/4) * (5/6) / (3/4 + 5/6)
#                = (2 * 15/24) / (9/12 + 10/12)
#                = (5/4) / (19/12)
#                = (5/4) * (12/19) = 60/76 = 15/19 = 0.7894736842...
#
# ---- Pairwise (same-cluster relation; clusters are transitively closed)
#   gold same-cluster pairs: G1 -> ab ac bc ; G2 -> de ; G3 -> none  => 4
#   pred same-cluster pairs: P1 -> ab ac ad bc bd cd ; P2, P3 -> none => 6
#   intersection: ab ac bc                                            => 3
#   pairwise precision = 3 / 6 = 0.5
#   pairwise recall    = 3 / 4 = 0.75
#   pairwise F1        = 2 * 0.5 * 0.75 / (0.5 + 0.75) = 0.75 / 1.25 = 0.6
#
# ---- Exact recovery: only G3 = {f} is reproduced exactly -> 1 / 3
GOLD = {"a": "G1", "b": "G1", "c": "G1", "d": "G2", "e": "G2", "f": "G3"}
PRED = {"a": "P1", "b": "P1", "c": "P1", "d": "P1", "e": "P2", "f": "P3"}


# ---------------------------------------------------------------------------
# Representation and converters
# ---------------------------------------------------------------------------
def test_to_assignment_accepts_an_iterable_of_clusters() -> None:
    as_clusters = [{"a", "b", "c"}, {"d", "e"}, {"f"}]
    assignment = to_assignment(as_clusters)
    # Cluster ids become 0, 1, 2 in iteration order.
    assert assignment["a"] == assignment["b"] == assignment["c"] == 0
    assert assignment["d"] == assignment["e"] == 1
    assert assignment["f"] == 2
    # The two representations must score identically.
    assert bcubed_scores(as_clusters, PRED).to_dict() == bcubed_scores(
        GOLD, PRED
    ).to_dict()


def test_clusters_to_assignment_handles_cluster_keyed_mappings() -> None:
    keyed = {"G1": ["a", "b", "c"], "G2": ["d", "e"], "G3": ["f"]}
    assert clusters_to_assignment(keyed) == GOLD


def test_assignment_to_clusters_inverts_an_assignment() -> None:
    assert assignment_to_clusters(GOLD) == {
        "G1": {"a", "b", "c"},
        "G2": {"d", "e"},
        "G3": {"f"},
    }


def test_overlapping_clusters_are_rejected() -> None:
    with pytest.raises(ValueError):
        to_assignment([{"a", "b"}, {"b", "c"}])


def test_mismatched_item_sets_are_rejected() -> None:
    with pytest.raises(ValueError):
        bcubed_scores(GOLD, {"a": "P1", "b": "P1"})


# ---------------------------------------------------------------------------
# B-cubed
# ---------------------------------------------------------------------------
def test_bcubed_matches_the_hand_computed_values() -> None:
    scores = bcubed_scores(GOLD, PRED)
    assert scores.precision == pytest.approx(0.75)
    assert scores.recall == pytest.approx(5.0 / 6.0)
    assert scores.f1 == pytest.approx(15.0 / 19.0)
    assert scores.n_items == 6
    # Precision and recall differ here, so a P/R swap would be caught.
    assert scores.precision != pytest.approx(scores.recall)


def test_bcubed_is_perfect_on_identical_partitions() -> None:
    scores = bcubed_scores(GOLD, GOLD)
    assert scores.precision == pytest.approx(1.0)
    assert scores.recall == pytest.approx(1.0)
    assert scores.f1 == pytest.approx(1.0)


def test_bcubed_all_singletons_is_perfect_precision_and_hand_computed_recall() -> None:
    # Every item alone: precision_i = 1/1 = 1 for all six items -> P = 1.
    # recall_i = 1/|G(i)|: a,b,c -> 1/3 each ; d,e -> 1/2 each ; f -> 1
    #   sum = 3*(1/3) + 2*(1/2) + 1 = 1 + 1 + 1 = 3 -> R = 3/6 = 0.5
    singletons = {item: item for item in GOLD}
    scores = bcubed_scores(GOLD, singletons)
    assert scores.precision == pytest.approx(1.0)
    assert scores.recall == pytest.approx(0.5)


def test_bcubed_on_empty_partitions_is_zero() -> None:
    scores = bcubed_scores({}, {})
    assert (scores.precision, scores.recall, scores.f1, scores.n_items) == (
        0.0,
        0.0,
        0.0,
        0,
    )


# ---------------------------------------------------------------------------
# Pairwise
# ---------------------------------------------------------------------------
def test_pairwise_matches_the_hand_computed_values() -> None:
    scores = pairwise_scores(GOLD, PRED)
    assert scores.precision == pytest.approx(0.5)  # 3 of 6 predicted pairs
    assert scores.recall == pytest.approx(0.75)  # 3 of 4 gold pairs
    assert scores.f1 == pytest.approx(0.6)


def test_pairwise_is_perfect_on_identical_partitions() -> None:
    scores = pairwise_scores(GOLD, GOLD)
    assert scores.precision == pytest.approx(1.0)
    assert scores.recall == pytest.approx(1.0)
    assert scores.f1 == pytest.approx(1.0)


def test_pairwise_all_singletons_has_no_predicted_pairs() -> None:
    # No predicted same-cluster pairs at all -> precision denominator is 0,
    # which the documented convention reports as 0.0 (never NaN).
    singletons = {item: item for item in GOLD}
    scores = pairwise_scores(GOLD, singletons)
    assert scores.precision == 0.0
    assert scores.recall == 0.0
    assert scores.f1 == 0.0


# ---------------------------------------------------------------------------
# Exact cluster recovery
# ---------------------------------------------------------------------------
def test_exact_recovery_of_identical_partitions_is_one() -> None:
    assert exact_cluster_recovery_rate(GOLD, GOLD) == pytest.approx(1.0)


def test_exact_recovery_drops_when_one_cluster_is_split() -> None:
    # Gold G1 = {a,b,c}, G2 = {d,e}. Predicted keeps G1 intact but splits G2
    # into {d} and {e}: 1 of 2 gold clusters recovered exactly -> 0.5.
    gold = {"a": "G1", "b": "G1", "c": "G1", "d": "G2", "e": "G2"}
    split = {"a": "P1", "b": "P1", "c": "P1", "d": "P2", "e": "P3"}
    rate = exact_cluster_recovery_rate(gold, split)
    assert rate == pytest.approx(0.5)
    assert rate < 1.0


def test_exact_recovery_on_the_worked_example_is_one_third() -> None:
    # Only G3 = {f} survives intact; G1 gained d and G2 lost d.
    assert exact_cluster_recovery_rate(GOLD, PRED) == pytest.approx(1.0 / 3.0)


def test_exact_recovery_does_not_credit_a_superset() -> None:
    # A single predicted cluster containing everything is a superset of each
    # gold cluster but reproduces none of them exactly.
    merged = {item: "ALL" for item in GOLD}
    assert exact_cluster_recovery_rate(GOLD, merged) == 0.0


# ---------------------------------------------------------------------------
# Overmerge / undermerge diagnostics
# ---------------------------------------------------------------------------
def test_overmerge_diagnostics_on_the_worked_example() -> None:
    # P1 = {a,b,c,d} touches gold G1 and G2 -> exactly one offending pair.
    diag = overmerge_diagnostics(GOLD, PRED)
    assert diag.n_overmerged_predicted_clusters == 1
    assert diag.n_gold_cluster_pairs_merged == 1
    assert diag.n_gold_clusters_involved == 2
    assert diag.gold_cluster_id_pairs == (("G1", "G2"),)
    assert diag.predicted_cluster_ids == ("P1",)


def test_overmerge_diagnostics_counts_every_pair_in_a_big_merge() -> None:
    # One predicted cluster swallowing G1, G2 and G3 spans 3 gold clusters,
    # i.e. 3 * 2 / 2 = 3 offending pairs.
    merged = {item: "ALL" for item in GOLD}
    diag = overmerge_diagnostics(GOLD, merged)
    assert diag.n_gold_cluster_pairs_merged == 3
    assert diag.gold_cluster_id_pairs == (
        ("G1", "G2"),
        ("G1", "G3"),
        ("G2", "G3"),
    )


def test_no_overmerge_when_predictions_only_split() -> None:
    singletons = {item: item for item in GOLD}
    diag = overmerge_diagnostics(GOLD, singletons)
    assert diag.n_overmerged_predicted_clusters == 0
    assert diag.gold_cluster_id_pairs == ()


def test_undermerge_diagnostics_on_the_worked_example() -> None:
    # G2 = {d,e} is spread over P1 and P2 -> 1 split gold cluster, 1 extra
    # fragment. G1 sits wholly inside P1 and G3 wholly inside P3.
    diag = undermerge_diagnostics(GOLD, PRED)
    assert diag.n_split_gold_clusters == 1
    assert diag.n_extra_fragments == 1
    assert diag.gold_cluster_ids == ("G2",)
    assert diag.fragments_by_gold_cluster == {"G2": 2}


def test_undermerge_diagnostics_on_full_fragmentation() -> None:
    # Every item alone: G1 (3 items) -> 3 fragments, G2 (2) -> 2, G3 (1) -> 1.
    # Split gold clusters: G1 and G2 (G3 is a singleton and stays intact).
    # Extra fragments = (3 - 1) + (2 - 1) = 3.
    singletons = {item: item for item in GOLD}
    diag = undermerge_diagnostics(GOLD, singletons)
    assert diag.n_split_gold_clusters == 2
    assert diag.n_extra_fragments == 3
    assert diag.gold_cluster_ids == ("G1", "G2")
    assert diag.fragments_by_gold_cluster == {"G1": 3, "G2": 2}


def test_no_undermerge_on_identical_partitions() -> None:
    diag = undermerge_diagnostics(GOLD, GOLD)
    assert diag.n_split_gold_clusters == 0
    assert diag.n_extra_fragments == 0


# ---------------------------------------------------------------------------
# Component size distribution
# ---------------------------------------------------------------------------
def test_component_size_summary_of_the_predicted_partition() -> None:
    # Predicted component sizes are [4, 1, 1] (P1, P2, P3).
    #   count = 3, items = 6, min = 1, max = 4
    #   mean   = (4 + 1 + 1) / 3 = 6 / 3 = 2.0
    #   median of sorted [1, 1, 4] = 1
    #   histogram = {1: 2, 4: 1}
    summary = component_size_summary(PRED)
    assert summary.n_components == 3
    assert summary.n_items == 6
    assert summary.min_size == 1
    assert summary.max_size == 4
    assert summary.mean_size == pytest.approx(2.0)
    assert summary.median_size == pytest.approx(1.0)
    assert summary.histogram == {1: 2, 4: 1}


def test_component_size_summary_of_the_gold_partition() -> None:
    # Gold sizes are [3, 2, 1]: mean = 6/3 = 2.0, median of [1,2,3] = 2.
    summary = component_size_summary(GOLD)
    assert summary.n_components == 3
    assert summary.mean_size == pytest.approx(2.0)
    assert summary.median_size == pytest.approx(2.0)
    assert summary.histogram == {1: 1, 2: 1, 3: 1}


def test_component_size_summary_of_an_empty_partition() -> None:
    summary = component_size_summary({})
    assert summary.n_components == 0
    assert summary.n_items == 0
    assert summary.min_size is None
    assert summary.max_size is None
    assert summary.histogram == {}
