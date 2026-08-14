from decimal import Decimal

import pytest

from app.genai_client import MODEL_EMBED, MODEL_FLASH
from app.meter import pricing


def test_text_cost_one_million_each() -> None:
    # 1M input + 1M output tokens == price_in + price_out
    assert pricing.text_cost(MODEL_FLASH, 1_000_000, 1_000_000) == Decimal("0.30") + Decimal("2.50")


def test_text_cost_scales_with_tokens() -> None:
    assert pricing.text_cost(MODEL_FLASH, 500_000, 0) == Decimal("0.15")


def test_embedding_cost_ignores_output() -> None:
    assert pricing.embedding_cost(MODEL_EMBED, 1_000_000) == Decimal("0.15")


def test_image_cost_is_flat() -> None:
    assert pricing.image_cost() == Decimal("0.039")


def test_video_cost_scales_with_seconds() -> None:
    assert pricing.video_cost(8) == Decimal("0.10") * 8


def test_unknown_model_raises() -> None:
    with pytest.raises(KeyError):
        pricing.text_cost("not-a-model", 1, 1)
