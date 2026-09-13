"""Tests for the B8 retrieve-then-prompt hybrid baseline.

Everything here runs offline. The embedding stage is exercised against the
locally-cached MiniLM model with ``HF_HUB_OFFLINE=1``; if that cache is absent
the stage must degrade to a clearly-flagged "embedding unavailable" result
rather than crashing, and there is a test for that path too (forced, so it is
checked on every machine regardless of cache state).
"""

from __future__ import annotations

import pytest

from strengthening.baselines.b7_direct_relation.client import B7Client, MockB7Client
from strengthening.baselines.b8_retrieve_then_prompt import dense_retrieval
from strengthening.baselines.b8_retrieve_then_prompt.candidate_union import (
    dedupe_pairs,
    union_candidates,
)
from strengthening.baselines.b8_retrieve_then_prompt.clustering import (
    UnionFind,
    component_size_distribution,
    connected_components,
)
from strengthening.baselines.b8_retrieve_then_prompt.dense_retrieval import (
    EMBEDDING_MODEL_NAME,
    ROUTE_DENSE,
    DenseRetrievalResult,
    dense_retrieve,
    embedding_available,
)
from strengthening.baselines.b8_retrieve_then_prompt.lexical_anchor import (
    ROUTE_LEXICAL,
    lexical_anchor,
    lexical_anchor_pairs,
)
from strengthening.baselines.b8_retrieve_then_prompt.logging_hooks import (
    B8RunLog,
    candidate_retrieval_recall,
)
from strengthening.baselines.b8_retrieve_then_prompt.normalisation import (
    EXCLUDED_BY_POLICY,
    NORMALISATION_STEPS,
    legacy_normalise,
)
from strengthening.baselines.b8_retrieve_then_prompt.pipeline import (
    retrieve_candidates,
    run_b8_pipeline,
)
from strengthening.baselines.b8_retrieve_then_prompt.relation_classification import (
    MATCH_RELATION,
    accepted_match_edges,
    classify_pair,
    classify_pairs,
)

# A small synthetic universe. No real data, no restricted keyword strings.
SYNTHETIC_UNIVERSE = [
    "circular economy",
    "Circular Economy",
    "circular  economy",
    "circular economies",
    "waste hierarchy",
    "waste management",
    "industrial symbiosis",
]


# ---------------------------------------------------------------------------
# Stage 0 -- legacy-exact normalisation
# ---------------------------------------------------------------------------


def test_normalisation_applies_exactly_the_four_legacy_steps() -> None:
    assert NORMALISATION_STEPS == (
        "unicode_nfkc",
        "lowercase",
        "strip_leading_trailing_whitespace",
        "collapse_internal_whitespace",
    )
    assert legacy_normalise("  Circular   Economy  ") == "circular economy"
    assert legacy_normalise("CIRCULAR\tECONOMY") == "circular economy"
    # NFKC folds the compatibility ligature and the full-width form.
    assert legacy_normalise("ﬁnance") == "finance"
    assert legacy_normalise("ＣＥ") == "ce"


def test_normalisation_does_not_apply_excluded_policy_steps() -> None:
    """Punctuation, acronyms, stemming, lemmas and stopwords stay untouched."""

    assert "punctuation_standardisation" in EXCLUDED_BY_POLICY

    # Punctuation is preserved -> hyphenation variants do NOT anchor lexically.
    assert legacy_normalise("e-waste") == "e-waste"
    assert legacy_normalise("e waste") == "e waste"
    assert legacy_normalise("e-waste") != legacy_normalise("e waste")

    # No stemming/lemmatisation -> plurals do NOT collapse.
    assert legacy_normalise("circular economies") != legacy_normalise(
        "circular economy"
    )

    # No acronym expansion.
    assert legacy_normalise("EPR") == "epr"

    # No stopword removal.
    assert legacy_normalise("The Circular Economy") == "the circular economy"


# ---------------------------------------------------------------------------
# Stage 1 -- lexical anchoring
# ---------------------------------------------------------------------------


def test_lexical_anchoring_finds_case_and_whitespace_variants() -> None:
    result = lexical_anchor("circular economy", SYNTHETIC_UNIVERSE)

    assert result.normalised_seed == "circular economy"
    # Case variant and double-space variant anchor; the plural does not.
    assert set(result.candidates) == {"Circular Economy", "circular  economy"}
    assert "circular economies" not in result.candidates
    assert result.route == ROUTE_LEXICAL
    # The seed's own surface string is excluded by default.
    assert "circular economy" not in result.candidates


def test_lexical_anchoring_can_include_self_and_is_order_stable() -> None:
    with_self = lexical_anchor(
        "circular economy", SYNTHETIC_UNIVERSE, include_self=True
    )
    assert with_self.candidates[0] == "circular economy"
    # Output follows universe order.
    assert list(with_self.candidates) == [
        "circular economy",
        "Circular Economy",
        "circular  economy",
    ]


def test_lexical_anchoring_returns_nothing_for_an_isolated_seed() -> None:
    result = lexical_anchor("industrial symbiosis", SYNTHETIC_UNIVERSE)
    assert result.candidates == ()
    assert len(result) == 0


def test_lexical_anchor_pairs_enumerates_all_anchored_pairs() -> None:
    pairs = lexical_anchor_pairs(SYNTHETIC_UNIVERSE)
    # The three "circular economy" surface variants form C(3,2) = 3 pairs.
    assert len(pairs) == 3
    assert ("circular economy", "Circular Economy") in pairs
    assert ("circular economy", "circular  economy") in pairs
    assert ("Circular Economy", "circular  economy") in pairs


# ---------------------------------------------------------------------------
# Stage 2 -- dense retrieval
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def embedding_is_available() -> bool:
    return embedding_available()


def test_dense_retrieval_returns_plausible_neighbours_or_reports_unavailable(
    embedding_is_available: bool,
) -> None:
    """The primary embedding path, with an explicit unavailable fallback.

    If the cached model cannot load, this asserts the degradation contract
    instead of failing -- and the flag makes that visible in the log.
    """

    universe = [
        "circular economy",
        "circular economies",
        "recycling",
        "industrial symbiosis",
        "blood pressure",
        "myocardial infarction",
    ]
    result = dense_retrieve("circular economy", universe, top_k=3)

    if not embedding_is_available:
        assert result.available is False
        assert result.unavailable_reason is not None
        assert "embedding unavailable" in result.unavailable_reason
        assert result.neighbours == ()
        pytest.skip(
            "cached embedding model unavailable; degradation path asserted instead"
        )

    assert result.available is True
    assert result.unavailable_reason is None
    assert len(result) == 3
    assert result.model_name == EMBEDDING_MODEL_NAME
    assert result.route == ROUTE_DENSE

    # The seed itself is excluded from its own neighbour list.
    assert "circular economy" not in result.candidates

    # Plausibility: the near-duplicate outranks the unrelated biomedical term.
    assert result.candidates[0] == "circular economies"
    similarities = [n.similarity for n in result.neighbours]
    assert similarities == sorted(similarities, reverse=True)
    assert all(-1.0001 <= s <= 1.0001 for s in similarities)
    assert result.neighbours[0].similarity > 0.5
    assert [n.rank for n in result.neighbours] == [0, 1, 2]


def test_dense_retrieval_is_deterministic(embedding_is_available: bool) -> None:
    if not embedding_is_available:
        pytest.skip("cached embedding model unavailable")

    universe = ["waste hierarchy", "waste management", "recycling", "hypertension"]
    first = dense_retrieve("waste hierarchy", universe, top_k=3)
    second = dense_retrieve("waste hierarchy", universe, top_k=3)
    assert first.candidates == second.candidates
    assert [n.similarity for n in first.neighbours] == [
        n.similarity for n in second.neighbours
    ]


def test_dense_retrieval_honours_min_similarity(
    embedding_is_available: bool,
) -> None:
    if not embedding_is_available:
        pytest.skip("cached embedding model unavailable")

    universe = ["circular economies", "myocardial infarction"]
    strict = dense_retrieve(
        "circular economy", universe, top_k=5, min_similarity=0.9
    )
    assert strict.available is True
    assert "myocardial infarction" not in strict.candidates


def test_dense_retrieval_degrades_cleanly_when_the_model_cannot_load(
    monkeypatch,
) -> None:
    """Forced failure path -- checked on every machine, cache or no cache."""

    monkeypatch.setattr(
        dense_retrieval,
        "load_embedding_model",
        lambda model_name=EMBEDDING_MODEL_NAME: (None, "OSError: no local cache"),
    )

    result = dense_retrieve("circular economy", SYNTHETIC_UNIVERSE, top_k=3)

    assert isinstance(result, DenseRetrievalResult)
    assert result.available is False
    assert result.neighbours == ()
    assert result.unavailable_reason is not None
    assert "embedding unavailable" in result.unavailable_reason
    assert "no local cache" in result.unavailable_reason


def test_dense_retrieval_offline_environment_is_forced() -> None:
    """The hub must be pinned offline before the library is ever imported."""

    import os

    dense_retrieval._force_offline_env()
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_dense_retrieval_handles_an_empty_pool() -> None:
    result = dense_retrieve("solo", ["solo"], top_k=3)
    assert result.neighbours == ()
    assert result.available is True


# ---------------------------------------------------------------------------
# Stage 3 -- union + de-duplication with provenance
# ---------------------------------------------------------------------------


def _fake_dense(seed: str, pairs: list[tuple[str, float]]) -> DenseRetrievalResult:
    return DenseRetrievalResult(
        seed=seed,
        neighbours=tuple(
            dense_retrieval.Neighbour(candidate=name, similarity=score, rank=rank)
            for rank, (name, score) in enumerate(pairs)
        ),
    )


def test_union_dedupes_and_preserves_multi_route_provenance() -> None:
    lexical = lexical_anchor("circular economy", SYNTHETIC_UNIVERSE)
    dense = _fake_dense(
        "circular economy",
        [("Circular Economy", 0.99), ("circular economies", 0.93), ("recycling", 0.6)],
    )

    merged = union_candidates(lexical, dense)
    names = merged.candidate_strings

    # Each candidate appears exactly once.
    assert len(names) == len(set(names))
    assert set(names) == {
        "Circular Economy",
        "circular  economy",
        "circular economies",
        "recycling",
    }

    by_name = {c.candidate: c for c in merged.candidates}

    # Found by BOTH routes -> both tags retained, dense score kept.
    assert by_name["Circular Economy"].routes == (ROUTE_LEXICAL, ROUTE_DENSE)
    assert by_name["Circular Economy"].multi_route is True
    assert by_name["Circular Economy"].similarity == pytest.approx(0.99)
    assert by_name["Circular Economy"].dense_rank == 0

    # Lexical only.
    assert by_name["circular  economy"].routes == (ROUTE_LEXICAL,)
    assert by_name["circular  economy"].similarity is None
    assert by_name["circular  economy"].multi_route is False

    # Dense only.
    assert by_name["circular economies"].routes == (ROUTE_DENSE,)
    assert by_name["circular economies"].similarity == pytest.approx(0.93)

    assert len(merged.multi_route_candidates) == 1
    assert merged.by_route(ROUTE_LEXICAL) == [
        by_name["Circular Economy"],
        by_name["circular  economy"],
    ]


def test_union_orders_lexical_first_then_dense_by_rank() -> None:
    lexical = lexical_anchor("circular economy", SYNTHETIC_UNIVERSE)
    dense = _fake_dense(
        "circular economy", [("circular economies", 0.93), ("recycling", 0.6)]
    )
    merged = union_candidates(lexical, dense)
    assert list(merged.candidate_strings) == [
        "Circular Economy",
        "circular  economy",
        "circular economies",
        "recycling",
    ]


def test_union_works_with_the_dense_route_absent_or_unavailable() -> None:
    lexical = lexical_anchor("circular economy", SYNTHETIC_UNIVERSE)

    no_dense = union_candidates(lexical, None)
    assert no_dense.dense_available is True
    assert all(c.routes == (ROUTE_LEXICAL,) for c in no_dense.candidates)

    unavailable = union_candidates(
        lexical,
        DenseRetrievalResult(
            seed="circular economy",
            available=False,
            unavailable_reason="embedding unavailable: forced",
        ),
    )
    assert unavailable.dense_available is False
    assert unavailable.dense_unavailable_reason == "embedding unavailable: forced"
    # The lexical route still contributed.
    assert len(unavailable) == 2


def test_union_rejects_mismatched_seeds() -> None:
    lexical = lexical_anchor("a", ["a", "A"])
    with pytest.raises(ValueError, match="seed mismatch"):
        union_candidates(lexical, _fake_dense("b", []))


def test_dedupe_pairs_collapses_mirrored_pairs() -> None:
    sets = retrieve_candidates(
        ["circular economy", "Circular Economy"],
        SYNTHETIC_UNIVERSE,
        use_dense=False,
    )
    pairs = dedupe_pairs(sets)
    # (circular economy, Circular Economy) and its mirror count once.
    as_frozensets = [frozenset(p) for p in pairs]
    assert len(as_frozensets) == len(set(as_frozensets))
    assert frozenset({"circular economy", "Circular Economy"}) in as_frozensets


# ---------------------------------------------------------------------------
# Stage 4 -- B7 comparator applied to candidate pairs
# ---------------------------------------------------------------------------


def test_only_same_as_creates_a_match_edge() -> None:
    client = MockB7Client(
        canned_responses={
            ("a", "b"): "same_as",
            ("c", "d"): "broader",
            ("e", "f"): "narrower",
            ("g", "h"): "other",
        }
    )
    judgements = classify_pairs(client, [("a", "b"), ("c", "d"), ("e", "f"), ("g", "h")])

    assert [j.relation for j in judgements] == [
        "same_as",
        "broader",
        "narrower",
        "other",
    ]
    assert [j.accepted_as_match for j in judgements] == [True, False, False, False]
    assert accepted_match_edges(judgements) == [("a", "b")]
    assert MATCH_RELATION == "same_as"


def test_parse_failures_are_recorded_and_never_become_matches() -> None:
    class BrokenClient:
        def classify(self, keyword_a: str, keyword_b: str):
            from strengthening.baselines.b7_direct_relation.client import B7Response

            return B7Response(
                keyword_a=keyword_a, keyword_b=keyword_b, raw_text="not json"
            )

    judgement = classify_pair(BrokenClient(), "a", "b")
    assert judgement.parse_ok is False
    assert judgement.relation is None
    assert judgement.accepted_as_match is False
    assert accepted_match_edges([judgement]) == []


def test_real_mode_client_raises_before_any_call() -> None:
    """B8 must never be able to reach a live model either."""

    with pytest.raises(NotImplementedError, match="not authorised"):
        classify_pair(B7Client(), "a", "b")

    with pytest.raises(NotImplementedError, match="not authorised"):
        run_b8_pipeline(
            ["circular economy"],
            SYNTHETIC_UNIVERSE,
            client=B7Client(),
            use_dense=False,
        )


def test_judgement_carries_route_provenance_and_token_counts() -> None:
    judgement = classify_pair(
        MockB7Client(), "a", "b", routes=(ROUTE_LEXICAL, ROUTE_DENSE)
    )
    assert judgement.routes == (ROUTE_LEXICAL, ROUTE_DENSE)
    assert judgement.input_tokens > 0
    assert judgement.output_tokens > 0
    assert judgement.as_dict()["routes"] == [ROUTE_LEXICAL, ROUTE_DENSE]


# ---------------------------------------------------------------------------
# Stage 5 -- connected components over accepted match edges
# ---------------------------------------------------------------------------


def test_connected_components_on_a_hand_constructed_edge_list() -> None:
    """8 nodes, hand-checked expected partition.

    Edges: a-b, b-c   -> {a, b, c}
           d-e        -> {d, e}
           f-g, g-h   -> {f, g, h}
    (no node is left out; there are no singletons in this example)
    """

    nodes = ["a", "b", "c", "d", "e", "f", "g", "h"]
    edges = [("a", "b"), ("b", "c"), ("d", "e"), ("f", "g"), ("g", "h")]

    output = connected_components(edges, nodes=nodes)

    assert output.clusters == (
        ("a", "b", "c"),
        ("d", "e"),
        ("f", "g", "h"),
    )
    assert output.n_clusters == 3
    assert output.n_items == 8
    assert output.n_singletons == 0
    assert output.assignments["a"] == output.assignments["c"] == 0
    assert output.assignments["d"] == 1
    assert output.assignments["h"] == 2


def test_connected_components_includes_singletons_for_unmatched_nodes() -> None:
    nodes = ["a", "b", "c", "d", "e"]
    edges = [("a", "b")]
    output = connected_components(edges, nodes=nodes)

    assert output.clusters == (("a", "b"), ("c",), ("d",), ("e",))
    assert output.n_singletons == 3
    assert component_size_distribution(output) == {1: 3, 2: 1}


def test_connected_components_is_invariant_to_edge_order() -> None:
    nodes = ["a", "b", "c", "d", "e"]
    forward = connected_components(
        [("a", "b"), ("b", "c"), ("d", "e")], nodes=nodes
    )
    reversed_edges = connected_components(
        [("d", "e"), ("b", "c"), ("a", "b")], nodes=nodes
    )
    swapped = connected_components(
        [("b", "a"), ("c", "b"), ("e", "d")], nodes=nodes
    )
    assert forward.clusters == reversed_edges.clusters == swapped.clusters


def test_union_find_reports_whether_a_union_merged_anything() -> None:
    union_find = UnionFind(["a", "b", "c"])
    assert union_find.union("a", "b") is True
    assert union_find.union("a", "b") is False  # already together
    assert union_find.find("a") == union_find.find("b")
    assert union_find.find("c") != union_find.find("a")


def test_transitive_closure_chains_through_the_middle_node() -> None:
    output = connected_components([("a", "b"), ("b", "c")], nodes=["a", "b", "c"])
    assert output.clusters == (("a", "b", "c"),)


# ---------------------------------------------------------------------------
# Logging hooks
# ---------------------------------------------------------------------------


def test_candidate_retrieval_recall_is_none_without_gold() -> None:
    pairs = [("a", "b"), ("c", "d")]
    assert candidate_retrieval_recall(pairs, gold=None) is None
    assert candidate_retrieval_recall(pairs, gold=[]) is None


def test_candidate_retrieval_recall_with_synthetic_gold() -> None:
    retrieved = [("a", "b"), ("c", "d")]
    # Gold has 4 relevant pairs; 2 were retrieved (one mirrored) -> 0.5
    gold = [("b", "a"), ("c", "d"), ("e", "f"), ("g", "h")]
    assert candidate_retrieval_recall(retrieved, gold) == pytest.approx(0.5)


def test_run_log_reports_every_required_field() -> None:
    log = B8RunLog()
    as_dict = log.as_dict()
    for required in (
        "candidate_count",
        "candidate_retrieval_recall",
        "number_of_llm_calls",
        "tokens",
        "estimated_cost",
        "runtime_seconds",
        "accepted_match_edges",
        "cluster_output",
    ):
        assert required in as_dict


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------


def test_pipeline_end_to_end_is_deterministic_and_reproducible() -> None:
    seeds = ["circular economy", "waste hierarchy"]

    def run():
        return run_b8_pipeline(
            seeds,
            SYNTHETIC_UNIVERSE,
            client=MockB7Client(),
            use_dense=False,
        )

    first, second = run(), run()

    assert first.clusters.clusters == second.clusters.clusters
    assert first.clusters.assignments == second.clusters.assignments
    assert first.log.accepted_match_edges == second.log.accepted_match_edges
    assert first.log.candidate_count == second.log.candidate_count
    assert first.log.number_of_llm_calls == second.log.number_of_llm_calls
    assert first.log.tokens == second.log.tokens
    assert [j.relation for j in first.judgements] == [
        j.relation for j in second.judgements
    ]


def test_pipeline_clusters_the_normalised_variants_together() -> None:
    """The mock returns same_as for strings equal after casefolding."""

    result = run_b8_pipeline(
        ["circular economy"],
        SYNTHETIC_UNIVERSE,
        client=MockB7Client(),
        use_dense=False,
    )

    cluster_of = result.clusters.assignments
    assert cluster_of["circular economy"] == cluster_of["Circular Economy"]
    # The double-space variant normalises the same way, so it anchors and the
    # mock (which casefolds + collapses whitespace) accepts it as same_as.
    assert cluster_of["circular economy"] == cluster_of["circular  economy"]
    # An unrelated keyword stays in its own singleton cluster.
    assert cluster_of["industrial symbiosis"] != cluster_of["circular economy"]


def test_pipeline_log_is_populated_and_honest_about_missing_gold() -> None:
    result = run_b8_pipeline(
        ["circular economy", "waste hierarchy"],
        SYNTHETIC_UNIVERSE,
        client=MockB7Client(),
        use_dense=False,
    )
    log = result.log

    assert log.n_seeds == 2
    assert log.candidate_count == len(dedupe_pairs(result.candidate_sets))
    assert log.number_of_llm_calls == len(result.judgements)
    assert log.tokens == log.input_tokens + log.output_tokens
    assert log.estimated_cost is not None and log.estimated_cost >= 0.0
    assert log.estimated_cost_is_placeholder is True
    assert log.runtime_seconds >= 0.0
    assert log.n_parse_failures == 0
    assert log.cluster_output is not None
    assert log.cluster_output["n_clusters"] == result.clusters.n_clusters

    # No gold retrieval annotations exist -> None, never a fabricated number.
    assert log.candidate_retrieval_recall is None


def test_pipeline_has_no_uncertain_or_abstention_output() -> None:
    """B8 is a simple baseline: every judgement is a four-way relation."""

    result = run_b8_pipeline(
        ["circular economy", "waste hierarchy"],
        SYNTHETIC_UNIVERSE,
        client=MockB7Client(),
        use_dense=False,
    )
    relations = {j.relation for j in result.judgements}
    assert "uncertain" not in relations
    assert relations <= {"same_as", "broader", "narrower", "other"}

    for judgement in result.judgements:
        assert not hasattr(judgement, "abstained")
        assert not hasattr(judgement, "uncertain")
        assert not hasattr(judgement, "guard_triggered")
    assert not hasattr(result.log, "n_abstentions")


def test_pipeline_with_dense_route_runs_or_flags_unavailable(
    embedding_is_available: bool,
) -> None:
    result = run_b8_pipeline(
        ["circular economy"],
        SYNTHETIC_UNIVERSE,
        client=MockB7Client(),
        use_dense=True,
        top_k=3,
    )

    assert result.log.dense_route_available is embedding_is_available
    if embedding_is_available:
        assert result.log.dense_unavailable_reason is None
        assert result.log.candidate_count > 0
        routes = {r for cs in result.candidate_sets for c in cs for r in c.routes}
        assert ROUTE_DENSE in routes
    else:
        assert result.log.dense_unavailable_reason is not None
        assert "embedding unavailable" in result.log.dense_unavailable_reason


def test_pipeline_can_exclude_singletons() -> None:
    result = run_b8_pipeline(
        ["circular economy"],
        SYNTHETIC_UNIVERSE,
        client=MockB7Client(),
        use_dense=False,
        include_singletons=False,
    )
    flat = {item for cluster in result.clusters.clusters for item in cluster}
    assert "industrial symbiosis" not in flat
