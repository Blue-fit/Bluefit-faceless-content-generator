"""Single source of truth for model unit costs (meter/CLAUDE.md).

When Google changes prices, update this file only. All values are EUR.

NOTE: the numbers below are PLACEHOLDER list prices — verify against current
Google pricing before production (scripts/verify_pricing.py compares predicted
vs actual and alerts on >10% drift).
"""

from __future__ import annotations

from decimal import Decimal

from app.genai_client import MODEL_EMBED, MODEL_FLASH, MODEL_PRO

# Text / embedding models priced per 1,000,000 tokens, as (input, output).
_PER_MILLION_TOKENS: dict[str, tuple[Decimal, Decimal]] = {
    MODEL_FLASH: (Decimal("0.30"), Decimal("2.50")),
    MODEL_PRO: (Decimal("1.25"), Decimal("10.00")),
    MODEL_EMBED: (Decimal("0.15"), Decimal("0")),
}

# Flat per-asset costs.
_PER_IMAGE = Decimal("0.039")  # Nano Banana, per image
_PER_VIDEO_SECOND = Decimal("0.15")  # Veo 3.1 Fast, per second of output

_MILLION = Decimal(1_000_000)


def text_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Cost of a text generation call from its token counts."""
    if model not in _PER_MILLION_TOKENS:
        raise KeyError(f"No pricing entry for model {model!r}")
    price_in, price_out = _PER_MILLION_TOKENS[model]
    return (price_in * input_tokens + price_out * output_tokens) / _MILLION


def embedding_cost(model: str, input_tokens: int) -> Decimal:
    """Cost of an embedding call (input tokens only)."""
    return text_cost(model, input_tokens, 0)


def image_cost() -> Decimal:
    """Flat cost of one generated image."""
    return _PER_IMAGE


def video_cost(seconds: int) -> Decimal:
    """Cost of a generated video of the given length."""
    return _PER_VIDEO_SECOND * seconds
