"""Run the researcher agent live and print the TrendBrief JSON it produces.

Usage (from the backend/ directory):

    uv run python scripts/run_researcher.py

It loads GOOGLE_API_KEY from backend/.env (ADK reads the key from the
environment), runs the researcher through an in-memory ADK Runner, and prints
the agent's JSON output. This makes a real — but cheap — Gemini Flash +
google_search call. It does NOT touch the database, R2, or the spend meter.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.genai import types

APP_NAME = "content-agent"
USER_ID = "client"
SESSION_ID = "researcher-test"


async def main() -> None:
    # ADK / google-genai authenticate from the environment, so load .env into it.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY not found — create backend/.env first.")

    from google.adk.runners import InMemoryRunner

    from app.agents.researcher import build_researcher

    runner = InMemoryRunner(agent=build_researcher(), app_name=APP_NAME)
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text="Produce this week's Blue Fit content themes.")],
    )

    final_text = ""
    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""

    print("\n=== Researcher output (expected: TrendBrief JSON) ===\n")
    print(final_text or "(no final response)")


if __name__ == "__main__":
    asyncio.run(main())
