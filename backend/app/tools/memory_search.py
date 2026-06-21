"""Semantic memory over past posts (`post_versions.reasoning_embedding`).

Same embed -> cosine-search retrieval as brand_rag, but over the "why" vector of
previous posts instead of the brand doc. Used for (a) week-over-week variety — the
production replacement for the run_all.py history.json stopgap — and (b) chat-edit
memory later. The query embedding is paid, so this is @meter-wrapped.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.db.connection import get_pool
from app.db.models import PostVersion
from app.db.repositories.post_versions import search_by_reasoning
from app.genai_client import MODEL_EMBED, embed
from app.meter import MeteredResult, MeterRequest, meter, pricing


class RecentPost(BaseModel):
    """A past post projected down to what the generator needs to avoid repeating."""

    version_id: UUID
    pillar: str | None
    theme: str | None
    value: str | None
    hook: str | None
    caption: str | None
    asset_url: str | None


class MemorySearchRequest(MeterRequest):
    query: str
    limit: int = 6


class MemorySearchResult(MeteredResult):
    versions: list[RecentPost]


def _project(version: PostVersion) -> RecentPost:
    """Pull the recap fields from reasoning_blob (+ columns); tolerate a missing blob."""
    blob = version.reasoning_blob or {}
    return RecentPost(
        version_id=version.id,
        pillar=blob.get("pillar"),
        theme=blob.get("theme"),
        value=blob.get("value"),
        hook=blob.get("hook"),
        caption=version.caption,
        asset_url=version.asset_url,
    )


@meter("embedding")
async def memory_search(req: MemorySearchRequest) -> MemorySearchResult:
    """Return past posts semantically closest to `req.query` (variety + edit memory)."""
    vector = await embed(req.query)
    async with get_pool().acquire() as conn:
        versions = await search_by_reasoning(conn, vector, req.limit)
    # Cost is the query embedding (pgvector search is free). ~4 chars/token estimate.
    tokens = max(1, len(req.query) // 4)
    return MemorySearchResult(
        model=MODEL_EMBED,
        cost_eur=pricing.embedding_cost(MODEL_EMBED, tokens),
        versions=[_project(v) for v in versions],
    )
