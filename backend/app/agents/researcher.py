"""Weekly researcher agent: Gemini Flash + built-in google_search.

Produces an abstract set of content themes as JSON text, saved to
``session.state['trend_brief']``. It uses a tool (`google_search`), so it has
**no** `output_schema` (that would disable tools); the pipeline validates the
JSON into `schemas.TrendBrief` with a repair retry. See agents/CLAUDE.md.
"""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from app.genai_client import MODEL_FLASH

_PROMPT = (Path(__file__).parent / "prompts" / "researcher.md").read_text(
    encoding="utf-8"
)


def build_researcher() -> LlmAgent:
    """Build the weekly researcher agent (Flash + google_search)."""
    return LlmAgent(
        name="researcher",
        model=MODEL_FLASH,
        description="Finds timely, on-brand weekly content themes via Google Search.",
        instruction=_PROMPT,
        tools=[google_search],
        output_key="trend_brief",
    )
