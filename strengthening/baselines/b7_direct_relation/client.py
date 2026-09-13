"""B7 clients.

Two clients live here:

* :class:`B7Client` -- the "real" client. ``classify()`` still raises
  :class:`NotImplementedError` on its first statement for every EXISTING
  call site (all of which call it with exactly two positional arguments)
  because the new ``execute_paid`` keyword-only parameter defaults to
  ``False``. Only an explicit ``classify(a, b, execute_paid=True)`` call
  proceeds past that check -- and even then, the actual Anthropic
  transport lives in the sibling module :mod:`.real_client`, imported
  lazily from inside ``classify()`` ONLY after the ``execute_paid`` check
  (and, inside :mod:`.real_client`, an ``ANTHROPIC_API_KEY`` presence
  check) have both passed. This file itself never imports an LLM SDK.
* :class:`MockB7Client` -- a deterministic offline stand-in used by the tests
  and by the B8 pipeline. Unchanged.

SAFETY PROPERTIES OF THIS MODULE (asserted by the test-suite):

* it does not import ``anthropic`` or any other LLM SDK at module scope,
* it does not import ``requests``, ``httpx``, ``urllib`` or ``socket``,
* it never reads ``ANTHROPIC_API_KEY`` or any other credential environment
  variable itself (that check lives in :mod:`.real_client`, reached only
  after ``execute_paid=True`` is passed explicitly), and contains no API
  key -- real or invented. Where a key-shaped string is structurally
  required, the obviously-fake sentinel :data:`MOCK_API_KEY_SENTINEL` is
  used.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Mapping

from .parser import ParseResult, parse_b7_response
from .prompt_builder import PROMPT_VERSION, RELATION_LABELS, build_b7_prompt

#: Pinned model identifier: same pinned primary LLM family as the legacy M7
#: comparison; DO NOT CALL -- placeholder for a future authorised run.
#:
#: This is a provenance constant only. It is never used to construct a client,
#: never sent anywhere, and no code in this repository dispatches on it. It is
#: recorded verbatim from the legacy M7 run so that a future, separately
#: authorised execution can be matched against the legacy configuration. (Note
#: for whoever performs that run: the dated form below is the legacy snapshot
#: identifier as recorded at legacy-run time; confirm the currently valid
#: model identifier against the provider's own model listing before use rather
#: than assuming this string still resolves.)
B7_MODEL_ID: Final[str] = "claude-haiku-4-5-20251001"

#: Intended sampling temperature, documented for legacy consistency. Recorded
#: in the run manifest; never applied here because nothing is ever called.
B7_INTENDED_TEMPERATURE: Final[float] = 0.0

#: Obviously-fake sentinel used wherever a credential-shaped string is
#: structurally required. This is NOT a key and must never be replaced with a
#: real one in version control.
MOCK_API_KEY_SENTINEL: Final[str] = "MOCK-NO-KEY"

MODE_MOCK: Final[str] = "mock"
MODE_REAL: Final[str] = "real"

_NOT_AUTHORISED_MESSAGE: Final[str] = (
    "B7 real API calls are not authorised in this task"
)


@dataclass(frozen=True)
class B7Response:
    """One B7 comparator response.

    ``raw_text`` is the model's response text exactly as it would arrive over
    the wire -- a JSON document as requested by the prompt. It is deliberately
    left unparsed so that :mod:`.parser` remains the single strict entry point
    for turning text into a validated record.

    ``input_tokens`` / ``output_tokens`` are counts only. In mock mode they are
    deterministic estimates, clearly flagged by ``mode == "mock"``; they are
    NOT measurements of a real API response.
    """

    keyword_a: str
    keyword_b: str
    raw_text: str
    model_id: str = B7_MODEL_ID
    mode: str = MODE_MOCK
    prompt_version: str = PROMPT_VERSION
    input_tokens: int = 0
    output_tokens: int = 0

    def parsed(self) -> ParseResult:
        """Strictly parse :attr:`raw_text` into a :class:`ParseResult`."""

        return parse_b7_response(self.raw_text)


class B7Client:
    """Real-mode B7 client. A SCAFFOLD -- it never calls anything.

    Constructing this object is harmless: it stores nothing but the pinned
    model id and the intended temperature. Every classification entry point
    raises :class:`NotImplementedError`, so there is no code path from here to
    a network socket. There is no ``api_key`` parameter and no environment
    lookup, by design.
    """

    #: Exposed on the class so callers/tests can reference the pin without
    #: instantiating anything.
    model_id: Final[str] = B7_MODEL_ID
    mode: Final[str] = MODE_REAL

    def __init__(
        self,
        *,
        model_id: str = B7_MODEL_ID,
        temperature: float = B7_INTENDED_TEMPERATURE,
    ) -> None:
        self._model_id = model_id
        self._temperature = temperature

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"B7Client(model_id={self._model_id!r}, mode={MODE_REAL!r}, "
            "authorised=False)"
        )

    def build_request(self, keyword_a: str, keyword_b: str) -> dict[str, object]:
        """Return the request payload that a future authorised run *would* send.

        Provided so that the prompt/parameters can be inspected, diffed and
        version-controlled without any possibility of dispatching them. This
        method performs no I/O.
        """

        prompt = build_b7_prompt(keyword_a, keyword_b)
        return {
            "model": self._model_id,
            "temperature": self._temperature,
            "system": prompt.system,
            "messages": [{"role": "user", "content": prompt.user}],
            "prompt_version": prompt.prompt_version,
        }

    def classify(
        self, keyword_a: str, keyword_b: str, *, execute_paid: bool = False
    ) -> B7Response:
        """Raises unless ``execute_paid=True`` is passed explicitly.

        Every existing call site in this repository (B8's pipeline
        included) calls ``classify(a, b)`` with exactly two positional
        arguments, so ``execute_paid`` defaults to ``False`` there and
        this raises on the first statement, before any request object,
        transport or credential could be touched -- byte-identical to the
        prior unconditional-raise behaviour for all of them.

        Only an explicit ``classify(a, b, execute_paid=True)`` call
        proceeds past the check, and even then the real Anthropic
        transport is imported lazily from :mod:`.real_client` -- which
        itself refuses (raising, without importing any SDK) if
        ``ANTHROPIC_API_KEY`` is not set. This module never calls the API
        itself; it only ever delegates, once both gates have passed.
        """

        if not execute_paid:
            raise NotImplementedError(_NOT_AUTHORISED_MESSAGE)
        from .real_client import call_real_b7_api

        return call_real_b7_api(self._model_id, self._temperature, keyword_a, keyword_b)


def _pair_digest(keyword_a: str, keyword_b: str) -> int:
    """Stable, process-independent digest of an ordered keyword pair.

    ``hashlib`` is used rather than the builtin :func:`hash` because string
    hashing is randomised per process (``PYTHONHASHSEED``), which would make
    "deterministic" mock output reproducible only within a single run.
    """

    payload = f"{keyword_a}\x1f{keyword_b}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _mock_normalise(text: str) -> str:
    """Casefold + whitespace-collapse, used only to make mock output sensible."""

    return " ".join(str(text).split()).casefold()


class MockB7Client:
    """Deterministic offline stand-in for :class:`B7Client`.

    Returns canned JSON responses keyed off a stable SHA-256 digest of the
    ordered input pair, so repeated calls with the same input -- in the same
    process or in a different one, on a different machine, on a different day
    -- return byte-identical text.

    Two deterministic rules are applied, in order:

    1. an explicit ``canned_responses`` override for a specific pair, if given;
    2. otherwise, if the two keywords are equal after casefolding and
       whitespace collapse, ``same_as``; else a digest-selected label from
       :data:`~.prompt_builder.RELATION_LABELS`.

    This makes mock output stable AND minimally sensible (identical strings
    always come back as ``same_as``), which is what the B8 pipeline test needs.
    It is a stub, not a model: nothing here is a claim about real behaviour.
    """

    mode: Final[str] = MODE_MOCK

    def __init__(
        self,
        *,
        canned_responses: Mapping[tuple[str, str], str] | None = None,
        model_id: str = B7_MODEL_ID,
        include_justification: bool = True,
    ) -> None:
        self._canned = dict(canned_responses or {})
        self._model_id = model_id
        self._include_justification = include_justification
        self.call_count = 0

    def relation_for(self, keyword_a: str, keyword_b: str) -> str:
        """Return the deterministic relation label for one pair."""

        override = self._canned.get((keyword_a, keyword_b))
        if override is not None:
            return override

        if _mock_normalise(keyword_a) == _mock_normalise(keyword_b):
            return "same_as"

        index = _pair_digest(keyword_a, keyword_b) % len(RELATION_LABELS)
        return RELATION_LABELS[index]

    def classify(self, keyword_a: str, keyword_b: str) -> B7Response:
        """Return a deterministic canned :class:`B7Response`.

        Performs no I/O of any kind.
        """

        self.call_count += 1
        relation = self.relation_for(keyword_a, keyword_b)

        # Built with json.dumps-equivalent ordering by hand so the canned text
        # is byte-stable and readable in test failures.
        if self._include_justification:
            justification = f"deterministic mock response for relation {relation}"
            raw_text = (
                '{"relation": "' + relation + '", '
                '"justification": "' + justification + '"}'
            )
        else:
            raw_text = '{"relation": "' + relation + '"}'

        prompt = build_b7_prompt(keyword_a, keyword_b)
        return B7Response(
            keyword_a=keyword_a,
            keyword_b=keyword_b,
            raw_text=raw_text,
            model_id=self._model_id,
            mode=MODE_MOCK,
            prompt_version=prompt.prompt_version,
            # Deterministic, clearly-fake token estimates (~4 chars/token).
            # Not a measurement.
            input_tokens=(len(prompt.system) + len(prompt.user)) // 4,
            output_tokens=max(1, len(raw_text) // 4),
        )
