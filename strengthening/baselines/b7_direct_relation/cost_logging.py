"""Cost-estimation hooks for B7.

These functions are PURE ARITHMETIC over token counts that the caller
supplies. They never inspect an API response, never call anything, and are
never invoked against a real response in this task.

The pricing table below is a clearly-labelled PLACEHOLDER. It has NOT been
verified against a live price list and must not be quoted as a cost figure in
any write-up. Before any authorised run, replace it with rates confirmed
against the provider's own published pricing at that time and flip
:data:`PRICING_IS_PLACEHOLDER` to ``False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

from .client import B7_MODEL_ID

# ---------------------------------------------------------------------------
# PLACEHOLDER PRICING -- NOT LIVE-VERIFIED. DO NOT CITE.
# ---------------------------------------------------------------------------

#: ``True`` for as long as the table below is unverified. Cost helpers stamp
#: this onto every estimate they return, so a placeholder-derived number can
#: never be mistaken for a real one downstream.
PRICING_IS_PLACEHOLDER: Final[bool] = True

#: Placeholder rates in US dollars per MILLION tokens, keyed by model id.
#: Units matter: these are per 1e6 tokens, not per token and not per 1e3.
PLACEHOLDER_PRICING_USD_PER_MTOK: Final[Mapping[str, Mapping[str, float]]] = {
    B7_MODEL_ID: {"input": 1.00, "output": 5.00},
}

_TOKENS_PER_MTOK: Final[float] = 1_000_000.0


@dataclass(frozen=True)
class CostEstimate:
    """An estimated cost, permanently marked with its provenance."""

    model_id: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    pricing_is_placeholder: bool = PRICING_IS_PLACEHOLDER

    def as_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "input_cost_usd": self.input_cost_usd,
            "output_cost_usd": self.output_cost_usd,
            "total_cost_usd": self.total_cost_usd,
            "pricing_is_placeholder": self.pricing_is_placeholder,
        }


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    *,
    model_id: str = B7_MODEL_ID,
    pricing: Mapping[str, Mapping[str, float]] | None = None,
) -> float:
    """Return the estimated cost in USD for one call's token counts.

    Parameters
    ----------
    input_tokens, output_tokens:
        Token counts supplied by the caller. Must be non-negative.
    model_id:
        Key into ``pricing``.
    pricing:
        Rate table in USD per million tokens. Defaults to the PLACEHOLDER
        table in this module.

    Raises
    ------
    ValueError
        If a token count is negative, or ``model_id`` is absent from the rate
        table (an unpriced model is not silently costed at zero).
    """

    return estimate_cost(
        input_tokens, output_tokens, model_id=model_id, pricing=pricing
    ).total_cost_usd


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    *,
    model_id: str = B7_MODEL_ID,
    pricing: Mapping[str, Mapping[str, float]] | None = None,
) -> CostEstimate:
    """Like :func:`estimate_cost_usd` but returns the full breakdown."""

    if input_tokens < 0 or output_tokens < 0:
        raise ValueError(
            "token counts must be non-negative, got "
            f"input={input_tokens}, output={output_tokens}"
        )

    table = pricing if pricing is not None else PLACEHOLDER_PRICING_USD_PER_MTOK
    if model_id not in table:
        raise ValueError(
            f"no pricing entry for model {model_id!r}; refusing to assume a "
            "zero rate. Add the model to the pricing table explicitly."
        )

    rates = table[model_id]
    input_cost = input_tokens * rates["input"] / _TOKENS_PER_MTOK
    output_cost = output_tokens * rates["output"] / _TOKENS_PER_MTOK

    return CostEstimate(
        model_id=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        total_cost_usd=input_cost + output_cost,
        pricing_is_placeholder=table is PLACEHOLDER_PRICING_USD_PER_MTOK,
    )


def aggregate_cost(
    estimates: list[CostEstimate],
) -> CostEstimate:
    """Sum a list of per-call estimates into one total.

    The aggregate is flagged as placeholder-derived if ANY input was.
    """

    if not estimates:
        return CostEstimate(
            model_id=B7_MODEL_ID,
            input_tokens=0,
            output_tokens=0,
            input_cost_usd=0.0,
            output_cost_usd=0.0,
            total_cost_usd=0.0,
        )

    model_ids = {e.model_id for e in estimates}
    model_id = model_ids.pop() if len(model_ids) == 1 else "mixed"

    input_cost = sum(e.input_cost_usd for e in estimates)
    output_cost = sum(e.output_cost_usd for e in estimates)
    return CostEstimate(
        model_id=model_id,
        input_tokens=sum(e.input_tokens for e in estimates),
        output_tokens=sum(e.output_tokens for e in estimates),
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        total_cost_usd=input_cost + output_cost,
        pricing_is_placeholder=any(e.pricing_is_placeholder for e in estimates),
    )
