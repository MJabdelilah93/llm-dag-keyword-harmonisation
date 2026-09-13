"""Candidate-generation (retrieval) audit metrics.

WHAT CANNOT YET BE COMPUTED
---------------------------
Two of these metrics -- :func:`pair_completeness` and :func:`pairs_quality`
-- are GOLD-DEPENDENT. They cannot be computed until gold retrieval
annotations exist (a human-adjudicated set of the pairs that *should* have
been generated for each seed). Until then, every gold-dependent function in
this module returns ``None`` when ``gold=None``.

``None`` here means "not estimable from the data available", and is
deliberately distinct from ``0.0``, which would mean "estimated, and the
answer is zero". Nothing in this module ever substitutes a placeholder
number for a missing annotation. This is the opposite convention to
:mod:`strengthening.metrics.binary` / ``three_way`` / ``selective`` /
``cluster`` (which return ``0.0`` for genuine zero denominators), and the
difference is intentional.

Metric definitions
------------------
``pair_completeness``
    |gold-relevant pairs also present among the generated candidates| /
    |gold-relevant pairs|. The recall of candidate generation. Requires gold.

``candidate_count``
    Number of distinct candidate pairs generated.

``exhaustive_comparisons``
    ``n * (n - 1) / 2`` -- the all-pairs baseline for ``n`` items.

``reduction_ratio``
    ``1 - candidate_count / exhaustive_comparisons``. How much of the
    all-pairs workload was avoided. Gold-independent.

``pairs_quality``
    PLACEHOLDER, gold-dependent. A precision-like quantity: the share of
    generated candidates that are gold-relevant (correct / accepted), over
    ``candidate_count``. Named a placeholder because the final definition of
    an "accepted" candidate is not settled; the arithmetic implemented here
    is the simple precision reading and should be revisited once the gold
    retrieval annotations are designed.

``latency`` / ``cost``
    Pass-through operational fields. Stored verbatim on
    :class:`RetrievalAudit`; nothing is computed from them.

Pair representation
-------------------
A pair is any 2-element iterable of hashable item ids. Pairs are unordered:
they are normalised by :func:`normalise_pair` to a sorted 2-tuple, so
``("a", "b")`` and ``("b", "a")`` are the same pair. Self-pairs are rejected.

Pure computation; no network access anywhere in this module.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "PairLike",
    "RetrievalAudit",
    "candidate_count",
    "exhaustive_comparisons",
    "normalise_pair",
    "normalise_pairs",
    "pair_completeness",
    "pairs_quality",
    "reduction_ratio",
    "retrieval_audit",
]

PairLike = Iterable[Any]


def normalise_pair(pair: PairLike) -> tuple[Any, Any]:
    """Normalise an unordered pair to a deterministic sorted 2-tuple.

    Falls back to sorting by ``repr`` when the ids are not mutually
    comparable, so mixed-type ids still normalise deterministically.
    Raises ``ValueError`` for a self-pair or a non-2-element input.
    """
    items = list(pair)
    if len(items) != 2:
        raise ValueError(f"a pair must have exactly 2 elements, got {items!r}")
    first, second = items
    if first == second:
        raise ValueError(f"self-pairs are not valid candidate pairs: {items!r}")
    try:
        return (first, second) if first <= second else (second, first)
    except TypeError:
        return tuple(sorted(items, key=repr))  # type: ignore[return-value]


def normalise_pairs(pairs: Iterable[PairLike]) -> set[tuple[Any, Any]]:
    """Normalise an iterable of pairs into a set of sorted 2-tuples (deduped)."""
    return {normalise_pair(pair) for pair in pairs}


def pair_completeness(
    candidates: Iterable[PairLike], gold: Iterable[PairLike] | None = None
) -> float | None:
    """Recall of candidate generation against gold-relevant pairs.

    ``|gold & candidates| / |gold|``.

    Returns ``None`` -- never a fabricated number -- when ``gold`` is
    ``None`` (the gold retrieval annotations do not exist yet) or when the
    gold set is empty (nothing to be complete with respect to).
    """
    if gold is None:
        return None
    gold_pairs = normalise_pairs(gold)
    if not gold_pairs:
        return None
    candidate_pairs = normalise_pairs(candidates)
    return len(gold_pairs & candidate_pairs) / len(gold_pairs)


def candidate_count(candidates: Iterable[PairLike]) -> int:
    """Number of DISTINCT candidate pairs generated (duplicates collapse)."""
    return len(normalise_pairs(candidates))


def exhaustive_comparisons(n_items: int) -> int:
    """All-pairs baseline ``n * (n - 1) / 2``. ``0`` for ``n < 2``."""
    if not isinstance(n_items, int) or isinstance(n_items, bool) or n_items < 0:
        raise ValueError(f"n_items must be a non-negative int, got {n_items!r}")
    if n_items < 2:
        return 0
    return n_items * (n_items - 1) // 2


def reduction_ratio(n_candidates: int, n_items: int) -> float | None:
    """``1 - candidate_count / exhaustive_comparisons``.

    Gold-independent. Returns ``None`` when the all-pairs baseline is zero
    (fewer than 2 items), because the ratio is then undefined rather than
    zero.
    """
    if not isinstance(n_candidates, int) or isinstance(n_candidates, bool) or n_candidates < 0:
        raise ValueError(f"n_candidates must be a non-negative int, got {n_candidates!r}")
    total = exhaustive_comparisons(n_items)
    if total == 0:
        return None
    return 1.0 - (float(n_candidates) / total)


def pairs_quality(
    candidates: Iterable[PairLike], gold: Iterable[PairLike] | None = None
) -> float | None:
    """PLACEHOLDER precision-like quality of the generated candidates.

    ``|candidates & gold| / candidate_count`` -- the share of generated
    candidates that are gold-relevant ("correct / accepted candidates over
    candidate_count").

    PLACEHOLDER: the operational definition of an *accepted* candidate is
    not settled, and this simple precision reading is expected to be
    replaced once the gold retrieval annotations are designed.

    Returns ``None`` -- never a fabricated number -- when ``gold`` is
    ``None`` (annotations do not exist yet) or when no candidates were
    generated (empty denominator).
    """
    if gold is None:
        return None
    candidate_pairs = normalise_pairs(candidates)
    if not candidate_pairs:
        return None
    gold_pairs = normalise_pairs(gold)
    return len(candidate_pairs & gold_pairs) / len(candidate_pairs)


@dataclass(frozen=True)
class RetrievalAudit:
    """Bundled retrieval-audit result.

    ``gold_available`` records whether gold retrieval annotations were
    supplied at all. When it is False, ``pair_completeness`` and
    ``pairs_quality`` are ``None`` by construction -- not zero, and not a
    placeholder value.

    ``latency_seconds`` and ``cost_usd`` are pure pass-through operational
    fields; no arithmetic is performed on them.
    """

    n_items: int
    candidate_count: int
    exhaustive_comparisons: int
    reduction_ratio: float | None
    pair_completeness: float | None
    pairs_quality: float | None
    gold_available: bool
    latency_seconds: float | None = None
    cost_usd: float | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "n_items": self.n_items,
            "candidate_count": self.candidate_count,
            "exhaustive_comparisons": self.exhaustive_comparisons,
            "reduction_ratio": self.reduction_ratio,
            "pair_completeness": self.pair_completeness,
            "pairs_quality": self.pairs_quality,
            "gold_available": self.gold_available,
            "latency_seconds": self.latency_seconds,
            "cost_usd": self.cost_usd,
            "notes": self.notes,
        }


def retrieval_audit(
    candidates: Iterable[PairLike],
    n_items: int,
    gold: Iterable[PairLike] | None = None,
    latency_seconds: float | None = None,
    cost_usd: float | None = None,
    notes: str | None = None,
) -> RetrievalAudit:
    """Compute every retrieval-audit metric that the available data supports.

    Gold-dependent fields stay ``None`` when ``gold`` is ``None``; the
    gold-independent ones (counts, exhaustive comparisons, reduction ratio)
    are always computed. ``latency_seconds`` and ``cost_usd`` are stored
    verbatim.
    """
    candidate_pairs = normalise_pairs(candidates)
    n_candidates = len(candidate_pairs)
    # Materialise gold once: it may be a one-shot iterator and is read twice.
    gold_pairs = None if gold is None else normalise_pairs(gold)
    return RetrievalAudit(
        n_items=n_items,
        candidate_count=n_candidates,
        exhaustive_comparisons=exhaustive_comparisons(n_items),
        reduction_ratio=reduction_ratio(n_candidates, n_items),
        pair_completeness=pair_completeness(candidate_pairs, gold_pairs),
        pairs_quality=pairs_quality(candidate_pairs, gold_pairs),
        gold_available=gold is not None,
        latency_seconds=latency_seconds,
        cost_usd=cost_usd,
        notes=notes,
    )
