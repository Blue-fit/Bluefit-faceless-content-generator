from uuid import UUID

import asyncpg

from app.db.models import Post


def _row_to_post(row: asyncpg.Record) -> Post:
    return Post(
        id=row["id"],
        week_id=row["week_id"],
        type=row["type"],
        pillar=row["pillar"],
        current_version_id=row["current_version_id"],
        created_at=row["created_at"],
    )


async def insert_post(
    conn: asyncpg.Connection,
    *,
    week_id: UUID,
    type: str,
    pillar: str,
) -> Post:
    row = await conn.fetchrow(
        """
        INSERT INTO posts (week_id, type, pillar)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        week_id,
        type,
        pillar,
    )
    return _row_to_post(row)


async def get_post(conn: asyncpg.Connection, post_id: UUID) -> Post | None:
    row = await conn.fetchrow("SELECT * FROM posts WHERE id = $1", post_id)
    return _row_to_post(row) if row else None


async def get_posts_for_week(conn: asyncpg.Connection, week_id: UUID) -> list[Post]:
    rows = await conn.fetch(
        "SELECT * FROM posts WHERE week_id = $1 ORDER BY created_at",
        week_id,
    )
    return [_row_to_post(r) for r in rows]


async def set_current_version(
    conn: asyncpg.Connection,
    post_id: UUID,
    version_id: UUID,
) -> None:
    await conn.execute(
        "UPDATE posts SET current_version_id = $1 WHERE id = $2",
        version_id,
        post_id,
    )
