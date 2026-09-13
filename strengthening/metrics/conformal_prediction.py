"""EXPERIMENTAL - not the primary method, disabled by default.

===========================================================================
EXPERIMENTAL SCAFFOLD. NOT WIRED INTO THE PRIMARY SELECTIVE-PREDICTION PATH.
===========================================================================

This module is an optional, opt-in sketch of a split-conformal style
threshold. It exists so the idea can be inspected and discussed; it is NOT
part of the protocol's primary selective-prediction analysis and
:mod:`strengthening.metrics.selective` never imports or calls anything here.

Every public function refuses to do any work unless the caller passes
``enabled=True`` explicitly. With the default ``enabled=False`` a
:class:`DisabledResult` is returned (or, with ``strict=True``, a
:class:`ConformalDisabledError` is raised). There is no global switch and no
configuration file entry that can flip the default.

Caveats if you do enable it
---------------------------
* The scores consumed here are the model's own RAW, SELF-REPORTED confidence
  values. They carry no distributional guarantee of any kind.
* The finite-sample coverage property normally associated with split
  conformal prediction requires exchangeability between the reserved
  tuning split and the evaluation data. That assumption has NOT been
  established for this benchmark, so no coverage guarantee is claimed,
  implied, or reportable from this scaffold.
* Treat any output as a diagnostic sketch only. Do not put it in a results
  table.

Pure computation; no network access, no credentials, no model calls.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "CONFORMAL_ENABLED_BY_DEFAULT",
    "ConformalDisabledError",
    "ConformalScaffoldResult",
    "DisabledResult",
    "conformal_score_threshold",
]

#: Hard-coded module policy. There is intentionally no way to change this
#: except by passing ``enabled=True`` at each individual call site.
CONFORMAL_ENABLED_BY_DEFAULT: bool = False

_DISABLED_REASON = (
    "conformal_prediction is an EXPERIMENTAL scaffold and is disabled by "
    "default; pass enabled=True explicitly to run it. It is not part of the "
    "primary selective-prediction path and claims no coverage guarantee."
)


class ConformalDisabledError(RuntimeError):
    """Raised when a disabled conformal entry point is called with ``strict=True``."""


@dataclass(frozen=True)
class DisabledResult:
    """Clearly-flagged 'this did nothing' result.

    Returned instead of any numbers whenever ``enabled`` is False, so a caller
    can never mistake a refusal for a computed value.
    """

    enabled: bool = False
    experimental: bool = True
    computed: bool = False
    reason: str = _DISABLED_REASON
    threshold: None = None

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return False


@dataclass(frozen=True)
class ConformalScaffoldResult:
    """Output of the opt-in scaffold. Diagnostic only; no guarantee claimed."""

    enabled: bool
    experimental: bool
    computed: bool
    alpha: float
    threshold: float
    n_reserved: int
    quantile_rank: int
    guarantee_claimed: bool = False
    note: str = (
        "EXPERIMENTAL diagnostic. Exchangeability has not been established "
        "for this benchmark, so no coverage guarantee is claimed."
    )


def _refuse(strict: bool) -> DisabledResult:
    if strict:
        raise ConformalDisabledError(_DISABLED_REASON)
    return DisabledResult()


def conformal_score_threshold(
    reserved_scores: Sequence[float],
    alpha: float = 0.1,
    *,
    enabled: bool = CONFORMAL_ENABLED_BY_DEFAULT,
    strict: bool = False,
) -> ConformalScaffoldResult | DisabledResult:
    """EXPERIMENTAL, opt-in only. Split-conformal style score threshold.

    Parameters
    ----------
    reserved_scores:
        Non-conformity scores from a reserved (held-out) split. For a
        confidence score ``s`` in [0, 1] a natural non-conformity score is
        ``1 - s``; the caller is responsible for that transformation.
    alpha:
        Nominal miscoverage level in (0, 1).
    enabled:
        MUST be passed as ``True`` explicitly, otherwise the function does
        nothing and returns :class:`DisabledResult`.
    strict:
        When True, a disabled call raises :class:`ConformalDisabledError`
        rather than returning a flagged result.

    Returns
    -------
    :class:`DisabledResult` when ``enabled`` is False (the default), else a
    :class:`ConformalScaffoldResult`. The returned threshold is a
    diagnostic sketch: no coverage guarantee is claimed.
    """
    if not enabled:
        return _refuse(strict)

    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must lie strictly in (0, 1), got {alpha!r}")
    scores = sorted(float(s) for s in reserved_scores)
    n = len(scores)
    if n == 0:
        raise ValueError("reserved_scores must be non-empty when enabled=True")

    # Standard split-conformal rank: ceil((n + 1) * (1 - alpha)), clipped.
    rank = min(n, max(1, math.ceil((n + 1) * (1.0 - alpha))))
    threshold = scores[rank - 1]

    return ConformalScaffoldResult(
        enabled=True,
        experimental=True,
        computed=True,
        alpha=float(alpha),
        threshold=float(threshold),
        n_reserved=n,
        quantile_rank=rank,
    )
