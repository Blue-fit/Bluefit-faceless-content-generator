"""Live full run of the production weekly pipeline (real research, generation, Veo).

Uses a local-disk uploader in place of Jacob's R2 AssetUploader, so we can see the
real assets and the DB still gets asset_urls. Writes 3 real posts to the DB and
costs real money (~EUR 2-3, dominated by Veo). Run from the backend/ directory:

    uv run python scripts/run_weekly_live.py
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from app.agents.pipeline import run_weekly
from app.db.connection import close_pool, create_pool
from app.storage.r2 import R2Uploader


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    await create_pool()
    try:
        result = await run_weekly(date.today(), uploader=R2Uploader())
        print("\n=== WeekResult ===")
        print("status   :", result.status)
        print("week_id  :", result.week_id)
        print("posts    :", len(result.post_ids))
        print("cost EUR :", result.cost_eur)
        for u in result.asset_urls:
            print("  asset  :", u)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
