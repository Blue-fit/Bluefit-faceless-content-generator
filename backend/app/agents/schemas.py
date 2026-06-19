"""Agent I/O contracts (versioned).

`TrendBrief` is the researcher's output; `GeneratorOutput` (a list of `PostSpec`)
is the generator's output and is used as the generator's ADK `output_schema`.
A breaking change to either requires bumping `SCHEMA_VERSION` (agents/CLAUDE.md).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1

Pillar = Literal["Community", "Keep Moving", "Keep Setting Goals", "Natural Eating"]
PostType = Literal["image", "video"]
# Values double as the prompt filename stem: prompts/caption_{template}.md
CaptionTemplate = Literal["question", "hottake", "observation"]


# --- Researcher output ---------------------------------------------------------


class TrendTheme(BaseModel):
    """One abstract, timely theme grounded in a source."""

    title: str = Field(description="Short headline for the theme.")
    summary: str = Field(description="What the theme is, in 1-2 sentences.")
    why_relevant: str = Field(description="Why it fits Blue Fit / its pillars.")
    source_url: str = Field(description="Where the theme was found.")


class TrendBrief(BaseModel):
    """The researcher's weekly output: abstract themes, not visual scenes."""

    week_start: date
    themes: list[TrendTheme]


# --- Generator output ----------------------------------------------------------


class PostReferences(BaseModel):
    """What the generator leaned on — seeds the post's reasoning_blob."""

    theme: str | None = Field(default=None, description="TrendTheme title used.")
    value: str | None = Field(
        default=None, description="The Power-9 value the post embodies."
    )
    brand_cues: list[str] = Field(default_factory=list)
    rule_applied: str | None = None


class PostSpec(BaseModel):
    """One post's specification. The generator writes the scene only; the style
    block is appended by the assembly step, not by the model."""

    pillar: Pillar
    type: PostType
    scene_prompt: str = Field(
        description="The creative scene/subject only — no brand style block."
    )
    motion: str | None = Field(
        default=None, description="Camera + temporal motion (video only)."
    )
    duration_seconds: int | None = Field(
        default=None, description="Clip length in seconds (video only; fixed 8)."
    )
    hook: str | None = Field(
        default=None,
        description="Video only: short on-screen opening hook text; null for images.",
    )
    caption_template: CaptionTemplate
    caption: str
    references_used: PostReferences


class GeneratorOutput(BaseModel):
    """The generator's full output — exactly 3 posts (2 image + 1 video)."""

    posts: list[PostSpec]
