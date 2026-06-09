from uuid import UUID

import asyncpg

from app.db.models import Rule


def _row_to_rule(row: asyncpg.Record) -> Rule:
    return Rule(
        id=row["id"],
        text=row["text"],
        confidence=row["confidence"],
        status=row["status"],
        source_week_id=row["source_week_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def get_active_rules(conn: asyncpg.Connection) -> list[Rule]:
    rows = await conn.fetch(
        "SELECT * FROM rules WHERE status = 'active' ORDER BY confidence DESC",
    )
    return [_row_to_rule(r) for r in rows]


async def get_all_rules(conn: asyncpg.Connection) -> list[Rule]:
    rows = await conn.fetch("SELECT * FROM rules ORDER BY created_at DESC")
    return [_row_to_rule(r) for r in rows]


async def insert_rule(
    conn: asyncpg.Connection,
    *,
    text: str,
    confidence: float,
    source_week_id: UUID | None,
) -> Rule:
    row = await conn.fetchrow(
        """
        INSERT INTO rules (text, confidence, source_week_id)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        text,
        confidence,
        source_week_id,
    )
    return _row_to_rule(row)


async def update_rule_confidence(
    conn: asyncpg.Connection,
    rule_id: UUID,
    confidence: float,
) -> None:
    await conn.execute(
        "UPDATE rules SET confidence = $1, updated_at = NOW() WHERE id = $2",
        confidence,
        rule_id,
    )


async def set_rule_status(
    conn: asyncpg.Connection,
    rule_id: UUID,
    status: str,
) -> None:
    await conn.execute(
        "UPDATE rules SET status = $1, updated_at = NOW() WHERE id = $2",
        status,
        rule_id,
    )
