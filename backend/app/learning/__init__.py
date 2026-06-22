"""Learning loop: distill recent edit instructions into durable brand rules.

`run_learning` is the nightly entry point (PRD §4.5): gather the last N days of edit
instructions -> Flash extraction -> upsert into `rules`. Active rules are then injected
into the generator by the weekly pipeline (`get_active_rules`), closing the loop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from pydantic import BaseModel

from app.db.connection import get_pool
from app.db.repositories.post_versions import recent_edit_instructions
from app.learning.apply import apply_candidates
from app.learning.extract import ExtractRequest, extract_rules

logger = structlog.get_logger(__name__)


class LearningResult(BaseModel):
    instructions: int
    candidates: int
    inserted: int
    updated: int
    cost_eur: Decimal


async def run_learning(days: int = 14) -> LearningResult:
    """Gather recent edit instructions, extract rules, and upsert them."""
    pool = get_pool()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with pool.acquire() as conn:
        instructions = await recent_edit_instructions(conn, since)
    logger.info("learning.gathered", instructions=len(instructions), days=days)

    extracted = await extract_rules(
        ExtractRequest(instructions=instructions, trigger="cron")
    )

    async with pool.acquire() as conn, conn.transaction():
        counts = await apply_candidates(conn, extracted.candidates)

    logger.info(
        "learning.done",
        candidates=len(extracted.candidates),
        inserted=counts["inserted"],
        updated=counts["updated"],
        cost_eur=str(extracted.cost_eur),
    )
    return LearningResult(
        instructions=len(instructions),
        candidates=len(extracted.candidates),
        inserted=counts["inserted"],
        updated=counts["updated"],
        cost_eur=extracted.cost_eur,
    )
