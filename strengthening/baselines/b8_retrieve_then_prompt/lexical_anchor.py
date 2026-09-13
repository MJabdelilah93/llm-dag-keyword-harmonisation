"""B8 stage 1 -- exact/normalised lexical anchoring.

Finds the trivial exact matches for a seed keyword within a candidate keyword
universe, using ONLY the legacy-exact normalisation chain (see
:mod:`.normalisation`). Two strings anchor to each other when their normalised
forms are byte-identical; no fuzzy distance, no punctuation folding, no
acronym expansion.

Output order is the order of appearance in the supplied universe, so the stage
is deterministic for a given input order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable, Sequence

from .normalisation import legacy_normalise

#: Route tag recorded on candidates proposed by this stage.
ROUTE_LEXICAL: Final[str] = "lexical_exact"


@dataclass(frozen=True)
class LexicalAnchorResult:
    """Candidates that anchor to ``seed`` by normalised string equality."""

    seed: str
    normalised_seed: str
    candidates: tuple[str, ...]
    route: str = ROUTE_LEXICAL

    def __len__(self) -> int:
        return len(self.candidates)


def build_normalised_index(universe: Iterable[str]) -> dict[str, list[str]]:
    """Group the universe by normalised form, preserving insertion order.

    Duplicate surface strings are kept (they are distinct universe entries);
    the caller decides whether to de-duplicate.
    """

    index: dict[str, list[str]] = {}
    for item in universe:
        index.setdefault(legacy_normalise(item), []).append(item)
    return index


def lexical_anchor(
    seed: str,
    universe: Sequence[str],
    *,
    include_self: bool = False,
) -> LexicalAnchorResult:
    """Return universe entries whose normalised form equals the seed's.

    Parameters
    ----------
    seed:
        The seed keyword.
    universe:
        The candidate keyword universe, in a stable order.
    include_self:
        When ``False`` (the default) an entry whose surface string is exactly
        equal to ``seed`` is skipped, so a seed does not anchor to itself.
        Entries that merely normalise to the same form (e.g. ``"Circular
        Economy"`` for the seed ``"circular economy"``) ARE returned -- those
        are the interesting trivial matches.
    """

    normalised_seed = legacy_normalise(seed)
    matches: list[str] = []
    for item in universe:
        if not include_self and item == seed:
            continue
        if legacy_normalise(item) == normalised_seed:
            matches.append(item)

    return LexicalAnchorResult(
        seed=seed,
        normalised_seed=normalised_seed,
        candidates=tuple(matches),
    )


def lexical_anchor_pairs(
    universe: Sequence[str],
) -> list[tuple[str, str]]:
    """Return every unordered pair in ``universe`` that anchors lexically.

    Pairs are emitted with the earlier universe entry first and the whole list
    is ordered by first-appearance, so the result is deterministic.
    """

    index = build_normalised_index(universe)
    pairs: list[tuple[str, str]] = []
    for members in index.values():
        for i, left in enumerate(members):
            for right in members[i + 1 :]:
                pairs.append((left, right))
    return pairs
