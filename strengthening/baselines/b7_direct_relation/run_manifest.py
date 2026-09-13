"""B7 run manifest.

Records exactly what a B7 run was configured to do, so that any output can be
traced back to a model pin, a prompt version and a mode. ``mode`` DEFAULTS TO
``"mock"``: a manifest that says "real" has to be asked for explicitly, and in
this task nothing may set it (see :mod:`.client`).

This module also owns :data:`RELATION_TO_M7_BINARY`, the documented mapping
from B7's four-way relation output down to the M7 binary comparison. B7 itself
never applies that mapping -- it is published here for the LATER evaluation
step to import, so that the projection is defined in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Final, Mapping

from .client import B7_INTENDED_TEMPERATURE, B7_MODEL_ID, MODE_MOCK, MODE_REAL
from .prompt_builder import PROMPT_VERSION, RELATION_LABELS

#: Mapping from B7's four-way relation label to the M7 binary comparison
#: label, used LATER by the evaluation code -- NOT computed by B7 itself.
#:
#: Only ``same_as`` projects to ``match``. ``broader`` and ``narrower`` are
#: explicitly non-matches: a hierarchical relation is not an equivalence for
#: harmonisation purposes, and collapsing it into one would merge distinct
#: concepts. ``other`` is likewise a non-match.
#:
#: Note the asymmetry with the overall M7 task: there is no ``uncertain``
#: target here, because B7 has no abstention label to project from.
RELATION_TO_M7_BINARY: Final[Mapping[str, str]] = {
    "same_as": "match",
    "broader": "non-match",
    "narrower": "non-match",
    "other": "non-match",
}

# Guard against the mapping and the label list drifting apart.
assert set(RELATION_TO_M7_BINARY) == set(RELATION_LABELS), (
    "RELATION_TO_M7_BINARY must cover exactly the four B7 relation labels"
)


@dataclass(frozen=True)
class B7RunManifest:
    """Provenance record for one B7 run (real or, in this task, mock)."""

    model_id: str = B7_MODEL_ID
    #: Documented as the intended legacy-consistent setting. Recorded, not applied.
    temperature: float = B7_INTENDED_TEMPERATURE
    prompt_version: str = PROMPT_VERSION
    #: ``"mock"`` or ``"real"``. Defaults to ``"mock"``.
    mode: str = MODE_MOCK
    timestamp: str = ""
    relation_to_m7_binary: Mapping[str, str] = field(
        default_factory=lambda: dict(RELATION_TO_M7_BINARY)
    )
    notes: str = (
        "B7 scaffold. Real API execution is not authorised; the pinned model "
        "id is recorded for provenance only and is never dispatched."
    )

    def __post_init__(self) -> None:
        if self.mode not in (MODE_MOCK, MODE_REAL):
            raise ValueError(
                f"mode must be {MODE_MOCK!r} or {MODE_REAL!r}, got {self.mode!r}"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "temperature": self.temperature,
            "prompt_version": self.prompt_version,
            "mode": self.mode,
            "timestamp": self.timestamp,
            "relation_to_m7_binary": dict(self.relation_to_m7_binary),
            "notes": self.notes,
        }


def build_run_manifest(
    *,
    mode: str = MODE_MOCK,
    model_id: str = B7_MODEL_ID,
    temperature: float = B7_INTENDED_TEMPERATURE,
    prompt_version: str = PROMPT_VERSION,
    timestamp: str | None = None,
) -> B7RunManifest:
    """Build a :class:`B7RunManifest`.

    ``timestamp`` defaults to the current UTC time in ISO-8601 form; pass an
    explicit value to make a manifest byte-reproducible in a test.
    """

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    return B7RunManifest(
        model_id=model_id,
        temperature=temperature,
        prompt_version=prompt_version,
        mode=mode,
        timestamp=timestamp,
    )


def map_relation_to_m7_binary(relation: str) -> str:
    """Project one B7 relation label onto the M7 binary comparison label.

    Raises :class:`KeyError` for an unknown relation rather than defaulting to
    ``non-match``: an unmappable relation is a bug, not a non-match.
    """

    return RELATION_TO_M7_BINARY[relation]
