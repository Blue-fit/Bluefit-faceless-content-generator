"""Agent I/O contracts (versioned).

`TrendBrief` is the researcher's output; `GeneratorOutput` (a list of `PostSpec`)
is the generator's output and is used as the generator's ADK `output_schema`.
A breaking change to either requires bumping `SCHEMA_VERSION` (agents/CLAUDE.md).
"""

from __future__ import annotations

from datetime import date
from typing import Literal, get_args

from pydantic import BaseModel, Field

SCHEMA_VERSION = 2  # v2: references_used.value is a required, typed Power-9 anchor

Pillar = Literal["Community", "Keep Moving", "Keep Setting Goals", "Natural Eating"]
# The nine Blue Zones "Power-9" values. Every post is anchored to exactly one, and
# the weekly no-repeat rule matches on these exact names (free text defeated it).
Power9Value = Literal[
    "Move naturally",
    "Have a purpose",
    "Relaxation",
    "The 80% rule",
    "Plant-based eating",
    "Wine in good company",
    "Belonging",
    "Family first",
    "Social circles",
]
POWER9_VALUES: tuple[str, ...] = get_args(Power9Value)
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
    value: Power9Value = Field(
        description="The one Power-9 value this post is anchored to (exact name)."
    )
    brand_cues: list[str] = Field(default_factory=list)
    rule_applied: str | None = None


class PostSpec(BaseModel):
    """One post's specification. The generator writes the scene only; the style
    block is appended by the assembly step, not by the model."""

    pillar: Pillar
    type: PostType
    scene_prompt: str = Field(
        description=(
            "The creative scene only — the Blue Fit mascot as subject, action, "
            "setting, composition; no brand style block, no mascot appearance."
        )
    )
    beat: str | None = Field(
        default=None,
        description="The one scroll-stopping visual moment/gag, one sentence.",
    )
    motion: str | None = Field(
        default=None,
        description="Video only: camera move + how the beat pays off within 8s.",
    )
    duration_seconds: int | None = Field(
        default=None, description="Clip length in seconds (video only; fixed 8)."
    )
    hook: str | None = Field(
        default=None,
        description="Every post: short on-screen hook text burned onto the asset.",
    )
    caption_template: CaptionTemplate
    caption: str
    references_used: PostReferences


class GeneratorOutput(BaseModel):
    """The generator's full output — exactly 3 posts (2 image + 1 video)."""

    posts: list[PostSpec]
