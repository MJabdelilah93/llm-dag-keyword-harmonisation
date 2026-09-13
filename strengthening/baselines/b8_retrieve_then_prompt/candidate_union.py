"""B8 stage 3 -- union and de-duplicate candidates, preserving provenance.

A candidate proposed by both the lexical and the dense route appears ONCE, but
carries BOTH route tags. Provenance is the point of this stage: knowing which
route surfaced a candidate is what lets a later analysis attribute recall to a
route, so it must survive de-duplication rather than being collapsed away.

Ordering is deterministic: lexical candidates first (in universe order), then
dense candidates in rank order, with the first occurrence fixing a candidate's
position.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .dense_retrieval import ROUTE_DENSE, DenseRetrievalResult
from .lexical_anchor import ROUTE_LEXICAL, LexicalAnchorResult


@dataclass(frozen=True)
class Candidate:
    """One retrieved candidate for one seed, with its route provenance."""

    seed: str
    candidate: str
    #: Every route that proposed this candidate, in the order they were merged.
    routes: tuple[str, ...]
    #: Cosine similarity if the dense route proposed it, else ``None``.
    similarity: float | None = None
    #: Rank within the dense route's top-k, if applicable.
    dense_rank: int | None = None

    @property
    def multi_route(self) -> bool:
        return len(self.routes) > 1

    def as_dict(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "candidate": self.candidate,
            "routes": list(self.routes),
            "similarity": self.similarity,
            "dense_rank": self.dense_rank,
        }


@dataclass
class CandidateSet:
    """The de-duplicated candidate set for one seed."""

    seed: str
    candidates: list[Candidate] = field(default_factory=list)
    #: ``False`` when the dense route could not run for this seed.
    dense_available: bool = True
    dense_unavailable_reason: str | None = None

    def __len__(self) -> int:
        return len(self.candidates)

    def __iter__(self):
        return iter(self.candidates)

    @property
    def candidate_strings(self) -> tuple[str, ...]:
        return tuple(c.candidate for c in self.candidates)

    def by_route(self, route: str) -> list[Candidate]:
        return [c for c in self.candidates if route in c.routes]

    @property
    def multi_route_candidates(self) -> list[Candidate]:
        return [c for c in self.candidates if c.multi_route]


def union_candidates(
    lexical: LexicalAnchorResult,
    dense: DenseRetrievalResult | None = None,
) -> CandidateSet:
    """Merge the lexical and dense candidate lists for one seed.

    The seed of both inputs must agree. A candidate found by both routes ends
    up with ``routes == ("lexical_exact", "dense_embedding")`` and keeps the
    dense similarity/rank.
    """

    if dense is not None and dense.seed != lexical.seed:
        raise ValueError(
            f"seed mismatch between routes: {lexical.seed!r} vs {dense.seed!r}"
        )

    seed = lexical.seed
    order: list[str] = []
    merged: dict[str, dict[str, object]] = {}

    for candidate in lexical.candidates:
        if candidate not in merged:
            order.append(candidate)
            merged[candidate] = {
                "routes": [ROUTE_LEXICAL],
                "similarity": None,
                "dense_rank": None,
            }
        elif ROUTE_LEXICAL not in merged[candidate]["routes"]:
            merged[candidate]["routes"].append(ROUTE_LEXICAL)

    if dense is not None:
        for neighbour in dense.neighbours:
            candidate = neighbour.candidate
            if candidate not in merged:
                order.append(candidate)
                merged[candidate] = {
                    "routes": [ROUTE_DENSE],
                    "similarity": neighbour.similarity,
                    "dense_rank": neighbour.rank,
                }
            else:
                if ROUTE_DENSE not in merged[candidate]["routes"]:
                    merged[candidate]["routes"].append(ROUTE_DENSE)
                merged[candidate]["similarity"] = neighbour.similarity
                merged[candidate]["dense_rank"] = neighbour.rank

    candidates = [
        Candidate(
            seed=seed,
            candidate=name,
            routes=tuple(merged[name]["routes"]),  # type: ignore[arg-type]
            similarity=merged[name]["similarity"],  # type: ignore[arg-type]
            dense_rank=merged[name]["dense_rank"],  # type: ignore[arg-type]
        )
        for name in order
    ]

    return CandidateSet(
        seed=seed,
        candidates=candidates,
        dense_available=True if dense is None else dense.available,
        dense_unavailable_reason=None if dense is None else dense.unavailable_reason,
    )


def dedupe_pairs(
    candidate_sets: Iterable[CandidateSet],
) -> list[tuple[str, str]]:
    """Collapse per-seed candidate sets into unique unordered pairs.

    A pair ``(a, b)`` and its mirror ``(b, a)`` are the same comparison, so
    only one is kept. The retained orientation is the one first encountered,
    which makes the output deterministic for a given input order. Self-pairs
    are dropped.
    """

    seen: set[frozenset[str]] = set()
    pairs: list[tuple[str, str]] = []
    for candidate_set in candidate_sets:
        for candidate in candidate_set.candidates:
            if candidate.seed == candidate.candidate:
                continue
            key = frozenset((candidate.seed, candidate.candidate))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((candidate.seed, candidate.candidate))
    return pairs


def candidate_universe_size(universe: Sequence[str]) -> int:
    """Number of distinct surface strings in the universe."""

    return len(set(universe))
