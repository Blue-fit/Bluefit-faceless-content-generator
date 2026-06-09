from datetime import date
from uuid import UUID

import asyncpg

from app.db.models import StrategicBrief


def _row_to_brief(row: asyncpg.Record) -> StrategicBrief:
    return StrategicBrief(
        id=row["id"],
        month=row["month"],
        content=row["content"],
        created_at=row["created_at"],
    )


async def insert_brief(
    conn: asyncpg.Connection,
    *,
    month: date,
    content: str,
) -> StrategicBrief:
    row = await conn.fetchrow(
        """
        INSERT INTO strategic_briefs (month, content)
        VALUES ($1, $2)
        RETURNING *
        """,
        month,
        content,
    )
    return _row_to_brief(row)


async def get_latest_brief(conn: asyncpg.Connection) -> StrategicBrief | None:
    row = await conn.fetchrow(
        "SELECT * FROM strategic_briefs ORDER BY month DESC LIMIT 1",
    )
    return _row_to_brief(row) if row else None


async def get_brief(conn: asyncpg.Connection, brief_id: UUID) -> StrategicBrief | None:
    row = await conn.fetchrow(
        "SELECT * FROM strategic_briefs WHERE id = $1",
        brief_id,
    )
    return _row_to_brief(row) if row else None
