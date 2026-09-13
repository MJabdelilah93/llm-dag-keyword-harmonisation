"""Tests for strengthening.metrics.bridge_amplification.

The canonical worked example: two correct gold clusters joined by a single
false edge, and the m*n implied equivalences that one edge creates.
"""

from __future__ import annotations

import pytest

from strengthening.metrics.bridge_amplification import (
    bridge_amplification_from_sizes,
    bridge_amplification_report,
    detect_bridge_events,
)

# ---------------------------------------------------------------------------
# The canonical hand-constructed example
# ---------------------------------------------------------------------------
#   gold cluster 1 = {a, b, c}   (size m = 3)
#   gold cluster 2 = {d, e}      (size n = 2)
#
# One false accepted match edge c--d bridges them, so connected components
# over accepted match edges produces the single component {a, b, c, d, e}.
#
# That one wrong pairwise decision implies equivalence between EVERY member
# of gold cluster 1 and EVERY member of gold cluster 2:
#   a-d a-e b-d b-e c-d c-e
#   number_of_false_implied_equivalences_created = m * n = 3 * 2 = 6
#   resulting_component_size                     = m + n = 3 + 2 = 5
GOLD = {"a": "G1", "b": "G1", "c": "G1", "d": "G2", "e": "G2"}
# The predicted partition after accepting the false edge c--d.
PRED_BRIDGED = {"a": "C1", "b": "C1", "c": "C1", "d": "C1", "e": "C1"}


def test_bridge_event_on_the_canonical_example() -> None:
    events = detect_bridge_events(GOLD, PRED_BRIDGED)
    assert len(events) == 1

    event = events[0]
    assert event.predicted_component_id == "C1"
    assert event.gold_cluster_ids == ("G1", "G2")
    assert event.size_gold_cluster_1 == 3
    assert event.size_gold_cluster_2 == 2
    assert event.number_of_false_implied_equivalences_created == 3 * 2 == 6
    assert event.resulting_component_size == 5


def test_bridge_report_on_the_canonical_example() -> None:
    report = bridge_amplification_report(GOLD, PRED_BRIDGED)
    assert report.n_bridge_events == 1
    assert report.n_bridged_components == 1
    assert report.total_false_implied_equivalences_created == 6
    assert report.largest_resulting_component_size == 5


def test_direct_helper_on_the_canonical_sizes() -> None:
    result = bridge_amplification_from_sizes(3, 2)
    assert result.number_of_false_implied_equivalences_created == 3 * 2 == 6
    assert result.resulting_component_size == 3 + 2 == 5
    assert result.size_gold_cluster_1 == 3
    assert result.size_gold_cluster_2 == 2


def test_direct_helper_arithmetic_on_further_sizes() -> None:
    # 1 * 1 = 1 false equivalence (the edge itself), component of size 2.
    one_to_one = bridge_amplification_from_sizes(1, 1)
    assert one_to_one.number_of_false_implied_equivalences_created == 1
    assert one_to_one.resulting_component_size == 2

    # 4 * 7 = 28 false equivalences, component of size 11.
    big = bridge_amplification_from_sizes(4, 7)
    assert big.number_of_false_implied_equivalences_created == 28
    assert big.resulting_component_size == 11

    # Amplification is symmetric in the two sizes.
    assert (
        bridge_amplification_from_sizes(7, 4).number_of_false_implied_equivalences_created
        == 28
    )

    # 10 * 10 = 100 from a single wrong edge.
    assert (
        bridge_amplification_from_sizes(
            10, 10
        ).number_of_false_implied_equivalences_created
        == 100
    )


def test_direct_helper_and_detection_agree_on_the_canonical_example() -> None:
    direct = bridge_amplification_from_sizes(3, 2)
    detected = detect_bridge_events(GOLD, PRED_BRIDGED)[0]
    assert (
        detected.number_of_false_implied_equivalences_created
        == direct.number_of_false_implied_equivalences_created
    )
    assert detected.resulting_component_size == direct.resulting_component_size


def test_direct_helper_rejects_bad_sizes() -> None:
    with pytest.raises(ValueError):
        bridge_amplification_from_sizes(-1, 2)
    with pytest.raises(ValueError):
        bridge_amplification_from_sizes(3, 2.5)  # type: ignore[arg-type]


def test_no_bridge_events_when_the_prediction_is_correct() -> None:
    assert detect_bridge_events(GOLD, GOLD) == []
    report = bridge_amplification_report(GOLD, GOLD)
    assert report.n_bridge_events == 0
    assert report.total_false_implied_equivalences_created == 0
    assert report.largest_resulting_component_size == 0


def test_no_bridge_events_when_the_prediction_only_splits() -> None:
    # Splitting is an undermerge, not a bridge: no component spans two gold
    # clusters, so no false equivalences are implied.
    singletons = {item: item for item in GOLD}
    assert detect_bridge_events(GOLD, singletons) == []


def test_component_spanning_three_gold_clusters_emits_one_event_per_pair() -> None:
    #   gold: G1 = {a, b} (2), G2 = {c} (1), G3 = {d} (1)
    #   predicted: one component {a, b, c, d} of size 4
    #   events: (G1,G2) -> 2*1 = 2 ; (G1,G3) -> 2*1 = 2 ; (G2,G3) -> 1*1 = 1
    #   total false implied equivalences = 2 + 2 + 1 = 5
    #   cross-check: the component asserts C(4,2) = 6 equivalences, of which
    #   only the single gold pair a-b is correct, so 6 - 1 = 5.  OK
    gold = {"a": "G1", "b": "G1", "c": "G2", "d": "G3"}
    merged = {"a": "C1", "b": "C1", "c": "C1", "d": "C1"}

    events = detect_bridge_events(gold, merged)
    assert len(events) == 3
    assert [event.gold_cluster_ids for event in events] == [
        ("G1", "G2"),
        ("G1", "G3"),
        ("G2", "G3"),
    ]
    assert [
        event.number_of_false_implied_equivalences_created for event in events
    ] == [2, 2, 1]
    assert all(event.resulting_component_size == 4 for event in events)

    report = bridge_amplification_report(gold, merged)
    assert report.total_false_implied_equivalences_created == 5
    assert report.n_bridged_components == 1


def test_partially_absorbed_gold_cluster_counts_only_the_absorbed_members() -> None:
    #   gold: G1 = {a, b, c} (3), G2 = {d, e, f} (3)
    #   predicted: C1 = {a, b, c, d} -- only ONE member of G2 was absorbed.
    #              C2 = {e, f}
    #   Inside C1 the bridged sizes are 3 (of G1) and 1 (of G2), so the false
    #   implied equivalences are 3 * 1 = 3 (a-d, b-d, c-d), and the resulting
    #   component size is 4. Counting the full gold size of G2 would wrongly
    #   report 3 * 3 = 9.
    gold = {"a": "G1", "b": "G1", "c": "G1", "d": "G2", "e": "G2", "f": "G2"}
    predicted = {"a": "C1", "b": "C1", "c": "C1", "d": "C1", "e": "C2", "f": "C2"}

    events = detect_bridge_events(gold, predicted)
    assert len(events) == 1
    event = events[0]
    assert event.size_gold_cluster_1 == 3
    assert event.size_gold_cluster_2 == 1
    assert event.number_of_false_implied_equivalences_created == 3
    assert event.resulting_component_size == 4


def test_partitions_may_be_given_as_iterables_of_clusters() -> None:
    gold_clusters = [{"a", "b", "c"}, {"d", "e"}]
    pred_clusters = [{"a", "b", "c", "d", "e"}]
    events = detect_bridge_events(gold_clusters, pred_clusters)
    assert len(events) == 1
    assert events[0].number_of_false_implied_equivalences_created == 6
    assert events[0].resulting_component_size == 5


def test_mismatched_item_sets_are_rejected() -> None:
    with pytest.raises(ValueError):
        detect_bridge_events(GOLD, {"a": "C1", "b": "C1"})
