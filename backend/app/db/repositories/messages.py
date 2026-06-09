from datetime import datetime
from uuid import UUID

import asyncpg

from app.db.models import Message


def _row_to_message(row: asyncpg.Record) -> Message:
    return Message(
        id=row["id"],
        post_id=row["post_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
    )


async def insert_message(
    conn: asyncpg.Connection,
    *,
    post_id: UUID,
    role: str,
    content: str,
) -> Message:
    row = await conn.fetchrow(
        """
        INSERT INTO messages (post_id, role, content)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        post_id,
        role,
        content,
    )
    return _row_to_message(row)


async def get_messages_for_post(
    conn: asyncpg.Connection,
    post_id: UUID,
) -> list[Message]:
    rows = await conn.fetch(
        "SELECT * FROM messages WHERE post_id = $1 ORDER BY created_at",
        post_id,
    )
    return [_row_to_message(r) for r in rows]


async def get_messages_since(
    conn: asyncpg.Connection,
    since: datetime,
) -> list[Message]:
    """Return all messages newer than `since`, ordered by post and time.

    Used by the nightly rule extraction job (14-day window).
    """
    rows = await conn.fetch(
        "SELECT * FROM messages WHERE created_at >= $1 ORDER BY post_id, created_at",
        since,
    )
    return [_row_to_message(r) for r in rows]
