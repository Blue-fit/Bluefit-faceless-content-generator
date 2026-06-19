"""Run researcher -> generator end-to-end (standalone harness) and print both,
plus a token-usage breakdown for the whole run.

Usage (from the backend/ directory):

    uv run python scripts/run_pipeline.py

1. Runs the researcher (Flash + google_search) -> this week's themes.
2. Builds the generator's message from THOSE REAL themes + a sample brand snippet
   + a sample rule (brand_rag retrieval and rules-from-DB are Jacob's pipeline,
   stubbed here).
3. Runs the generator (Pro, output_schema) -> 3 PostSpecs.
4. Reports tokens used by each agent and the total.

Standalone test only — no DB, R2, or meter. The real pipeline.py is Jacob's.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agents.generator import build_generator
from app.agents.researcher import build_researcher
from app.agents.schemas import GeneratorOutput

APP_NAME = "content-agent"
USER_ID = "client"

# Sample brand context — the real pipeline retrieves this via brand_rag.
_BRAND_CONTEXT = (
    'Blue Fit is "The Blue Zone on the Waal" — premium, cinematic '
    "wellness-meets-travel: open water, sunrises, riverside, wide landscapes. "
    "Real people of varied ages, candid, in gentle motion. Not a hardcore gym."
)
_RULE = "ocean blue, not navy"

Usage = dict[str, int]


def _empty_usage() -> Usage:
    return {"prompt": 0, "output": 0, "thoughts": 0, "total": 0}


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return t


async def _run_agent(
    agent: LlmAgent, message: str, session_id: str
) -> tuple[str, Usage]:
    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    usage = _empty_usage()
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=content
    ):
        um = getattr(event, "usage_metadata", None)
        if um is not None:
            usage["prompt"] += um.prompt_token_count or 0
            usage["output"] += um.candidates_token_count or 0
            usage["thoughts"] += um.thoughts_token_count or 0
            usage["total"] += um.total_token_count or 0
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""
    return final_text, usage


def _print_usage(label: str, u: Usage) -> None:
    print(
        f"  {label:11} prompt={u['prompt']:>7,}  output={u['output']:>7,}  "
        f"thoughts={u['thoughts']:>7,}  total={u['total']:>7,}"
    )


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY not found — create backend/.env first.")

    # 1) Researcher -> themes
    themes_raw, research_usage = await _run_agent(
        build_researcher(),
        "Produce this week's Blue Fit content themes.",
        "pipeline-researcher",
    )
    print("\n=== 1) RESEARCHER output (themes) ===\n")
    print(themes_raw or "(no output)")

    # 2) Build the generator's message FROM the researcher's real themes.
    generator_message = (
        "## This week's themes (from the researcher)\n"
        f"{_strip_fences(themes_raw)}\n\n"
        f"## Brand context (retrieved)\n{_BRAND_CONTEXT}\n\n"
        f"## Active rules\n- {_RULE}\n\n"
        "Produce the 3 PostSpecs now (2 image, 1 video, distinct pillars)."
    )

    # 3) Generator -> PostSpecs
    specs_raw, generate_usage = await _run_agent(
        build_generator(), generator_message, "pipeline-generator"
    )
    print("\n=== 2) GENERATOR output (PostSpecs, fed by the researcher) ===\n")
    print(specs_raw or "(no output)")

    try:
        out = GeneratorOutput.model_validate_json(_strip_fences(specs_raw))
        kinds = [p.type for p in out.posts]
        pillars = [p.pillar for p in out.posts]
        print(f"\nParsed OK: {len(out.posts)} posts | types={kinds} | pillars={pillars}")
    except Exception as exc:  # noqa: BLE001 - diagnostic harness
        print(f"\nParse failed: {exc}")

    grand_total = research_usage["total"] + generate_usage["total"]
    print("\n=== TOKEN USAGE (research agent -> final 3 posts) ===")
    _print_usage("researcher", research_usage)
    _print_usage("generator", generate_usage)
    print(f"  {'GRAND TOTAL':11} {'':>30}total={grand_total:>7,}")


if __name__ == "__main__":
    asyncio.run(main())