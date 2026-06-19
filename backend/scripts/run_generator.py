"""Run the generator agent live with canned inputs and print the PostSpecs.

Usage (from the backend/ directory):

    uv run python scripts/run_generator.py

Feeds a sample TrendBrief + brand snippet + rule as the message (no DB needed),
runs the generator through an in-memory ADK Runner, prints the GeneratorOutput
JSON, and validates it (3 specs: 2 image + 1 video). Real Gemini Pro call. Does
NOT touch the database, R2, or the spend meter.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.genai import types

APP_NAME = "content-agent"
USER_ID = "client"
SESSION_ID = "generator-test"

# Stands in for what the pipeline assembles (themes + brand_context + rules).
_MESSAGE = """## This week's themes (from the researcher)
- "Exercise Snacks" (Keep Moving / Move Naturally): short bursts of natural movement through the day; anti-gym.
- "Cultivating Calm / Downshifting" (Relaxation): small daily rituals to reduce stress.
- "Vitality of Connection" (Community): strong social bonds and longevity.

## Brand context (retrieved brand chunks)
Blue Fit is "The Blue Zone on the Waal" — premium, cinematic wellness-meets-travel:
open water, sunrises, riverside, wide landscapes. Real people of varied ages,
candid, in gentle motion. Not a hardcore gym.

## Active rules
- ocean blue, not navy

Produce the 3 PostSpecs now (2 image, 1 video, distinct pillars)."""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return t


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY not found — create backend/.env first.")

    from google.adk.runners import InMemoryRunner

    from app.agents.generator import build_generator
    from app.agents.schemas import GeneratorOutput

    runner = InMemoryRunner(agent=build_generator(), app_name=APP_NAME)
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    message = types.Content(role="user", parts=[types.Part(text=_MESSAGE)])

    final_text = ""
    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""

    print("\n=== Generator output (GeneratorOutput JSON) ===\n")
    print(final_text or "(no final response)")

    try:
        out = GeneratorOutput.model_validate_json(_strip_fences(final_text))
        kinds = [p.type for p in out.posts]
        pillars = [p.pillar for p in out.posts]
        print(f"\nParsed OK: {len(out.posts)} posts | types={kinds} | pillars={pillars}")
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic harness
        print(f"\nParse failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
