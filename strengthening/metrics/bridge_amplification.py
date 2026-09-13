"""Bridge error amplification diagnostic.

Clustering in this protocol is connected components over accepted match
edges, so a SINGLE false-positive edge between two otherwise-correct gold
clusters silently asserts equivalence between every member of one and every
member of the other. That is the amplification: one wrong pairwise decision
becomes ``m * n`` wrong implied equivalences.

For a bridge joining a gold cluster of size ``m`` to one of size ``n``::

    number_of_false_implied_equivalences_created = m * n
    resulting_component_size                     = m + n

Two entry points
----------------
:func:`bridge_amplification_from_sizes`
    The direct helper: give it ``(m, n)`` and it returns the arithmetic
    above. No partitions needed.

:func:`detect_bridge_events` / :func:`bridge_amplification_report`
    Given a gold partition and a predicted partition, find every predicted
    component that spans more than one gold cluster and report one
    :class:`BridgeEvent` per unordered PAIR of gold clusters inside that
    component. ``size_gold_cluster_1`` / ``size_gold_cluster_2`` are the
    numbers of members of those gold clusters that are actually inside the
    component (so a partially-absorbed gold cluster is not overcounted), and
    ``resulting_component_size`` is the size of the predicted component as a
    whole. When a component contains two gold clusters in full, that
    component size equals ``m + n``, matching the direct helper.

Partitions use the same representation as
:mod:`strengthening.metrics.cluster` (a mapping ``item -> cluster_id``, or an
iterable of clusters); the converter there is reused rather than duplicated.

Pure computation; no network access anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from .cluster import assignment_to_clusters, to_assignment

__all__ = [
    "BridgeAmplification",
    "BridgeEvent",
    "BridgeReport",
    "bridge_amplification_from_sizes",
    "bridge_amplification_report",
    "detect_bridge_events",
]


@dataclass(frozen=True)
class BridgeAmplification:
    """Amplification arithmetic for a bridge between clusters of size m and n."""

    size_gold_cluster_1: int
    size_gold_cluster_2: int
    number_of_false_implied_equivalences_created: int
    resulting_component_size: int

    def to_dict(self) -> dict[str, int]:
        return {
            "size_gold_cluster_1": self.size_gold_cluster_1,
            "size_gold_cluster_2": self.size_gold_cluster_2,
            "number_of_false_implied_equivalences_created": (
                self.number_of_false_implied_equivalences_created
            ),
            "resulting_component_size": self.resulting_component_size,
        }


def bridge_amplification_from_sizes(m: int, n: int) -> BridgeAmplification:
    """Direct helper: one false bridge between clusters of size ``m`` and ``n``.

    Returns ``m * n`` false implied equivalences and a resulting component
    of size ``m + n``. Sizes must be non-negative ints.
    """
    for name, value in (("m", m), ("n", n)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} must be a non-negative int, got {value!r}")
    return BridgeAmplification(
        size_gold_cluster_1=m,
        size_gold_cluster_2=n,
        number_of_false_implied_equivalences_created=m * n,
        resulting_component_size=m + n,
    )


@dataclass(frozen=True)
class BridgeEvent:
    """One pair of gold clusters bridged inside a single predicted component."""

    predicted_component_id: Any
    gold_cluster_id_1: Any
    gold_cluster_id_2: Any
    size_gold_cluster_1: int
    size_gold_cluster_2: int
    number_of_false_implied_equivalences_created: int
    resulting_component_size: int

    @property
    def gold_cluster_ids(self) -> tuple[Any, Any]:
        return (self.gold_cluster_id_1, self.gold_cluster_id_2)

    def to_dict(self) -> dict[str, object]:
        return {
            "predicted_component_id": self.predicted_component_id,
            "gold_cluster_id_1": self.gold_cluster_id_1,
            "gold_cluster_id_2": self.gold_cluster_id_2,
            "size_gold_cluster_1": self.size_gold_cluster_1,
            "size_gold_cluster_2": self.size_gold_cluster_2,
            "number_of_false_implied_equivalences_created": (
                self.number_of_false_implied_equivalences_created
            ),
            "resulting_component_size": self.resulting_component_size,
        }


def _sorted_ids(ids: Any) -> list[Any]:
    ids = list(ids)
    try:
        return sorted(ids)
    except TypeError:
        return sorted(ids, key=repr)


def detect_bridge_events(gold: Any, predicted: Any) -> list[BridgeEvent]:
    """Every bridge event in a predicted partition, relative to a gold partition.

    A predicted component spanning ``k > 1`` gold clusters yields
    ``k * (k - 1) / 2`` events, one per unordered pair of the gold cluster
    ids it spans, ordered deterministically by (component id, gold id pair).

    Items must be the same in both partitions (enforced here, matching
    :mod:`strengthening.metrics.cluster`).
    """
    gold_assignment = to_assignment(gold)
    pred_assignment = to_assignment(predicted)
    if set(gold_assignment) != set(pred_assignment):
        raise ValueError(
            "gold and predicted partitions must cover the same items"
        )
    pred_clusters = assignment_to_clusters(pred_assignment)

    events: list[BridgeEvent] = []
    for component_id in _sorted_ids(pred_clusters):
        members = pred_clusters[component_id]
        # Members of each gold cluster that are actually inside this component.
        inside: dict[Any, int] = {}
        for item in members:
            gold_id = gold_assignment[item]
            inside[gold_id] = inside.get(gold_id, 0) + 1
        if len(inside) < 2:
            continue
        component_size = len(members)
        for gold_id_1, gold_id_2 in combinations(_sorted_ids(inside), 2):
            size_1 = inside[gold_id_1]
            size_2 = inside[gold_id_2]
            events.append(
                BridgeEvent(
                    predicted_component_id=component_id,
                    gold_cluster_id_1=gold_id_1,
                    gold_cluster_id_2=gold_id_2,
                    size_gold_cluster_1=size_1,
                    size_gold_cluster_2=size_2,
                    number_of_false_implied_equivalences_created=size_1 * size_2,
                    resulting_component_size=component_size,
                )
            )
    return events


@dataclass(frozen=True)
class BridgeReport:
    """Aggregate view over all bridge events.

    ``total_false_implied_equivalences_created`` is the sum over events. For
    a component whose gold parts have sizes ``s_1..s_k`` that sum equals
    ``sum_{i<j} s_i * s_j`` -- exactly the pairs the component asserts as
    equivalent that gold does not.
    """

    n_bridge_events: int
    n_bridged_components: int
    total_false_implied_equivalences_created: int
    largest_resulting_component_size: int
    events: tuple[BridgeEvent, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "n_bridge_events": self.n_bridge_events,
            "n_bridged_components": self.n_bridged_components,
            "total_false_implied_equivalences_created": (
                self.total_false_implied_equivalences_created
            ),
            "largest_resulting_component_size": self.largest_resulting_component_size,
            "events": [event.to_dict() for event in self.events],
        }


def bridge_amplification_report(gold: Any, predicted: Any) -> BridgeReport:
    """Summarise every bridge event between a gold and a predicted partition."""
    events = detect_bridge_events(gold, predicted)
    components = {event.predicted_component_id for event in events}
    return BridgeReport(
        n_bridge_events=len(events),
        n_bridged_components=len(components),
        total_false_implied_equivalences_created=sum(
            event.number_of_false_implied_equivalences_created for event in events
        ),
        largest_resulting_component_size=(
            max(event.resulting_component_size for event in events) if events else 0
        ),
        events=tuple(events),
    )
