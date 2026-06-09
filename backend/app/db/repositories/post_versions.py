from uuid import UUID

import asyncpg
import numpy as np

from app.db.models import PostVersion


def _row_to_version(row: asyncpg.Record) -> PostVersion:
    emb = row["reasoning_embedding"]
    return PostVersion(
        id=row["id"],
        post_id=row["post_id"],
        parent_version_id=row["parent_version_id"],
        version_number=row["version_number"],
        asset_url=row["asset_url"],
        caption=row["caption"],
        edit_instruction=row["edit_instruction"],
        reasoning_blob=row["reasoning_blob"],
        reasoning_embedding=emb.tolist() if emb is not None else None,
        created_at=row["created_at"],
    )


async def insert_version(
    conn: asyncpg.Connection,
    *,
    post_id: UUID,
    parent_version_id: UUID | None,
    version_number: int,
    asset_url: str | None,
    caption: str | None,
    edit_instruction: str | None,
    reasoning_blob: dict | None,
    reasoning_embedding: list[float] | None,
) -> PostVersion:
    emb = np.array(reasoning_embedding, dtype=np.float32) if reasoning_embedding is not None else None
    row = await conn.fetchrow(
        """
        INSERT INTO post_versions
            (post_id, parent_version_id, version_number, asset_url,
             caption, edit_instruction, reasoning_blob, reasoning_embedding)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        post_id,
        parent_version_id,
        version_number,
        asset_url,
        caption,
        edit_instruction,
        reasoning_blob,
        emb,
    )
    return _row_to_version(row)


async def get_version(conn: asyncpg.Connection, version_id: UUID) -> PostVersion | None:
    row = await conn.fetchrow("SELECT * FROM post_versions WHERE id = $1", version_id)
    return _row_to_version(row) if row else None


async def get_versions_for_post(
    conn: asyncpg.Connection,
    post_id: UUID,
) -> list[PostVersion]:
    rows = await conn.fetch(
        "SELECT * FROM post_versions WHERE post_id = $1 ORDER BY version_number",
        post_id,
    )
    return [_row_to_version(r) for r in rows]


async def count_versions_for_post(conn: asyncpg.Connection, post_id: UUID) -> int:
    return await conn.fetchval(
        "SELECT COUNT(*) FROM post_versions WHERE post_id = $1",
        post_id,
    )


async def search_by_reasoning(
    conn: asyncpg.Connection,
    embedding: list[float],
    limit: int = 5,
) -> list[PostVersion]:
    """Return versions whose reasoning_embedding is closest to the query (cosine)."""
    emb = np.array(embedding, dtype=np.float32)
    rows = await conn.fetch(
        """
        SELECT *
        FROM post_versions
        WHERE reasoning_embedding IS NOT NULL
        ORDER BY reasoning_embedding <=> $1
        LIMIT $2
        """,
        emb,
        limit,
    )
    return [_row_to_version(r) for r in rows]
