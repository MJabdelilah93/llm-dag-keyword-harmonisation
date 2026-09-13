"""B7 response schema and its validator.

The authoritative schema document lives beside this module in
``relation_schema.json``; it is loaded at import time so the JSON file and the
Python constant can never drift apart.

The schema has EXACTLY ONE required field, ``relation``, whose value must be
one of ``same_as`` / ``broader`` / ``narrower`` / ``other``, plus an OPTIONAL
free-text ``justification`` string. There is deliberately:

  * no ``confidence`` field (B7 requests no score of any kind), and
  * no ``uncertain`` enum value (B7 has no abstention label).

``jsonschema`` is not a dependency of this project, so :func:`validate_b7_payload`
implements the small subset of JSON Schema that this document actually uses
(``type: object``, ``properties``, per-property ``type``/``enum``,
``required``, ``additionalProperties: false``). Validation is strict: it never
coerces a bad value into a default.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Mapping

SCHEMA_PATH: Final[Path] = Path(__file__).with_name("relation_schema.json")

#: The parsed schema document. Treated as read-only.
B7_RELATION_SCHEMA: Final[Mapping[str, Any]] = json.loads(
    SCHEMA_PATH.read_text(encoding="utf-8")
)

#: Convenience view of the permitted enum values, taken from the schema itself.
ALLOWED_RELATIONS: Final[tuple[str, ...]] = tuple(
    B7_RELATION_SCHEMA["properties"]["relation"]["enum"]
)

_JSON_TYPES: Final[Mapping[str, type | tuple[type, ...]]] = {
    "string": str,
    "object": dict,
    "array": list,
    "boolean": bool,
    "number": (int, float),
    "integer": int,
}


class SchemaValidationError(ValueError):
    """Raised when a candidate payload does not satisfy the B7 schema.

    Attributes
    ----------
    reason:
        A short machine-friendly reason code, one of ``not_an_object``,
        ``missing_field``, ``additional_property``, ``wrong_type`` or
        ``invalid_enum_value``.
    field:
        The offending field name, when applicable.
    """

    def __init__(self, message: str, *, reason: str, field: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.field = field


def validate_b7_payload(payload: Any) -> dict[str, Any]:
    """Validate ``payload`` against the B7 schema and return it unchanged.

    Raises :class:`SchemaValidationError` on any violation. Never repairs,
    defaults or coerces a value.
    """

    schema = B7_RELATION_SCHEMA

    expected_type = _JSON_TYPES[schema["type"]]
    if not isinstance(payload, expected_type) or isinstance(payload, bool):
        raise SchemaValidationError(
            f"expected a JSON object, got {type(payload).__name__}",
            reason="not_an_object",
        )

    properties: Mapping[str, Any] = schema["properties"]

    for field in schema.get("required", []):
        if field not in payload:
            raise SchemaValidationError(
                f"missing required field {field!r}",
                reason="missing_field",
                field=field,
            )

    if schema.get("additionalProperties") is False:
        for key in payload:
            if key not in properties:
                raise SchemaValidationError(
                    f"additional property {key!r} is not permitted",
                    reason="additional_property",
                    field=key,
                )

    for field, spec in properties.items():
        if field not in payload:
            continue
        value = payload[field]

        if "type" in spec:
            wanted = _JSON_TYPES[spec["type"]]
            if not isinstance(value, wanted) or (
                spec["type"] != "boolean" and isinstance(value, bool)
            ):
                raise SchemaValidationError(
                    f"field {field!r} must be of type {spec['type']}, "
                    f"got {type(value).__name__}",
                    reason="wrong_type",
                    field=field,
                )

        if "enum" in spec and value not in spec["enum"]:
            raise SchemaValidationError(
                f"field {field!r} has invalid value {value!r}; "
                f"permitted values are {list(spec['enum'])}",
                reason="invalid_enum_value",
                field=field,
            )

    return dict(payload)
