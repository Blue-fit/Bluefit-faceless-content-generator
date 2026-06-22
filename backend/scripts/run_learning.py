"""Run the nightly learning loop manually (the cron calls run_learning directly).

Usage (from the backend/ directory):

    uv run python scripts/run_learning.py

Distills the last 14 days of edit instructions into brand rules and upserts them,
then prints the active rules. Cheap (one Flash call). Needs a live DB.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv

from app.db.connection import close_pool, create_pool, get_pool
from app.db.repositories.rules import get_active_rules
from app.learning import run_learning


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    await create_pool()
    try:
        result = await run_learning(days=14)
        print("\n=== LearningResult ===")
        print(f"instructions gathered : {result.instructions}")
        print(f"candidates extracted  : {result.candidates}")
        print(f"rules inserted/updated: {result.inserted} / {result.updated}")
        print(f"cost EUR              : {result.cost_eur}")
        async with get_pool().acquire() as conn:
            rules = await get_active_rules(conn)
        print(f"\nActive rules now ({len(rules)}):")
        for r in rules:
            print(f"  - [conf {r.confidence:.2f}] {r.text}")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
