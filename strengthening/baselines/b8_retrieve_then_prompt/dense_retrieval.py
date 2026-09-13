"""B8 stage 2 -- dense semantic retrieval.

Embeds a seed keyword and a candidate pool with
``sentence-transformers/all-MiniLM-L6-v2`` and returns the cosine top-k.

OFFLINE BY CONSTRUCTION: ``HF_HUB_OFFLINE=1`` (and the transformers/datasets
equivalents) are set in this process BEFORE the library is imported, so the
hub client is never allowed to reach the network -- it resolves the model from
the local cache or fails. Telemetry is disabled for the same reason.

If the model cannot be loaded for any reason -- no local cache in a fresh test
sandbox, a corrupted download, a missing optional dependency -- the stage
degrades to a CLEARLY FLAGGED "embedding unavailable" mode
(:attr:`DenseRetrievalResult.available` is ``False`` and
:attr:`DenseRetrievalResult.unavailable_reason` says why) and returns no
neighbours. It never raises out of the pipeline and never silently returns an
empty result that could be mistaken for "no similar candidates".
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Final, Sequence

#: Route tag recorded on candidates proposed by this stage.
ROUTE_DENSE: Final[str] = "dense_embedding"

#: Pinned embedding model, matching ``embedding_model`` in protocol_v1.yaml.
EMBEDDING_MODEL_NAME: Final[str] = "sentence-transformers/all-MiniLM-L6-v2"

#: Environment forced before the library import, to guarantee no hub traffic.
_OFFLINE_ENV: Final[dict[str, str]] = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}

# Process-level cache: loading the model costs tens of seconds, and the whole
# point of the guard is that we attempt it at most once per (process, name).
_MODEL_CACHE: dict[str, Any] = {}
_FAILURE_CACHE: dict[str, str] = {}


@dataclass(frozen=True)
class Neighbour:
    """One retrieved candidate and its cosine similarity to the seed."""

    candidate: str
    similarity: float
    rank: int


@dataclass(frozen=True)
class DenseRetrievalResult:
    """Outcome of the dense retrieval stage for one seed.

    ``available is False`` means the embedding model could not be loaded. That
    is a REPORTED CONDITION, not an empty result: downstream code and any
    write-up must distinguish "the dense route found nothing" from "the dense
    route could not run".
    """

    seed: str
    neighbours: tuple[Neighbour, ...] = ()
    available: bool = True
    unavailable_reason: str | None = None
    model_name: str = EMBEDDING_MODEL_NAME
    route: str = ROUTE_DENSE

    @property
    def candidates(self) -> tuple[str, ...]:
        return tuple(n.candidate for n in self.neighbours)

    def __len__(self) -> int:
        return len(self.neighbours)


def _force_offline_env() -> None:
    """Set the offline env vars. Must run before importing the library."""

    for key, value in _OFFLINE_ENV.items():
        os.environ.setdefault(key, value)
        # setdefault is not enough if a caller set "0" earlier in the process.
        if os.environ.get(key) in ("0", "false", "False", ""):
            os.environ[key] = value


def load_embedding_model(model_name: str = EMBEDDING_MODEL_NAME) -> tuple[Any, str | None]:
    """Load (and cache) the sentence-transformers model.

    Returns ``(model, None)`` on success and ``(None, reason)`` on failure.
    Never raises.
    """

    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name], None
    if model_name in _FAILURE_CACHE:
        return None, _FAILURE_CACHE[model_name]

    _force_offline_env()
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        model = SentenceTransformer(model_name)
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the pipeline
        reason = f"{type(exc).__name__}: {exc}"
        _FAILURE_CACHE[model_name] = reason
        return None, reason

    _MODEL_CACHE[model_name] = model
    return model, None


def embedding_available(model_name: str = EMBEDDING_MODEL_NAME) -> bool:
    """Return whether the pinned embedding model can be loaded offline."""

    model, _ = load_embedding_model(model_name)
    return model is not None


def reset_model_cache() -> None:
    """Clear the process-level model/failure caches (used by tests)."""

    _MODEL_CACHE.clear()
    _FAILURE_CACHE.clear()


def _cosine_similarities(seed_vector, matrix):
    """Cosine similarity of one vector against a matrix of vectors."""

    import numpy as np  # noqa: PLC0415

    seed_vector = np.asarray(seed_vector, dtype="float64")
    matrix = np.asarray(matrix, dtype="float64")

    seed_norm = np.linalg.norm(seed_vector)
    row_norms = np.linalg.norm(matrix, axis=1)
    denom = seed_norm * row_norms
    # Guard against a zero-length vector (an empty or whitespace keyword).
    denom = np.where(denom == 0.0, 1e-12, denom)
    return (matrix @ seed_vector) / denom


def dense_retrieve(
    seed: str,
    universe: Sequence[str],
    *,
    top_k: int = 5,
    min_similarity: float | None = None,
    model_name: str = EMBEDDING_MODEL_NAME,
    exclude_self: bool = True,
) -> DenseRetrievalResult:
    """Return the cosine top-k neighbours of ``seed`` within ``universe``.

    Ties are broken by universe order (``numpy.argsort(kind="stable")`` on the
    negated similarities), so the result is deterministic for a given input
    order and a given model.
    """

    pool = [item for item in universe if not (exclude_self and item == seed)]
    if not pool:
        return DenseRetrievalResult(seed=seed, neighbours=())

    model, reason = load_embedding_model(model_name)
    if model is None:
        return DenseRetrievalResult(
            seed=seed,
            neighbours=(),
            available=False,
            unavailable_reason=(
                f"embedding unavailable: could not load {model_name!r} offline "
                f"({reason})"
            ),
            model_name=model_name,
        )

    try:
        import numpy as np  # noqa: PLC0415

        vectors = model.encode([seed, *pool], show_progress_bar=False)
        vectors = np.asarray(vectors, dtype="float64")
        similarities = _cosine_similarities(vectors[0], vectors[1:])
        order = np.argsort(-similarities, kind="stable")
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the pipeline
        return DenseRetrievalResult(
            seed=seed,
            neighbours=(),
            available=False,
            unavailable_reason=(
                f"embedding unavailable: encoding failed "
                f"({type(exc).__name__}: {exc})"
            ),
            model_name=model_name,
        )

    neighbours: list[Neighbour] = []
    for rank, idx in enumerate(order[: max(0, int(top_k))]):
        similarity = float(similarities[int(idx)])
        if min_similarity is not None and similarity < min_similarity:
            continue
        neighbours.append(
            Neighbour(candidate=pool[int(idx)], similarity=similarity, rank=rank)
        )

    return DenseRetrievalResult(
        seed=seed, neighbours=tuple(neighbours), model_name=model_name
    )


def encode_universe_once(
    universe: Sequence[str], *, model_name: str = EMBEDDING_MODEL_NAME
):
    """Encode every string in ``universe`` exactly once and return
    ``(embeddings, reason)``: ``embeddings`` is an ``(n, d)`` float64
    array in universe order on success, ``None`` with a reason string on
    failure. Never raises -- same degrade-cleanly contract as
    :func:`load_embedding_model`.

    This is the performance fix for :func:`dense_retrieve_batch`:
    ``dense_retrieve`` re-encodes the (near-)entire universe on EVERY
    call, which is fine for a handful of seeds but becomes an O(n_seeds *
    n_universe) cost that is impractical once both are in the thousands.
    Encoding the universe once and reusing the resulting matrix turns
    that into a single O(n_universe) encode plus, per seed, a cheap
    vectorised similarity computation over an already-computed matrix.
    """

    model, reason = load_embedding_model(model_name)
    if model is None:
        return None, f"embedding unavailable: could not load {model_name!r} offline ({reason})"
    try:
        import numpy as np  # noqa: PLC0415

        vectors = model.encode(list(universe), show_progress_bar=False)
        return np.asarray(vectors, dtype="float64"), None
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the pipeline
        return None, f"embedding unavailable: encoding failed ({type(exc).__name__}: {exc})"


def dense_retrieve_batch(
    seeds: Sequence[str],
    universe: Sequence[str],
    *,
    top_k: int = 5,
    min_similarity: float | None = None,
    model_name: str = EMBEDDING_MODEL_NAME,
    exclude_self: bool = True,
    precomputed_embeddings=None,
) -> dict[str, DenseRetrievalResult]:
    """Batched, algorithmically-identical replacement for calling
    :func:`dense_retrieve` once per seed.

    Encodes ``universe`` exactly ONCE (or reuses ``precomputed_embeddings``
    if given, in the same order as ``universe``), then for every seed in
    ``seeds`` (which need not be a subset of ``universe``, though for B8
    it always is) computes cosine similarities against the SAME pool a
    per-seed :func:`dense_retrieve` call would have used (universe minus
    the seed's own occurrence, in universe order), ranks them with the
    identical stable-sort tie-break, and applies the identical top-k-then-
    min_similarity filtering. For any seed present in ``universe``, this
    is required to produce byte-identical results to ``dense_retrieve``
    (verified by the equivalence tests in test_dense_retrieval_batch.py);
    for a seed NOT in ``universe`` the pool is simply the whole universe
    (nothing to exclude), which ``dense_retrieve`` also supports.

    Returns a ``{seed: DenseRetrievalResult}`` mapping. Degrades cleanly
    (every result carries ``available=False``) if the model cannot be
    loaded or encoding fails -- it never raises out of the pipeline.
    """
    import numpy as np  # noqa: PLC0415

    universe_list = list(universe)

    if precomputed_embeddings is not None:
        universe_vectors = np.asarray(precomputed_embeddings, dtype="float64")
        reason = None
    else:
        universe_vectors, reason = encode_universe_once(universe_list, model_name=model_name)

    if universe_vectors is None:
        return {
            seed: DenseRetrievalResult(
                seed=seed, neighbours=(), available=False, unavailable_reason=reason, model_name=model_name
            )
            for seed in seeds
        }

    # Map each universe string to ALL its row indices (a universe may, in
    # principle, contain duplicate surface strings -- lexical_anchor.py's
    # own build_normalised_index makes the same allowance).
    indices_by_string: dict[str, list[int]] = {}
    for i, item in enumerate(universe_list):
        indices_by_string.setdefault(item, []).append(i)

    results: dict[str, DenseRetrievalResult] = {}
    for seed in seeds:
        seed_rows = indices_by_string.get(seed)
        if seed_rows and exclude_self:
            # Exclude exactly ONE occurrence of the seed's own row (its
            # first), matching dense_retrieve's `item == seed` exclusion
            # applied while walking the universe in order.
            self_row = seed_rows[0]
            pool_indices = [i for i in range(len(universe_list)) if i != self_row]
        else:
            pool_indices = list(range(len(universe_list)))
        pool = [universe_list[i] for i in pool_indices]

        if not pool:
            results[seed] = DenseRetrievalResult(seed=seed, neighbours=())
            continue

        if seed_rows:
            seed_vector = universe_vectors[seed_rows[0]]
        else:
            # Seed not present in the universe at all: encode it fresh,
            # exactly as dense_retrieve would (it always includes the
            # seed in its own per-call encode([seed, *pool]) batch).
            fresh, fresh_reason = encode_universe_once([seed], model_name=model_name)
            if fresh is None:
                results[seed] = DenseRetrievalResult(
                    seed=seed, neighbours=(), available=False, unavailable_reason=fresh_reason, model_name=model_name
                )
                continue
            seed_vector = fresh[0]

        pool_matrix = universe_vectors[pool_indices]
        similarities = _cosine_similarities(seed_vector, pool_matrix)

        order = np.argsort(-similarities, kind="stable")
        neighbours: list[Neighbour] = []
        for rank, idx in enumerate(order[: max(0, int(top_k))]):
            similarity = float(similarities[int(idx)])
            if min_similarity is not None and similarity < min_similarity:
                continue
            neighbours.append(Neighbour(candidate=pool[int(idx)], similarity=similarity, rank=rank))

        results[seed] = DenseRetrievalResult(seed=seed, neighbours=tuple(neighbours), model_name=model_name)

    return results
