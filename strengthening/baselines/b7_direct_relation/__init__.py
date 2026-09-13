"""B7 -- direct scholarly semantic-relation LLM comparator (SCAFFOLD ONLY).

B7 is a comparator baseline for the M7 study. Given two keyword strings it
asks a single LLM call for exactly one of four scholarly relation labels:

    same_as | broader | narrower | other

B7 is deliberately SIMPLER than the M7 system under evaluation:

  * B7 has NO ``uncertain`` label.
  * B7 has NO guard, NO abstention routing and NO contradiction check.
  * B7 asks for no confidence score of any kind.

The three-label semantic task (match / non-match / uncertain) is the OVERALL
M7 task; it is NOT B7's task. Do not blur the two. The four-way relation
output is mapped down to the M7 binary comparison *later*, by the evaluation
code, using :data:`run_manifest.RELATION_TO_M7_BINARY` -- B7 itself never
computes that mapping.

NO REAL API CALLS ARE MADE ANYWHERE IN THIS PACKAGE. ``B7Client.classify`` in
"real" mode raises ``NotImplementedError``. Nothing here imports an LLM SDK,
opens a socket, or reads an API-key environment variable. Testing uses
:class:`client.MockB7Client`, which returns deterministic canned responses
derived from a stable hash of the input pair.
"""

from __future__ import annotations

from .client import B7_MODEL_ID, B7Client, MockB7Client
from .cost_logging import PLACEHOLDER_PRICING_USD_PER_MTOK, estimate_cost_usd
from .parser import B7ParseError, ParseErrorKind, ParseResult, parse_b7_response
from .prompt_builder import PROMPT_VERSION, RELATION_LABELS, build_b7_prompt
from .run_manifest import RELATION_TO_M7_BINARY, B7RunManifest, build_run_manifest
from .schema import B7_RELATION_SCHEMA, SchemaValidationError, validate_b7_payload

__all__ = [
    "B7_MODEL_ID",
    "B7_RELATION_SCHEMA",
    "B7Client",
    "B7ParseError",
    "B7RunManifest",
    "MockB7Client",
    "PLACEHOLDER_PRICING_USD_PER_MTOK",
    "PROMPT_VERSION",
    "RELATION_LABELS",
    "RELATION_TO_M7_BINARY",
    "ParseErrorKind",
    "ParseResult",
    "SchemaValidationError",
    "build_b7_prompt",
    "build_run_manifest",
    "estimate_cost_usd",
    "parse_b7_response",
    "validate_b7_payload",
]
