"""B7 prompt construction.

Builds the system + user prompt for the B7 direct scholarly semantic-relation
comparator. The prompt asks for EXACTLY ONE of four relation labels and for
strict JSON output conforming to :mod:`.schema`.

Deliberate omissions (these are the properties that keep B7 a *simple*
baseline, distinct from the M7 system under evaluation):

  * No ``uncertain`` option is offered.
  * No confidence score is requested, and none would be accepted as input to
    any M7-style guard / abstention / contradiction-check machinery, because
    B7 has no such machinery.
  * No title/abstract context is included in the primary condition. A
    clearly-labelled, DEFAULT-OFF parameter (``include_context``) is kept for
    later context-augmented experiments only.

Nothing in this module performs I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping, Sequence

#: Bump this whenever the prompt text changes; it is recorded in the run
#: manifest so that outputs stay traceable to the exact prompt that produced
#: them.
PROMPT_VERSION: Final[str] = "b7-direct-relation-v1"

#: The four permitted relation labels, in canonical order. There is
#: deliberately no ``uncertain`` label: B7 is a four-way relation classifier,
#: not the three-label M7 task.
RELATION_LABELS: Final[tuple[str, ...]] = ("same_as", "broader", "narrower", "other")

#: Relation definitions, embedded verbatim into the prompt. These strings are
#: the authoritative wording; tests assert on them.
RELATION_DEFINITIONS: Final[Mapping[str, str]] = {
    "same_as": (
        "the two strings denote the same concept for harmonisation purposes, "
        "including ordinary spelling, formatting, singular/plural, and "
        "unambiguous acronym/expanded-form variants."
    ),
    "broader": "Keyword A denotes a concept broader in scope than Keyword B.",
    "narrower": "Keyword A denotes a concept narrower in scope than Keyword B.",
    "other": (
        "they are distinct concepts and neither is a simple broader/narrower "
        "relation."
    ),
}

_SYSTEM_PROMPT: Final[str] = (
    "You are a bibliometric subject specialist classifying the scholarly "
    "semantic relation between two author-supplied keyword strings.\n"
    "\n"
    "Assign EXACTLY ONE of the following four relation labels:\n"
    "\n"
    f"- same_as: {RELATION_DEFINITIONS['same_as']}\n"
    f"- broader: {RELATION_DEFINITIONS['broader']}\n"
    f"- narrower: {RELATION_DEFINITIONS['narrower']}\n"
    f"- other: {RELATION_DEFINITIONS['other']}\n"
    "\n"
    "The relation is directional: 'broader' and 'narrower' are stated from "
    "the point of view of Keyword A relative to Keyword B.\n"
    "\n"
    "You must choose one of the four labels above. Do not invent additional "
    "labels. Do not report a score, a probability, or any other numeric "
    "judgement.\n"
    "\n"
    "Respond with strict JSON only -- no prose before or after, no code "
    "fences. The JSON object must have the required key \"relation\" whose "
    'value is one of "same_as", "broader", "narrower", "other". It may '
    'additionally have an optional key "justification" whose value is a '
    "short free-text string. No other keys are permitted.\n"
    "\n"
    "Example of a well-formed response:\n"
    '{"relation": "same_as", "justification": "Plural variant of the same '
    'concept."}'
)


@dataclass(frozen=True)
class B7Prompt:
    """A built B7 prompt pair plus the metadata needed to reproduce it."""

    system: str
    user: str
    prompt_version: str = PROMPT_VERSION
    keyword_a: str = ""
    keyword_b: str = ""
    include_context: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "system": self.system,
            "user": self.user,
            "prompt_version": self.prompt_version,
            "keyword_a": self.keyword_a,
            "keyword_b": self.keyword_b,
            "include_context": self.include_context,
        }


def build_system_prompt() -> str:
    """Return the B7 system prompt (constant for a given ``PROMPT_VERSION``)."""

    return _SYSTEM_PROMPT


def build_user_prompt(
    keyword_a: str,
    keyword_b: str,
    *,
    include_context: bool = False,
    context_a: Sequence[str] | None = None,
    context_b: Sequence[str] | None = None,
) -> str:
    """Return the B7 user prompt for one keyword pair.

    Parameters
    ----------
    keyword_a, keyword_b:
        The two keyword strings to compare, verbatim. They are NOT normalised
        here -- B7 judges the strings as supplied.
    include_context:
        OPTIONAL / DISABLED BY DEFAULT. Reserved for a later
        context-augmented experiment. The primary B7 condition passes no
        title/abstract context whatsoever, so this defaults to ``False`` and
        ``context_a`` / ``context_b`` are ignored unless it is explicitly
        turned on.
    context_a, context_b:
        Title/abstract snippets, used only when ``include_context=True``.
    """

    lines = [
        f"Keyword A: {keyword_a}",
        f"Keyword B: {keyword_b}",
    ]

    if include_context:
        # OPTIONAL / NON-PRIMARY CONDITION. Not used by the primary B7 run.
        for label, context in (("A", context_a), ("B", context_b)):
            if context:
                joined = " | ".join(str(item) for item in context)
                lines.append(f"Optional context for Keyword {label}: {joined}")

    lines.append("")
    lines.append(
        "Return strict JSON with the required key \"relation\" set to exactly "
        "one of: same_as, broader, narrower, other."
    )
    return "\n".join(lines)


def build_b7_prompt(
    keyword_a: str,
    keyword_b: str,
    *,
    include_context: bool = False,
    context_a: Sequence[str] | None = None,
    context_b: Sequence[str] | None = None,
) -> B7Prompt:
    """Build the full system + user prompt pair for one keyword pair."""

    return B7Prompt(
        system=build_system_prompt(),
        user=build_user_prompt(
            keyword_a,
            keyword_b,
            include_context=include_context,
            context_a=context_a,
            context_b=context_b,
        ),
        prompt_version=PROMPT_VERSION,
        keyword_a=keyword_a,
        keyword_b=keyword_b,
        include_context=include_context,
    )
