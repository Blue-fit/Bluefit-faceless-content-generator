import asyncpg
import numpy as np

from app.db.models import BrandChunk


def _row_to_chunk(row: asyncpg.Record) -> BrandChunk:
    emb = row["embedding"]
    return BrandChunk(
        id=row["id"],
        content=row["content"],
        embedding=emb.tolist() if emb is not None else None,
        source=row["source"],
        created_at=row["created_at"],
    )


async def insert_chunk(
    conn: asyncpg.Connection,
    *,
    content: str,
    embedding: list[float],
    source: str,
) -> BrandChunk:
    emb = np.array(embedding, dtype=np.float32)
    row = await conn.fetchrow(
        """
        INSERT INTO brand_chunks (content, embedding, source)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        content,
        emb,
        source,
    )
    return _row_to_chunk(row)


async def search_chunks(
    conn: asyncpg.Connection,
    embedding: list[float],
    limit: int = 5,
) -> list[BrandChunk]:
    """Return the closest brand chunks by cosine distance."""
    emb = np.array(embedding, dtype=np.float32)
    rows = await conn.fetch(
        """
        SELECT *
        FROM brand_chunks
        ORDER BY embedding <=> $1
        LIMIT $2
        """,
        emb,
        limit,
    )
    return [_row_to_chunk(r) for r in rows]


async def delete_all_chunks(conn: asyncpg.Connection) -> None:
    """Remove all brand chunks. Used during re-ingestion."""
    await conn.execute("DELETE FROM brand_chunks")


async def count_chunks(conn: asyncpg.Connection) -> int:
    return await conn.fetchval("SELECT COUNT(*) FROM brand_chunks")
