"""Friday weekly content generation — the Render Cron entrypoint.

Schedule: Fridays 09:00 UTC. Builds the DB pool, runs the full weekly pipeline
(research -> RAG -> generate -> render -> upload to R2 -> persist), then exits
non-zero if the week did not finish 'ready' so the cron run is flagged failed.

Local run (from backend/):  uv run python scripts/trigger_weekly.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

import structlog
from dotenv import load_dotenv

from app.agents.pipeline import run_weekly
from app.db.connection import close_pool, create_pool
from app.notifications.email import send_weekly_digest
from app.storage.r2 import R2Uploader

log = structlog.get_logger()


async def main() -> int:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    week_start = date.today()
    await create_pool()
    try:
        result = await run_weekly(week_start, uploader=R2Uploader())
        log.info(
            "weekly.done",
            status=result.status,
            week_id=str(result.week_id),
            posts=len(result.post_ids),
            cost_eur=result.cost_eur,
        )
        if result.status == "ready":
            await send_weekly_digest(
                week_label=f"Week of {week_start.strftime('%B')} {week_start.day}",
                n_posts=len(result.post_ids),
            )
        return 0 if result.status == "ready" else 1
    finally:
        await close_pool()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
