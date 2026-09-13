"""B8 stage 4 -- apply the B7 relation classifier to each candidate pair.

B8 reuses B7's comparator wholesale: same four-way relation prompt, same
strict schema, same strict parser. In this task the only client that may
actually be used is :class:`~...b7_direct_relation.client.MockB7Client`;
passing a real-mode :class:`~...b7_direct_relation.client.B7Client` raises
``NotImplementedError`` from B7 itself, which this module deliberately does
NOT catch.

Note what is absent, and must stay absent: B8 has no uncertain output, no
guard, no abstention routing and no contradiction check. A pair that fails to
parse is recorded as a parse failure and is simply not accepted as a match --
it is not routed anywhere, and it is not counted as an abstention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Iterable, Protocol, Sequence

from ..b7_direct_relation.parser import ParseErrorKind

#: The only relation that creates a match edge (see B7's documented mapping:
#: same_as -> match; broader/narrower/other -> non-match).
MATCH_RELATION: Final[str] = "same_as"


class SupportsClassify(Protocol):
    """Structural type for anything B8 will call as a comparator."""

    def classify(self, keyword_a: str, keyword_b: str) -> Any: ...


@dataclass(frozen=True)
class PairJudgement:
    """The B7 judgement for one candidate pair."""

    keyword_a: str
    keyword_b: str
    relation: str | None
    accepted_as_match: bool
    parse_ok: bool
    parse_error_kind: ParseErrorKind | None = None
    raw_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    routes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "keyword_a": self.keyword_a,
            "keyword_b": self.keyword_b,
            "relation": self.relation,
            "accepted_as_match": self.accepted_as_match,
            "parse_ok": self.parse_ok,
            "parse_error_kind": (
                self.parse_error_kind.value if self.parse_error_kind else None
            ),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "routes": list(self.routes),
        }


def classify_pair(
    client: SupportsClassify,
    keyword_a: str,
    keyword_b: str,
    *,
    routes: Sequence[str] = (),
) -> PairJudgement:
    """Classify one candidate pair with the supplied comparator client."""

    response = client.classify(keyword_a, keyword_b)
    parsed = response.parsed()

    relation = parsed.relation if parsed.ok else None
    return PairJudgement(
        keyword_a=keyword_a,
        keyword_b=keyword_b,
        relation=relation,
        accepted_as_match=(relation == MATCH_RELATION),
        parse_ok=parsed.ok,
        parse_error_kind=parsed.error_kind,
        raw_text=getattr(response, "raw_text", ""),
        input_tokens=getattr(response, "input_tokens", 0),
        output_tokens=getattr(response, "output_tokens", 0),
        routes=tuple(routes),
    )


def classify_pairs(
    client: SupportsClassify,
    pairs: Iterable[tuple[str, str]],
) -> list[PairJudgement]:
    """Classify many pairs, preserving input order."""

    return [classify_pair(client, a, b) for a, b in pairs]


def accepted_match_edges(
    judgements: Iterable[PairJudgement],
) -> list[tuple[str, str]]:
    """Return only the edges accepted as matches, in judgement order.

    ONLY a ``same_as`` relation produces an edge. ``broader`` and ``narrower``
    are hierarchical, not equivalent, and must not create one.
    """

    return [
        (j.keyword_a, j.keyword_b) for j in judgements if j.accepted_as_match
    ]
