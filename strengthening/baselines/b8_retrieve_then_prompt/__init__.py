"""B8 -- retrieve-then-prompt hybrid baseline (SCAFFOLD + MOCKS ONLY).

Pipeline: lexical anchoring + dense retrieval -> union/de-dup -> B7's four-way
relation comparator per candidate pair -> connected components over the
``same_as`` edges only.

Like B7, B8 is deliberately SIMPLER than the M7 system it is compared against:
no ``uncertain`` output, no guard, no abstention routing, no contradiction
check.

Nothing here calls a live model. The comparator is B7's
:class:`~...b7_direct_relation.client.MockB7Client`; a real-mode
:class:`~...b7_direct_relation.client.B7Client` raises ``NotImplementedError``
before any request could be issued. Embedding is forced offline
(``HF_HUB_OFFLINE=1``) and degrades to a clearly-flagged "embedding
unavailable" mode when the local cache is absent.
"""

from __future__ import annotations

from .candidate_union import Candidate, CandidateSet, dedupe_pairs, union_candidates
from .clustering import (
    ClusterOutput,
    UnionFind,
    component_size_distribution,
    connected_components,
)
from .dense_retrieval import (
    EMBEDDING_MODEL_NAME,
    ROUTE_DENSE,
    DenseRetrievalResult,
    Neighbour,
    dense_retrieve,
    embedding_available,
)
from .lexical_anchor import (
    ROUTE_LEXICAL,
    LexicalAnchorResult,
    lexical_anchor,
    lexical_anchor_pairs,
)
from .logging_hooks import B8RunLog, build_run_log, candidate_retrieval_recall
from .normalisation import EXCLUDED_BY_POLICY, NORMALISATION_STEPS, legacy_normalise
from .pipeline import B8Result, retrieve_candidates, run_b8_pipeline
from .relation_classification import (
    MATCH_RELATION,
    PairJudgement,
    accepted_match_edges,
    classify_pair,
    classify_pairs,
)

__all__ = [
    "B8Result",
    "B8RunLog",
    "Candidate",
    "CandidateSet",
    "ClusterOutput",
    "DenseRetrievalResult",
    "EMBEDDING_MODEL_NAME",
    "EXCLUDED_BY_POLICY",
    "LexicalAnchorResult",
    "MATCH_RELATION",
    "NORMALISATION_STEPS",
    "Neighbour",
    "PairJudgement",
    "ROUTE_DENSE",
    "ROUTE_LEXICAL",
    "UnionFind",
    "accepted_match_edges",
    "build_run_log",
    "candidate_retrieval_recall",
    "classify_pair",
    "classify_pairs",
    "component_size_distribution",
    "connected_components",
    "dedupe_pairs",
    "dense_retrieve",
    "embedding_available",
    "legacy_normalise",
    "lexical_anchor",
    "lexical_anchor_pairs",
    "retrieve_candidates",
    "run_b8_pipeline",
    "union_candidates",
]
