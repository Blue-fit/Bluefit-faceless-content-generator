"""Shared google-genai client + canonical model IDs.

Single factory for direct model calls in tools and agents. We are Google-only
and use google-genai directly — no abstraction layer (docs/decisions/007). The
client is created from the Gemini Developer API key in settings; ADK agents read
the same key from the environment separately.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import TypeVar

import structlog
from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import get_settings
from app.tools import ToolError

logger = structlog.get_logger(__name__)

_TRANSIENT_CODES = {429, 500, 503}
_T = TypeVar("_T")

# Canonical model IDs — referenced by tools, agents, and meter/pricing.py.
MODEL_FLASH = "gemini-2.5-flash"
MODEL_PRO = "gemini-3.1-pro-preview"
MODEL_IMAGE = "gemini-3.1-flash-image"  # Nano Banana
MODEL_VIDEO = "veo-3.1-fast-generate-preview"  # Veo 3.1 Fast
MODEL_EMBED = "gemini-embedding-001"  # Developer API; truncated to 768 (pgvector cols)


@lru_cache
def get_genai_client() -> genai.Client:
    """Return a process-cached google-genai client for the Developer API."""
    settings = get_settings()
    if settings.google_genai_use_vertexai:
        raise RuntimeError(
            "GOOGLE_GENAI_USE_VERTEXAI is true, but this deployment is "
            "configured for the Gemini Developer API only. Add Vertex "
            "project/location settings before enabling it."
        )
    return genai.Client(api_key=settings.google_api_key.get_secret_value())


async def with_retry(call: Callable[[], Awaitable[_T]], *, attempts: int = 5) -> _T:
    """Retry a google-genai call on transient errors (429/500/503) with backoff.

    Google's models periodically return 503 "high demand"; the SDK's built-in
    retry gives up too quickly for a sustained spike. This makes a single
    transient blip self-heal instead of failing the user-facing call.
    """
    delay = 4.0
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except APIError as exc:
            code = getattr(exc, "code", None)
            if code in _TRANSIENT_CODES and attempt < attempts:
                logger.warning("genai.transient_retry", attempt=attempt, code=code, wait_s=delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
                continue
            raise
    raise RuntimeError("unreachable")  # pragma: no cover


async def generate_text(
    model: str, contents: str, *, fallback_model: str | None = None
) -> types.GenerateContentResponse:
    """Single-shot text generation with transient-error retry + optional model fallback.

    Tries `model` (retrying 503/429/500); if it still fails transiently and a
    `fallback_model` is given, retries on that model. Lets a user-facing call
    survive one model being overloaded while the other is up.
    """
    try:
        return await with_retry(
            lambda: get_genai_client().aio.models.generate_content(model=model, contents=contents),
            attempts=3,
        )
    except APIError as exc:
        if fallback_model and getattr(exc, "code", None) in _TRANSIENT_CODES:
            logger.warning("genai.model_fallback", from_model=model, to=fallback_model)
            return await with_retry(
                lambda: get_genai_client().aio.models.generate_content(
                    model=fallback_model, contents=contents
                ),
                attempts=3,
            )
        raise


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts into 768-dim vectors — one per input, in order.

    The batch worker: ingestion embeds many chunks in a single round-trip (faster
    and cheaper than one call per chunk). This is the unmetered core, like
    ``render_image`` — callers that spend money (ingest, brand_rag, memory_search)
    wrap it with ``@meter("embedding")``. Raises ``ToolError`` on a bad response.
    """
    if not texts:
        raise ToolError("embed_texts called with no texts.")
    response = await get_genai_client().aio.models.embed_content(
        model=MODEL_EMBED,
        # google-genai types `contents` as a wide union; list invariance makes mypy
        # reject our list[str] even though it's the documented batch input.
        contents=texts,  # type: ignore[arg-type]
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    embeddings = response.embeddings or []
    if len(embeddings) != len(texts):
        raise ToolError(
            f"Embedding count mismatch: sent {len(texts)} texts, got {len(embeddings)}."
        )
    return [list(e.values or []) for e in embeddings]


async def embed(text: str) -> list[float]:
    """Embed a single text into one 768-dim vector (thin wrapper over embed_texts)."""
    return (await embed_texts([text]))[0]
