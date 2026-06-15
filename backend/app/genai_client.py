"""Shared google-genai client + canonical model IDs.

Single factory for direct model calls in tools and agents. We are Google-only
and use google-genai directly — no abstraction layer (docs/decisions/007). The
client is created from the Gemini Developer API key in settings; ADK agents read
the same key from the environment separately.
"""

from __future__ import annotations

from functools import lru_cache

from google import genai

from app.config import get_settings

# Canonical model IDs — referenced by tools, agents, and meter/pricing.py.
MODEL_FLASH = "gemini-2.5-flash"
MODEL_PRO = "gemini-2.5-pro"
MODEL_IMAGE = "gemini-2.5-flash-image"  # Nano Banana
MODEL_VIDEO = "veo-3.1-fast-generate-preview"  # Veo 3.1 Fast
MODEL_EMBED = "text-embedding-005"  # 768-dim, matches the pgvector columns


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
