"""Stage 9 metric modules for the M7 strengthening protocol.

Pure computation only. Nothing in this package performs network access,
reads credentials, or calls any external service. Every module here is
deterministic given its inputs (bootstrap resampling is seeded explicitly).

Shared conventions
------------------
Label vocabulary
    The three allowed gold/predicted label strings are exactly
    ``"match"``, ``"non-match"`` (with a hyphen) and ``"uncertain"``.
    They are read from ``strengthening/config/protocol_v1.yaml`` at import
    time, with a hard-coded fallback if that file is missing or unreadable.

Random seed
    ``DEFAULT_SEED`` is read from ``random_seed`` in the same YAML file,
    falling back to ``FALLBACK_SEED = 42``. Import never raises because of a
    missing or malformed config file.

Zero denominators
    ``binary``, ``three_way``, ``selective`` and ``cluster`` return ``0.0``
    for a metric whose denominator is zero (documented per function).
    ``retrieval`` instead returns ``None`` whenever a metric depends on gold
    annotations that do not exist yet -- that is a *different* situation
    ("not estimable") and is deliberately signalled differently so that a
    missing-gold result can never be mistaken for a real score of zero.

Confidence scores
    Where a per-item confidence score appears it is the model's own
    *raw / self-reported* confidence. No formal calibration guarantee is
    claimed or implied by any function in this package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = [
    "ALLOWED_LABELS",
    "DEFAULT_ABSTAIN_LABELS",
    "DEFAULT_SEED",
    "FALLBACK_ALLOWED_LABELS",
    "FALLBACK_SEED",
    "LABEL_MATCH",
    "LABEL_NON_MATCH",
    "LABEL_UNCERTAIN",
    "PROTOCOL_CONFIG_PATH",
    "load_allowed_labels",
    "load_protocol_seed",
]

#: Hard-coded fallbacks used when the protocol YAML cannot be read.
FALLBACK_SEED = 42
FALLBACK_ALLOWED_LABELS: tuple[str, ...] = ("match", "non-match", "uncertain")

#: Location of the shared, read-only protocol configuration.
PROTOCOL_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "protocol_v1.yaml"

LABEL_MATCH = "match"
LABEL_NON_MATCH = "non-match"
LABEL_UNCERTAIN = "uncertain"

#: Predicted labels that count as an abstention (i.e. "not answered").
DEFAULT_ABSTAIN_LABELS: frozenset[str] = frozenset({LABEL_UNCERTAIN})


def _read_protocol_config(path: Path | str | None = None) -> dict[str, Any]:
    """Best-effort read of the protocol YAML. Returns ``{}`` on any failure.

    Deliberately swallows every exception: importing a metric module must
    never fail because a configuration file is absent, unreadable, or
    malformed.
    """
    candidate = Path(path) if path is not None else PROTOCOL_CONFIG_PATH
    try:
        import yaml  # local import so a missing PyYAML cannot break import

        with candidate.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except Exception:  # noqa: BLE001 - intentional: never crash on import
        return {}
    return loaded if isinstance(loaded, dict) else {}


def load_protocol_seed(path: Path | str | None = None) -> int:
    """Return ``random_seed`` from the protocol YAML, or ``FALLBACK_SEED``.

    Never raises. A non-integer or missing value falls back to 42.
    """
    config = _read_protocol_config(path)
    value = config.get("random_seed", FALLBACK_SEED)
    try:
        return int(value)
    except (TypeError, ValueError):
        return FALLBACK_SEED


def load_allowed_labels(path: Path | str | None = None) -> tuple[str, ...]:
    """Return ``labels.allowed`` from the protocol YAML, or the fallback tuple.

    Never raises. The returned tuple preserves the order declared in the
    configuration file.
    """
    config = _read_protocol_config(path)
    labels = config.get("labels")
    if isinstance(labels, dict):
        allowed = labels.get("allowed")
        if isinstance(allowed, (list, tuple)) and allowed:
            coerced = tuple(str(item) for item in allowed)
            if all(coerced):
                return coerced
    return FALLBACK_ALLOWED_LABELS


#: Protocol random seed (42 unless the config says otherwise).
DEFAULT_SEED: int = load_protocol_seed()

#: The three allowed label strings, in protocol order.
ALLOWED_LABELS: tuple[str, ...] = load_allowed_labels()
