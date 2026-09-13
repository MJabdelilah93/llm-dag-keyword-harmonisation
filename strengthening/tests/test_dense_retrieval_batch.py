"""C1B Task 5: equivalence tests between the original per-seed
dense_retrieve and the new batched dense_retrieve_batch. Requires
IDENTICAL neighbour identities and ordering (same model, same
top_k/min_similarity, same tie-breaking) -- these are the tests that
justify treating the batched path as a pure performance fix, not an
algorithm change.

Skips (rather than failing) when the pinned embedding model cannot be
loaded offline in this environment, matching the existing test suite's
convention for embedding-dependent tests.
"""
from __future__ import annotations

import pytest

from strengthening.baselines.b8_retrieve_then_prompt.dense_retrieval import (
    dense_retrieve,
    dense_retrieve_batch,
    embedding_available,
    encode_universe_once,
)

SYNTHETIC_UNIVERSE = [
    "circular economy",
    "circular economy strategies",
    "closed loop supply chain",
    "recycling",
    "upcycling",
    "waste management",
    "sustainability",
    "resource efficiency",
    "linear economy",
    "product life extension",
    "reverse logistics",
    "cradle to cradle design",
]


@pytest.fixture(scope="module")
def embedding_is_available() -> bool:
    return embedding_available()


def _assert_identical(old_result, new_result):
    assert len(old_result.neighbours) == len(new_result.neighbours)
    for old_n, new_n in zip(old_result.neighbours, new_result.neighbours):
        assert old_n.candidate == new_n.candidate
        assert old_n.rank == new_n.rank
        assert old_n.similarity == pytest.approx(new_n.similarity, abs=1e-9)


def test_batch_matches_per_seed_for_every_seed_in_universe(embedding_is_available):
    if not embedding_is_available:
        pytest.skip("embedding model not available offline in this environment")

    batch_results = dense_retrieve_batch(SYNTHETIC_UNIVERSE, SYNTHETIC_UNIVERSE, top_k=5)
    for seed in SYNTHETIC_UNIVERSE:
        old = dense_retrieve(seed, SYNTHETIC_UNIVERSE, top_k=5)
        new = batch_results[seed]
        _assert_identical(old, new)


def test_batch_matches_per_seed_with_min_similarity_filter(embedding_is_available):
    if not embedding_is_available:
        pytest.skip("embedding model not available offline in this environment")

    batch_results = dense_retrieve_batch(SYNTHETIC_UNIVERSE, SYNTHETIC_UNIVERSE, top_k=5, min_similarity=0.3)
    for seed in SYNTHETIC_UNIVERSE:
        old = dense_retrieve(seed, SYNTHETIC_UNIVERSE, top_k=5, min_similarity=0.3)
        new = batch_results[seed]
        _assert_identical(old, new)


def test_batch_matches_per_seed_with_smaller_top_k(embedding_is_available):
    if not embedding_is_available:
        pytest.skip("embedding model not available offline in this environment")

    batch_results = dense_retrieve_batch(SYNTHETIC_UNIVERSE, SYNTHETIC_UNIVERSE, top_k=2)
    for seed in SYNTHETIC_UNIVERSE:
        old = dense_retrieve(seed, SYNTHETIC_UNIVERSE, top_k=2)
        new = batch_results[seed]
        _assert_identical(old, new)


def test_batch_accepts_precomputed_embeddings_and_matches(embedding_is_available):
    if not embedding_is_available:
        pytest.skip("embedding model not available offline in this environment")

    embeddings, reason = encode_universe_once(SYNTHETIC_UNIVERSE)
    assert reason is None
    batch_results = dense_retrieve_batch(
        SYNTHETIC_UNIVERSE, SYNTHETIC_UNIVERSE, top_k=5, precomputed_embeddings=embeddings
    )
    for seed in SYNTHETIC_UNIVERSE:
        old = dense_retrieve(seed, SYNTHETIC_UNIVERSE, top_k=5)
        new = batch_results[seed]
        _assert_identical(old, new)


def test_batch_seed_subset_matches_per_seed(embedding_is_available):
    """Seeds need not be the whole universe (B8 only ever queries with the
    900 benchmark strings as seeds, against a much larger domain universe)."""
    if not embedding_is_available:
        pytest.skip("embedding model not available offline in this environment")

    seeds = SYNTHETIC_UNIVERSE[:4]
    batch_results = dense_retrieve_batch(seeds, SYNTHETIC_UNIVERSE, top_k=3)
    for seed in seeds:
        old = dense_retrieve(seed, SYNTHETIC_UNIVERSE, top_k=3)
        new = batch_results[seed]
        _assert_identical(old, new)


def test_batch_degrades_cleanly_when_model_unavailable(monkeypatch):
    from strengthening.baselines.b8_retrieve_then_prompt import dense_retrieval

    monkeypatch.setattr(dense_retrieval, "load_embedding_model", lambda model_name=None: (None, "forced failure for test"))
    results = dense_retrieve_batch(["a"], ["a", "b", "c"], top_k=5)
    assert not results["a"].available
    assert "forced failure for test" in results["a"].unavailable_reason


def test_encode_universe_once_returns_none_on_failure(monkeypatch):
    from strengthening.baselines.b8_retrieve_then_prompt import dense_retrieval

    monkeypatch.setattr(dense_retrieval, "load_embedding_model", lambda model_name=None: (None, "forced failure for test"))
    embeddings, reason = dense_retrieval.encode_universe_once(["a", "b"])
    assert embeddings is None
    assert "forced failure for test" in reason
