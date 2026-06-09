from datetime import datetime
from decimal import Decimal
from uuid import UUID

import asyncpg

from app.db.models import UsageRecord


def _row_to_record(row: asyncpg.Record) -> UsageRecord:
    return UsageRecord(
        id=row["id"],
        model=row["model"],
        call_type=row["call_type"],
        cost_eur=row["cost_eur"],
        trigger=row["trigger"],
        post_id=row["post_id"],
        created_at=row["created_at"],
    )


async def insert_usage(
    conn: asyncpg.Connection,
    *,
    model: str,
    call_type: str,
    cost_eur: Decimal,
    trigger: str,
    post_id: UUID | None,
) -> UsageRecord:
    row = await conn.fetchrow(
        """
        INSERT INTO usage (model, call_type, cost_eur, trigger, post_id)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        model,
        call_type,
        cost_eur,
        trigger,
        post_id,
    )
    return _row_to_record(row)


async def get_monthly_spend(conn: asyncpg.Connection, month_start: datetime) -> Decimal:
    value = await conn.fetchval(
        "SELECT COALESCE(SUM(cost_eur), 0) FROM usage WHERE created_at >= $1",
        month_start,
    )
    return Decimal(value)
