"""Weekly generator agent: Gemini Pro with structured PostSpec output.

Receives this week's themes + brand context + active rules in the runtime message
(pipeline-orchestrated — not a SequentialAgent) and emits a `GeneratorOutput`
(3 PostSpecs: 2 image, 1 video). It uses `output_schema`, so it has **no tools** —
brand retrieval is done by the pipeline, not the agent. See agents/CLAUDE.md and
docs/references/golden-example.md.
"""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent

from app.agents.schemas import GeneratorOutput
from app.genai_client import MODEL_PRO

_PROMPT = (Path(__file__).parent / "prompts" / "generator.md").read_text(
    encoding="utf-8"
)


def build_generator() -> LlmAgent:
    """Build the weekly generator agent (Pro, structured PostSpec output)."""
    return LlmAgent(
        name="generator",
        model=MODEL_PRO,
        description="Turns weekly themes + brand context into 3 brand-aligned PostSpecs.",
        instruction=_PROMPT,
        output_schema=GeneratorOutput,
        output_key="post_specs",
    )
