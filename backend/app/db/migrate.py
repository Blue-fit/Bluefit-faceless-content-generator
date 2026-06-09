"""Forward-only migration runner.

Runs as a standalone script (``python -m app.db.migrate``) or is called from
the FastAPI lifespan before the connection pool is created. Uses a plain
asyncpg connection rather than the pool so it works before pgvector is
installed.
"""

import asyncio
import os

import asyncpg
import structlog

from app.config import get_settings

log = structlog.get_logger()

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


async def run_migrations(database_url: str | None = None) -> None:
    url = database_url or get_settings().database_url
    conn: asyncpg.Connection = await asyncpg.connect(url)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename   TEXT        PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        applied: set[str] = {
            row["filename"]
            for row in await conn.fetch("SELECT filename FROM schema_migrations")
        }

        files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))

        for filename in files:
            if filename in applied:
                continue

            path = os.path.join(MIGRATIONS_DIR, filename)
            with open(path) as f:
                sql = f.read().strip()

            if not sql:
                log.info("migration.skipped_empty", filename=filename)
                continue

            log.info("migration.applying", filename=filename)
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)",
                    filename,
                )
            log.info("migration.applied", filename=filename)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
