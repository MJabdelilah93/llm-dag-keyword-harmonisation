"""Cluster-level metrics: B-cubed, pairwise, exact recovery, merge diagnostics.

Partition representation
------------------------
The canonical representation used by EVERY function in this module is an
ASSIGNMENT: a mapping ``item -> cluster_id``. Both items and cluster ids
must be hashable::

    {"a": "G1", "b": "G1", "c": "G1", "d": "G2", "e": "G2"}

For convenience, every public function also accepts a partition given as an
iterable of clusters (sets / lists / tuples of items), which is converted by
:func:`to_assignment` with cluster ids ``0, 1, 2, ...`` in iteration order::

    [{"a", "b", "c"}, {"d", "e"}]

A ``Mapping`` argument is ALWAYS read as ``item -> cluster_id``. To go the
other way (``cluster_id -> members``) use :func:`clusters_to_assignment`, and
to invert an assignment use :func:`assignment_to_clusters`.

Because a partition is by construction an equivalence relation, predicted
components are already transitively closed; the pairwise metrics take
"in the same component" as the relation directly.

Gold and predicted partitions must cover exactly the same item set; a
mismatch raises ``ValueError`` rather than silently scoring a subset.

Zero-denominator convention: ``0.0`` (see the package docstring).
Pure computation; no network access anywhere in this module.
"""

from __future__ import annotations

import statistics
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Any

__all__ = [
    "Assignment",
    "ClusterScores",
    "OvermergeDiagnostics",
    "SizeSummary",
    "UndermergeDiagnostics",
    "assignment_to_clusters",
    "bcubed_scores",
    "clusters_to_assignment",
    "component_size_summary",
    "exact_cluster_recovery_rate",
    "overmerge_diagnostics",
    "pairwise_scores",
    "to_assignment",
    "undermerge_diagnostics",
]

Assignment = Mapping[Hashable, Hashable]


# --------------------------------------------------------------------------
# Representation helpers
# --------------------------------------------------------------------------
def to_assignment(partition: Any) -> dict[Hashable, Hashable]:
    """Coerce a partition to the canonical ``item -> cluster_id`` dict.

    A ``Mapping`` is copied as-is (it is read as item -> cluster_id). Any
    other iterable is read as an iterable of clusters and gets integer
    cluster ids in iteration order.

    Raises ``ValueError`` if an item appears in more than one cluster.
    """
    if isinstance(partition, Mapping):
        return dict(partition)
    assignment: dict[Hashable, Hashable] = {}
    for cluster_id, cluster in enumerate(partition):
        for item in cluster:
            if item in assignment:
                raise ValueError(
                    f"item {item!r} appears in more than one cluster; "
                    "a partition must assign each item exactly once"
                )
            assignment[item] = cluster_id
    return assignment


def clusters_to_assignment(clusters: Any) -> dict[Hashable, Hashable]:
    """Convert ``cluster_id -> members`` (or an iterable of clusters) to an assignment.

    Use this when your data is keyed by cluster rather than by item; passing
    a ``cluster_id -> members`` mapping to :func:`to_assignment` would be
    misread, since that function treats a Mapping as item -> cluster_id.
    """
    assignment: dict[Hashable, Hashable] = {}
    if isinstance(clusters, Mapping):
        pairs = clusters.items()
    else:
        pairs = ((index, members) for index, members in enumerate(clusters))
    for cluster_id, members in pairs:
        for item in members:
            if item in assignment:
                raise ValueError(
                    f"item {item!r} appears in more than one cluster; "
                    "a partition must assign each item exactly once"
                )
            assignment[item] = cluster_id
    return assignment


def assignment_to_clusters(partition: Any) -> dict[Hashable, set[Hashable]]:
    """Invert an assignment into ``cluster_id -> set(members)``."""
    assignment = to_assignment(partition)
    clusters: dict[Hashable, set[Hashable]] = {}
    for item, cluster_id in assignment.items():
        clusters.setdefault(cluster_id, set()).add(item)
    return clusters


def _aligned(gold: Any, predicted: Any) -> tuple[
    dict[Hashable, Hashable],
    dict[Hashable, Hashable],
    dict[Hashable, set[Hashable]],
    dict[Hashable, set[Hashable]],
]:
    gold_assignment = to_assignment(gold)
    pred_assignment = to_assignment(predicted)
    gold_items = set(gold_assignment)
    pred_items = set(pred_assignment)
    if gold_items != pred_items:
        only_gold = sorted(map(repr, gold_items - pred_items))[:5]
        only_pred = sorted(map(repr, pred_items - gold_items))[:5]
        raise ValueError(
            "gold and predicted partitions must cover the same items; "
            f"only in gold: {only_gold}, only in predicted: {only_pred}"
        )
    return (
        gold_assignment,
        pred_assignment,
        assignment_to_clusters(gold_assignment),
        assignment_to_clusters(pred_assignment),
    )


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator) / denominator if denominator > 0 else 0.0


def _harmonic(precision: float, recall: float) -> float:
    total = precision + recall
    return (2.0 * precision * recall / total) if total > 0 else 0.0


# --------------------------------------------------------------------------
# Score container
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ClusterScores:
    """Precision / recall / F1 for one clustering-evaluation family."""

    kind: str
    precision: float
    recall: float
    f1: float
    n_items: int

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "kind": self.kind,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "n_items": self.n_items,
        }


# --------------------------------------------------------------------------
# B-cubed
# --------------------------------------------------------------------------
def bcubed_scores(gold: Any, predicted: Any) -> ClusterScores:
    """Standard B-cubed (B^3) precision / recall / F1.

    Per item ``i`` with predicted cluster ``P(i)`` and gold cluster ``G(i)``::

        precision_i = |P(i) & G(i)| / |P(i)|
        recall_i    = |P(i) & G(i)| / |G(i)|

    B^3 precision and recall are the means of those over all items, and B^3
    F1 is the harmonic mean of the two AGGREGATES (not the mean of per-item
    F1s). Empty input scores ``0.0`` across the board.
    """
    gold_assignment, pred_assignment, gold_clusters, pred_clusters = _aligned(
        gold, predicted
    )
    items = list(pred_assignment)
    n = len(items)
    if n == 0:
        return ClusterScores(kind="bcubed", precision=0.0, recall=0.0, f1=0.0, n_items=0)

    precision_sum = 0.0
    recall_sum = 0.0
    for item in items:
        pred_cluster = pred_clusters[pred_assignment[item]]
        gold_cluster = gold_clusters[gold_assignment[item]]
        shared = len(pred_cluster & gold_cluster)
        precision_sum += shared / len(pred_cluster)
        recall_sum += shared / len(gold_cluster)

    precision = precision_sum / n
    recall = recall_sum / n
    return ClusterScores(
        kind="bcubed",
        precision=precision,
        recall=recall,
        f1=_harmonic(precision, recall),
        n_items=n,
    )


# --------------------------------------------------------------------------
# Pairwise (after transitive closure)
# --------------------------------------------------------------------------
def _same_cluster_pairs(
    clusters: Mapping[Hashable, set[Hashable]]
) -> set[tuple[Any, Any]]:
    """All unordered within-cluster pairs, normalised to sorted 2-tuples."""
    pairs: set[tuple[Any, Any]] = set()
    for members in clusters.values():
        if len(members) < 2:
            continue
        try:
            ordered = sorted(members)
        except TypeError:
            ordered = sorted(members, key=repr)
        pairs.update(combinations(ordered, 2))
    return pairs


def pairwise_scores(gold: Any, predicted: Any) -> ClusterScores:
    """Pairwise precision / recall / F1 over same-cluster pairs.

    Clusters are equivalence classes, so they are already transitively
    closed: the relation scored here is "these two items ended up in the
    same component". Let ``P`` be the set of predicted same-cluster pairs
    and ``G`` the gold same-cluster pairs::

        precision = |P & G| / |P|
        recall    = |P & G| / |G|

    Both return ``0.0`` on an empty denominator (e.g. an all-singleton
    predicted partition has no predicted pairs).
    """
    _, pred_assignment, gold_clusters, pred_clusters = _aligned(gold, predicted)
    gold_pairs = _same_cluster_pairs(gold_clusters)
    pred_pairs = _same_cluster_pairs(pred_clusters)
    shared = len(gold_pairs & pred_pairs)
    precision = _safe_ratio(shared, len(pred_pairs))
    recall = _safe_ratio(shared, len(gold_pairs))
    return ClusterScores(
        kind="pairwise",
        precision=precision,
        recall=recall,
        f1=_harmonic(precision, recall),
        n_items=len(pred_assignment),
    )


# --------------------------------------------------------------------------
# Exact recovery
# --------------------------------------------------------------------------
def exact_cluster_recovery_rate(gold: Any, predicted: Any) -> float:
    """Fraction of gold clusters reproduced EXACTLY as a predicted cluster.

    A gold cluster counts as recovered only when some predicted cluster has
    exactly the same member set -- neither a superset (overmerge) nor a
    subset (undermerge). Returns ``0.0`` when there are no gold clusters.
    """
    _, _, gold_clusters, pred_clusters = _aligned(gold, predicted)
    if not gold_clusters:
        return 0.0
    predicted_sets = {frozenset(members) for members in pred_clusters.values()}
    recovered = sum(
        1 for members in gold_clusters.values() if frozenset(members) in predicted_sets
    )
    return recovered / len(gold_clusters)


# --------------------------------------------------------------------------
# Overmerge / undermerge diagnostics
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class OvermergeDiagnostics:
    """Gold clusters that were incorrectly merged together.

    A predicted cluster that touches more than one gold cluster is an
    overmerge; every unordered pair of the gold cluster ids it spans is
    recorded in ``gold_cluster_id_pairs``.
    """

    n_overmerged_predicted_clusters: int
    n_gold_cluster_pairs_merged: int
    n_gold_clusters_involved: int
    gold_cluster_id_pairs: tuple[tuple[Any, Any], ...]
    predicted_cluster_ids: tuple[Any, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "n_overmerged_predicted_clusters": self.n_overmerged_predicted_clusters,
            "n_gold_cluster_pairs_merged": self.n_gold_cluster_pairs_merged,
            "n_gold_clusters_involved": self.n_gold_clusters_involved,
            "gold_cluster_id_pairs": [list(p) for p in self.gold_cluster_id_pairs],
            "predicted_cluster_ids": list(self.predicted_cluster_ids),
        }


def _sorted_ids(ids: Iterable[Any]) -> list[Any]:
    ids = list(ids)
    try:
        return sorted(ids)
    except TypeError:
        return sorted(ids, key=repr)


def overmerge_diagnostics(gold: Any, predicted: Any) -> OvermergeDiagnostics:
    """Counts and offending gold-cluster-id pairs for incorrect merges."""
    gold_assignment, _, _, pred_clusters = _aligned(gold, predicted)
    offending: list[tuple[Any, Any]] = []
    involved: set[Any] = set()
    offending_predicted: list[Any] = []
    for pred_id in _sorted_ids(pred_clusters):
        spanned = _sorted_ids({gold_assignment[item] for item in pred_clusters[pred_id]})
        if len(spanned) > 1:
            offending_predicted.append(pred_id)
            involved.update(spanned)
            offending.extend(combinations(spanned, 2))
    return OvermergeDiagnostics(
        n_overmerged_predicted_clusters=len(offending_predicted),
        n_gold_cluster_pairs_merged=len(offending),
        n_gold_clusters_involved=len(involved),
        gold_cluster_id_pairs=tuple(offending),
        predicted_cluster_ids=tuple(offending_predicted),
    )


@dataclass(frozen=True)
class UndermergeDiagnostics:
    """Gold clusters that were incorrectly split across predicted clusters.

    ``n_extra_fragments`` is ``sum(k_g - 1)`` over split gold clusters, where
    ``k_g`` is the number of predicted clusters gold cluster ``g`` spans --
    i.e. the number of surplus pieces beyond the single correct one.
    """

    n_split_gold_clusters: int
    n_extra_fragments: int
    gold_cluster_ids: tuple[Any, ...]
    fragments_by_gold_cluster: dict[Any, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "n_split_gold_clusters": self.n_split_gold_clusters,
            "n_extra_fragments": self.n_extra_fragments,
            "gold_cluster_ids": list(self.gold_cluster_ids),
            "fragments_by_gold_cluster": dict(self.fragments_by_gold_cluster),
        }


def undermerge_diagnostics(gold: Any, predicted: Any) -> UndermergeDiagnostics:
    """Counts and offending gold-cluster ids for incorrect splits."""
    _, pred_assignment, gold_clusters, _ = _aligned(gold, predicted)
    offending: list[Any] = []
    fragments: dict[Any, int] = {}
    extra = 0
    for gold_id in _sorted_ids(gold_clusters):
        spanned = {pred_assignment[item] for item in gold_clusters[gold_id]}
        if len(spanned) > 1:
            offending.append(gold_id)
            fragments[gold_id] = len(spanned)
            extra += len(spanned) - 1
    return UndermergeDiagnostics(
        n_split_gold_clusters=len(offending),
        n_extra_fragments=extra,
        gold_cluster_ids=tuple(offending),
        fragments_by_gold_cluster=fragments,
    )


# --------------------------------------------------------------------------
# Component size distribution
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SizeSummary:
    """Summary of a partition's component-size distribution.

    ``histogram`` maps component size -> number of components of that size,
    with keys in ascending size order. An empty partition gives zeroed
    scalars, ``None`` for min/max and an empty histogram.
    """

    n_components: int
    n_items: int
    min_size: int | None
    max_size: int | None
    mean_size: float
    median_size: float
    histogram: dict[int, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "n_components": self.n_components,
            "n_items": self.n_items,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "mean_size": self.mean_size,
            "median_size": self.median_size,
            "histogram": dict(self.histogram),
        }


def component_size_summary(partition: Any) -> SizeSummary:
    """Count / min / max / mean / median / histogram of component sizes."""
    clusters = assignment_to_clusters(partition)
    sizes = sorted(len(members) for members in clusters.values())
    if not sizes:
        return SizeSummary(
            n_components=0,
            n_items=0,
            min_size=None,
            max_size=None,
            mean_size=0.0,
            median_size=0.0,
            histogram={},
        )
    histogram: dict[int, int] = {}
    for size in sizes:
        histogram[size] = histogram.get(size, 0) + 1
    return SizeSummary(
        n_components=len(sizes),
        n_items=sum(sizes),
        min_size=sizes[0],
        max_size=sizes[-1],
        mean_size=sum(sizes) / len(sizes),
        median_size=float(statistics.median(sizes)),
        histogram={size: histogram[size] for size in sorted(histogram)},
    )
