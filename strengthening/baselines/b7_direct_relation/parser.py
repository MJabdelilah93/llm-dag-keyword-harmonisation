"""Strict parser for B7 raw model responses.

Turns a model's raw text into a validated ``{relation, justification}``
record. Parsing is STRICT by design:

  * malformed JSON is a parse error,
  * an invalid ``relation`` enum value is a parse error,
  * a missing ``relation`` field is a parse error,
  * an unexpected extra field is a parse error.

A failure is NEVER silently coerced into a default relation (coercing an
unreadable response to ``other`` would quietly manufacture a non-match and
bias the baseline). Callers get a typed error result, or an exception if they
prefer to fail loudly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

_MARKDOWN_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _strip_markdown_fence(text: str) -> str:
    """Strip a wrapping ```json ... ``` (or bare ``` ... ```) fence, if
    present. The B7 prompt explicitly instructs "no code fences", but real
    model output sometimes adds one anyway despite that instruction --
    this is a decode-robustness fix only, applied before JSON parsing; it
    changes no scientific behaviour (label set, confidence, guard, prompt)
    and a fence-free response is returned unchanged."""
    match = _MARKDOWN_FENCE_RE.match(text.strip())
    return match.group(1).strip() if match else text


class ParseErrorKind(str, Enum):
    """The kinds of B7 response failure that are distinguished."""

    #: The response text was not valid JSON at all.
    MALFORMED_JSON = "malformed_json"
    #: Valid JSON, but not a JSON object at the top level.
    NOT_AN_OBJECT = "not_an_object"
    #: Valid JSON object, but the required ``relation`` field is absent.
    MISSING_FIELD = "missing_field"
    #: ``relation`` was present but not one of the four permitted values.
    INVALID_ENUM_VALUE = "invalid_enum_value"
    #: A field had the wrong JSON type.
    WRONG_TYPE = "wrong_type"
    #: An unexpected additional property was present.
    ADDITIONAL_PROPERTY = "additional_property"
    #: The response was empty / whitespace only.
    EMPTY_RESPONSE = "empty_response"


class B7ParseError(ValueError):
    """Raised by :func:`parse_b7_response_strict` on any parse failure."""

    def __init__(
        self,
        message: str,
        *,
        kind: ParseErrorKind,
        raw_text: str,
        field_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.raw_text = raw_text
        self.field_name = field_name


@dataclass(frozen=True)
class B7Record:
    """A successfully parsed B7 response."""

    relation: str
    justification: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"relation": self.relation, "justification": self.justification}


@dataclass(frozen=True)
class ParseResult:
    """Typed outcome of parsing one raw B7 response.

    Exactly one of :attr:`record` / :attr:`error_kind` is populated. Check
    :attr:`ok` before reading :attr:`record`.
    """

    ok: bool
    record: B7Record | None = None
    error_kind: ParseErrorKind | None = None
    error_message: str | None = None
    error_field: str | None = None
    raw_text: str = field(default="", repr=False)

    @property
    def relation(self) -> str | None:
        """The parsed relation, or ``None`` when parsing failed.

        Note that this is ``None`` rather than a fallback label: a failed
        parse has no relation, it is not an ``other``.
        """

        return self.record.relation if self.record is not None else None


def parse_b7_response(raw_text: str) -> ParseResult:
    """Parse a raw B7 model response into a :class:`ParseResult`.

    Never raises for a bad response; returns a failed :class:`ParseResult`
    carrying a typed :class:`ParseErrorKind` instead.
    """

    # Imported here rather than at module scope so that `parser` stays usable
    # even if callers only want the error taxonomy.
    from .schema import SchemaValidationError, validate_b7_payload

    if raw_text is None or not str(raw_text).strip():
        return ParseResult(
            ok=False,
            error_kind=ParseErrorKind.EMPTY_RESPONSE,
            error_message="response text was empty or whitespace only",
            raw_text=raw_text or "",
        )

    try:
        payload = json.loads(_strip_markdown_fence(raw_text))
    except (json.JSONDecodeError, TypeError) as exc:
        return ParseResult(
            ok=False,
            error_kind=ParseErrorKind.MALFORMED_JSON,
            error_message=f"response was not valid JSON: {exc}",
            raw_text=raw_text,
        )

    try:
        validated = validate_b7_payload(payload)
    except SchemaValidationError as exc:
        return ParseResult(
            ok=False,
            error_kind=ParseErrorKind(exc.reason),
            error_message=str(exc),
            error_field=exc.field,
            raw_text=raw_text,
        )

    justification = validated.get("justification")
    return ParseResult(
        ok=True,
        record=B7Record(relation=validated["relation"], justification=justification),
        raw_text=raw_text,
    )


def parse_b7_response_strict(raw_text: str) -> B7Record:
    """Like :func:`parse_b7_response` but raises :class:`B7ParseError`."""

    result = parse_b7_response(raw_text)
    if not result.ok:
        assert result.error_kind is not None  # narrowing for type checkers
        raise B7ParseError(
            result.error_message or "B7 response could not be parsed",
            kind=result.error_kind,
            raw_text=result.raw_text,
            field_name=result.error_field,
        )
    assert result.record is not None
    return result.record
