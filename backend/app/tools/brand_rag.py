"""Brand RAG retrieval over `brand_chunks` (generation-time grounding).

Embeds a query and returns the closest brand-doc chunks (cosine, pgvector) so the
generator can ground and justify a post in the real requirements doc. The pgvector
search is free, but the query embedding is a paid call — so this is @meter-wrapped.
Returns chunk text (for the prompt) and chunk IDs (for `reasoning_blob.brand_chunk_ids`).
"""

from __future__ import annotations

from uuid import UUID

from app.db.connection import get_pool
from app.db.repositories.brand_chunks import search_chunks
from app.genai_client import MODEL_EMBED, embed
from app.meter import MeteredResult, MeterRequest, meter, pricing


class BrandRagRequest(MeterRequest):
    query: str
    limit: int = 5


class BrandRagResult(MeteredResult):
    chunks: list[str]
    chunk_ids: list[UUID]


@meter("embedding")
async def brand_rag(req: BrandRagRequest) -> BrandRagResult:
    """Return the brand chunks most relevant to `req.query` (text + IDs)."""
    vector = await embed(req.query)
    async with get_pool().acquire() as conn:
        rows = await search_chunks(conn, vector, req.limit)
    # Cost is the query embedding (search is free). ~4 chars/token estimate;
    # pricing.py values are placeholders and verify_pricing.py catches drift.
    tokens = max(1, len(req.query) // 4)
    return BrandRagResult(
        model=MODEL_EMBED,
        cost_eur=pricing.embedding_cost(MODEL_EMBED, tokens),
        chunks=[r.content for r in rows],
        chunk_ids=[r.id for r in rows],
    )
