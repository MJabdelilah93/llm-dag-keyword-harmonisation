"""B8 stage 5 -- connected components over accepted match edges.

Only edges accepted as ``same_as`` reach this stage (see
:mod:`.relation_classification`), so the components are the transitive closure
of the accepted equivalences -- which is exactly the documented M7 clustering
mechanism (``clustering.primary_mechanism`` in the protocol).

A small union-find is implemented here rather than delegating to networkx.
The reason is determinism: this implementation's output order is a pure
function of the node order and the edge order given to it, with no dependence
on set/dict iteration of an external library's internal structures. Union by
size with path compression; ties in union-by-size are broken toward the root
that was inserted first, so the same input always yields the same forest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


class UnionFind:
    """Deterministic union-find over hashable, insertion-ordered items."""

    def __init__(self, items: Iterable[str] = ()) -> None:
        self._parent: dict[str, str] = {}
        self._size: dict[str, int] = {}
        self._order: dict[str, int] = {}
        for item in items:
            self.add(item)

    def add(self, item: str) -> None:
        if item not in self._parent:
            self._parent[item] = item
            self._size[item] = 1
            self._order[item] = len(self._order)

    def find(self, item: str) -> str:
        self.add(item)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        # Path compression.
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, left: str, right: str) -> bool:
        """Merge two items' components. Returns ``True`` if they were distinct."""

        root_left, root_right = self.find(left), self.find(right)
        if root_left == root_right:
            return False

        # Union by size; deterministic tie-break on insertion order.
        if (self._size[root_left], -self._order[root_left]) < (
            self._size[root_right],
            -self._order[root_right],
        ):
            root_left, root_right = root_right, root_left

        self._parent[root_right] = root_left
        self._size[root_left] += self._size[root_right]
        return True

    def components(self) -> list[list[str]]:
        """Return components as lists, both inner and outer in insertion order."""

        groups: dict[str, list[str]] = {}
        for item in self._parent:
            groups.setdefault(self.find(item), []).append(item)
        # Order components by the insertion index of their earliest member, so
        # the output does not depend on which node happened to become root.
        ordered = sorted(
            groups.values(), key=lambda members: min(self._order[m] for m in members)
        )
        return ordered


@dataclass(frozen=True)
class ClusterOutput:
    """The clustering produced by B8 for one run."""

    #: Components as a sorted tuple of sorted tuples -- a canonical form that
    #: is identical for any input order producing the same partition.
    clusters: tuple[tuple[str, ...], ...]
    #: Mapping from item to a stable integer cluster id (0-based, assigned in
    #: canonical cluster order).
    assignments: dict[str, int] = field(default_factory=dict)
    n_items: int = 0
    n_clusters: int = 0
    n_singletons: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "clusters": [list(c) for c in self.clusters],
            "assignments": dict(self.assignments),
            "n_items": self.n_items,
            "n_clusters": self.n_clusters,
            "n_singletons": self.n_singletons,
        }


def connected_components(
    edges: Sequence[tuple[str, str]],
    *,
    nodes: Iterable[str] = (),
) -> ClusterOutput:
    """Build connected components from an accepted-match edge list.

    Parameters
    ----------
    edges:
        Accepted ``same_as`` edges. Order does not affect the resulting
        partition, and the canonical output form makes that visible.
    nodes:
        Extra nodes to include, so that items with no accepted edge still
        appear as singleton clusters. Pass the full keyword universe to get a
        complete partition.
    """

    union_find = UnionFind(nodes)
    for left, right in edges:
        union_find.add(left)
        union_find.add(right)
    for left, right in edges:
        union_find.union(left, right)

    raw = union_find.components()
    canonical = tuple(sorted(tuple(sorted(members)) for members in raw))

    assignments = {
        item: index for index, members in enumerate(canonical) for item in members
    }
    return ClusterOutput(
        clusters=canonical,
        assignments=assignments,
        n_items=len(assignments),
        n_clusters=len(canonical),
        n_singletons=sum(1 for members in canonical if len(members) == 1),
    )


def component_size_distribution(output: ClusterOutput) -> dict[int, int]:
    """Histogram mapping component size -> number of components of that size."""

    histogram: dict[int, int] = {}
    for members in output.clusters:
        histogram[len(members)] = histogram.get(len(members), 0) + 1
    return dict(sorted(histogram.items()))
