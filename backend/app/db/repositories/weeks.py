from datetime import date
from uuid import UUID

import asyncpg

from app.db.models import Week


def _row_to_week(row: asyncpg.Record) -> Week:
    return Week(
        id=row["id"],
        week_start=row["week_start"],
        trend_brief=row["trend_brief"],
        status=row["status"],
        created_at=row["created_at"],
    )


async def insert_week(conn: asyncpg.Connection, week_start: date) -> Week:
    row = await conn.fetchrow(
        """
        INSERT INTO weeks (week_start)
        VALUES ($1)
        RETURNING *
        """,
        week_start,
    )
    return _row_to_week(row)


async def get_week(conn: asyncpg.Connection, week_id: UUID) -> Week | None:
    row = await conn.fetchrow("SELECT * FROM weeks WHERE id = $1", week_id)
    return _row_to_week(row) if row else None


async def get_week_by_start(conn: asyncpg.Connection, week_start: date) -> Week | None:
    row = await conn.fetchrow("SELECT * FROM weeks WHERE week_start = $1", week_start)
    return _row_to_week(row) if row else None


async def set_week_brief(
    conn: asyncpg.Connection,
    week_id: UUID,
    trend_brief: dict,
) -> None:
    await conn.execute(
        "UPDATE weeks SET trend_brief = $1 WHERE id = $2",
        trend_brief,
        week_id,
    )


async def set_week_status(
    conn: asyncpg.Connection,
    week_id: UUID,
    status: str,
) -> None:
    await conn.execute(
        "UPDATE weeks SET status = $1 WHERE id = $2",
        status,
        week_id,
    )
