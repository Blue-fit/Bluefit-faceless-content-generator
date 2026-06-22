"""Caption generation via Gemini Flash with an engagement template.

Writes (or rewrites) an Instagram caption in one of the three engagement styles
(question / hot-take / observation), grounded in the post's brief. Used by the
edit subsystem for caption tweaks/rewrites. Paid (Flash) -> @meter("caption").
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from app.genai_client import MODEL_FLASH, get_genai_client
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.tools import ToolError

Template = Literal["question", "hottake", "observation"]
_PROMPTS = Path(__file__).resolve().parents[1] / "agents" / "prompts"


class CaptionRequest(MeterRequest):
    template: Template
    brief: str  # what the post is about (pillar, value, theme, scene)
    instruction: str | None = None  # an edit instruction, when rewriting a caption


class CaptionResult(MeteredResult):
    caption: str


@meter("caption")
async def generate_caption(req: CaptionRequest) -> CaptionResult:
    """Write a caption in the requested engagement style, grounded in the brief."""
    spec_file = _PROMPTS / f"caption_{req.template}.md"
    if not spec_file.exists():
        raise ToolError(f"Unknown caption template: {req.template}")

    parts = [
        spec_file.read_text(encoding="utf-8"),
        f"\n## This post\n{req.brief}",
    ]
    if req.instruction:
        parts.append(f"\n## Edit instruction (apply this)\n{req.instruction}")
    parts.append(
        "\nWrite ONLY the caption now — in **Dutch** (Blue Fit's brand language), in "
        "the brand's calm, grounded voice. No preamble, no quotes."
    )
    contents = "\n".join(parts)

    response = await get_genai_client().aio.models.generate_content(
        model=MODEL_FLASH, contents=contents
    )
    caption = (response.text or "").strip()
    if not caption:
        raise ToolError("generate_caption: Flash returned no text.")

    usage = response.usage_metadata
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    return CaptionResult(
        model=MODEL_FLASH,
        cost_eur=pricing.text_cost(MODEL_FLASH, in_tok, out_tok),
        caption=caption,
    )
