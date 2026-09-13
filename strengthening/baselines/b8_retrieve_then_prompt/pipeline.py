"""B8 end-to-end pipeline: retrieve, then prompt, then cluster.

Stages, each independently testable in its own module:

  1. :mod:`.lexical_anchor`         -- exact/normalised anchoring
  2. :mod:`.dense_retrieval`        -- cosine top-k over MiniLM embeddings
  3. :mod:`.candidate_union`        -- union + de-dup, preserving provenance
  4. :mod:`.relation_classification`-- B7's four-way comparator per pair
  5. :mod:`.clustering`             -- components over accepted match edges

Determinism: for a fixed seed list, universe order, top-k and comparator
client, the pipeline produces byte-identical cluster output. The stages are
individually order-deterministic and the final clustering is emitted in a
canonical (sorted) form.

B8 has NO uncertain output, NO guard, NO abstention routing and NO
contradiction check. It is a simpler baseline than the M7 system, on purpose.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from ..b7_direct_relation.client import MockB7Client
from ..b7_direct_relation.cost_logging import estimate_cost
from .candidate_union import CandidateSet, dedupe_pairs, union_candidates
from .clustering import ClusterOutput, connected_components
from .dense_retrieval import EMBEDDING_MODEL_NAME, dense_retrieve
from .lexical_anchor import lexical_anchor
from .logging_hooks import B8RunLog, build_run_log
from .relation_classification import (
    PairJudgement,
    SupportsClassify,
    accepted_match_edges,
    classify_pair,
)


@dataclass
class B8Result:
    """Everything one B8 run produced."""

    clusters: ClusterOutput
    judgements: list[PairJudgement] = field(default_factory=list)
    candidate_sets: list[CandidateSet] = field(default_factory=list)
    log: B8RunLog = field(default_factory=B8RunLog)

    @property
    def cluster_list(self) -> list[list[str]]:
        return [list(c) for c in self.clusters.clusters]


def retrieve_candidates(
    seeds: Sequence[str],
    universe: Sequence[str],
    *,
    top_k: int = 5,
    use_dense: bool = True,
    min_similarity: float | None = None,
    model_name: str = EMBEDDING_MODEL_NAME,
) -> list[CandidateSet]:
    """Run stages 1-3 for every seed and return the per-seed candidate sets."""

    candidate_sets: list[CandidateSet] = []
    for seed in seeds:
        lexical = lexical_anchor(seed, universe)
        dense = (
            dense_retrieve(
                seed,
                universe,
                top_k=top_k,
                min_similarity=min_similarity,
                model_name=model_name,
            )
            if use_dense
            else None
        )
        candidate_sets.append(union_candidates(lexical, dense))
    return candidate_sets


def run_b8_pipeline(
    seeds: Sequence[str],
    universe: Sequence[str],
    *,
    client: SupportsClassify | None = None,
    top_k: int = 5,
    use_dense: bool = True,
    min_similarity: float | None = None,
    model_name: str = EMBEDDING_MODEL_NAME,
    include_singletons: bool = True,
    gold_pairs: Iterable[tuple[str, str]] | None = None,
) -> B8Result:
    """Run the full B8 pipeline.

    Parameters
    ----------
    client:
        The comparator. Defaults to :class:`MockB7Client`. Passing a real-mode
        :class:`B7Client` will raise ``NotImplementedError`` from B7 on the
        first pair -- that is intended, and is not caught here.
    include_singletons:
        When ``True`` every universe item appears in the output partition,
        as a singleton if it acquired no accepted match edge.
    gold_pairs:
        Gold retrieval annotations, if they exist. They do not exist in this
        task, so the default ``None`` makes ``candidate_retrieval_recall``
        report ``None`` rather than a fabricated number.
    """

    if client is None:
        client = MockB7Client()

    started = time.perf_counter()

    candidate_sets = retrieve_candidates(
        seeds,
        universe,
        top_k=top_k,
        use_dense=use_dense,
        min_similarity=min_similarity,
        model_name=model_name,
    )

    route_lookup: dict[frozenset[str], tuple[str, ...]] = {}
    for candidate_set in candidate_sets:
        for candidate in candidate_set.candidates:
            key = frozenset((candidate.seed, candidate.candidate))
            merged = set(route_lookup.get(key, ())) | set(candidate.routes)
            # Keep a stable order for the merged route tuple.
            route_lookup[key] = tuple(
                r
                for r in ("lexical_exact", "dense_embedding")
                if r in merged
            )

    pairs = dedupe_pairs(candidate_sets)

    judgements = [
        classify_pair(
            client,
            keyword_a,
            keyword_b,
            routes=route_lookup.get(frozenset((keyword_a, keyword_b)), ()),
        )
        for keyword_a, keyword_b in pairs
    ]

    edges = accepted_match_edges(judgements)
    clusters = connected_components(
        edges, nodes=universe if include_singletons else ()
    )

    runtime_seconds = time.perf_counter() - started

    input_tokens = sum(j.input_tokens for j in judgements)
    output_tokens = sum(j.output_tokens for j in judgements)
    cost = estimate_cost(input_tokens, output_tokens)

    relation_counts: dict[str, int] = {}
    for judgement in judgements:
        key = judgement.relation or "parse_error"
        relation_counts[key] = relation_counts.get(key, 0) + 1

    dense_available = all(cs.dense_available for cs in candidate_sets)
    dense_reason = next(
        (
            cs.dense_unavailable_reason
            for cs in candidate_sets
            if cs.dense_unavailable_reason
        ),
        None,
    )

    log = build_run_log(
        candidate_count=len(pairs),
        number_of_llm_calls=len(judgements),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=cost.total_cost_usd,
        runtime_seconds=runtime_seconds,
        accepted_match_edges=edges,
        cluster_output=clusters.as_dict(),
        retrieved_pairs=pairs,
        gold=gold_pairs,
        estimated_cost_is_placeholder=cost.pricing_is_placeholder,
        n_seeds=len(seeds),
        n_parse_failures=sum(1 for j in judgements if not j.parse_ok),
        dense_route_available=dense_available,
        dense_unavailable_reason=dense_reason,
        relation_counts=relation_counts,
    )

    return B8Result(
        clusters=clusters,
        judgements=judgements,
        candidate_sets=candidate_sets,
        log=log,
    )
