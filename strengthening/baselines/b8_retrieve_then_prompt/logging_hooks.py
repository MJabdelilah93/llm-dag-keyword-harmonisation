"""B8 logging hooks.

Plain dataclasses / dict-returning functions. Nothing here is wired to any
real storage backend -- the pipeline fills a :class:`B8RunLog` and hands it
back to the caller, who decides what to do with it.

The gold-dependent field is honest about its own unavailability:
:func:`candidate_retrieval_recall` accepts ``gold=None`` and returns ``None``.
This task never touches real gold retrieval annotations, so in practice it
always returns ``None``. It must never fabricate a number in that state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


def candidate_retrieval_recall(
    retrieved_pairs: Iterable[tuple[str, str]],
    gold: Iterable[tuple[str, str]] | None = None,
) -> float | None:
    """Fraction of gold-relevant pairs that candidate generation surfaced.

    Returns ``None`` when ``gold is None`` -- i.e. when no gold retrieval
    annotations exist yet. That is the current state of this project, so
    ``None`` is the expected value, and it means "not estimable", NOT "zero".

    Pairs are compared unordered: ``(a, b)`` matches gold ``(b, a)``.
    """

    if gold is None:
        return None

    gold_set = {frozenset(pair) for pair in gold}
    if not gold_set:
        return None

    retrieved_set = {frozenset(pair) for pair in retrieved_pairs}
    return len(gold_set & retrieved_set) / len(gold_set)


@dataclass
class B8RunLog:
    """Instrumentation for one B8 pipeline run.

    ``candidate_retrieval_recall`` is ``None`` whenever gold retrieval
    annotations are unavailable; every other field is directly measurable.
    """

    candidate_count: int = 0
    candidate_retrieval_recall: float | None = None
    number_of_llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tokens: int = 0
    estimated_cost: float | None = None
    #: ``True`` when ``estimated_cost`` was derived from the placeholder
    #: pricing table, which is the only table available in this task.
    estimated_cost_is_placeholder: bool = True
    runtime_seconds: float = 0.0
    accepted_match_edges: list[tuple[str, str]] = field(default_factory=list)
    cluster_output: dict[str, Any] | None = None

    # --- diagnostics that are not part of the required field list ----------
    n_seeds: int = 0
    n_parse_failures: int = 0
    dense_route_available: bool = True
    dense_unavailable_reason: str | None = None
    relation_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_count": self.candidate_count,
            "candidate_retrieval_recall": self.candidate_retrieval_recall,
            "number_of_llm_calls": self.number_of_llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens": self.tokens,
            "estimated_cost": self.estimated_cost,
            "estimated_cost_is_placeholder": self.estimated_cost_is_placeholder,
            "runtime_seconds": self.runtime_seconds,
            "accepted_match_edges": [list(e) for e in self.accepted_match_edges],
            "cluster_output": self.cluster_output,
            "n_seeds": self.n_seeds,
            "n_parse_failures": self.n_parse_failures,
            "dense_route_available": self.dense_route_available,
            "dense_unavailable_reason": self.dense_unavailable_reason,
            "relation_counts": dict(self.relation_counts),
        }


def build_run_log(
    *,
    candidate_count: int,
    number_of_llm_calls: int,
    input_tokens: int,
    output_tokens: int,
    estimated_cost: float | None,
    runtime_seconds: float,
    accepted_match_edges: Sequence[tuple[str, str]],
    cluster_output: dict[str, Any] | None,
    retrieved_pairs: Sequence[tuple[str, str]] = (),
    gold: Iterable[tuple[str, str]] | None = None,
    **extra: Any,
) -> B8RunLog:
    """Assemble a :class:`B8RunLog` from the pipeline's measurements."""

    log = B8RunLog(
        candidate_count=candidate_count,
        candidate_retrieval_recall=candidate_retrieval_recall(retrieved_pairs, gold),
        number_of_llm_calls=number_of_llm_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tokens=input_tokens + output_tokens,
        estimated_cost=estimated_cost,
        runtime_seconds=runtime_seconds,
        accepted_match_edges=[tuple(e) for e in accepted_match_edges],
        cluster_output=cluster_output,
    )
    for key, value in extra.items():
        if hasattr(log, key):
            setattr(log, key, value)
    return log
