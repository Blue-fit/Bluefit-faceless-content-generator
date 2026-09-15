"""Image generation via Nano Banana (gemini-3.1-flash-image).

`render_image` is the no-DB core (used by tests + standalone harnesses);
`generate_image` is the public @meter-wrapped tool the pipeline calls.

Reference images (the mascot photos) ride along as image parts in `contents`
next to the prompt — that is how Nano Banana keeps a specific character
consistent across renders.

Blocked renders: Google's non-configurable filter returns a candidate with no
parts (finish_reason PROHIBITED_CONTENT) for roughly half of mascot requests —
the same request passes on a re-roll (measured 2026-09-15, decisions/008). A
blocked call produces no output tokens, so we simply retry a few times before
giving up.

NOTE: per the agreed split, this returns asset **bytes** + metadata and stops —
the R2 upload is the storage/pipeline layer's job (Jacob's), not this tool's.
This intentionally deviates from tools/CLAUDE.md ("upload to R2 / don't return
bytes") for that division of labor.
"""

from __future__ import annotations

from collections.abc import Sequence

import structlog
from google.genai import types

from app.genai_client import MODEL_IMAGE, get_genai_client, with_retry
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.tools import RefImage, ToolError

logger = structlog.get_logger(__name__)

# Re-rolls for a blocked (empty) candidate — see module docstring.
_BLOCK_ATTEMPTS = 5


class ImageRequest(MeterRequest):
    prompt: str
    aspect_ratio: str = "9:16"
    reference_images: list[RefImage] = []


class ImageResult(MeteredResult):
    image_bytes: bytes
    mime_type: str


def _contents(prompt: str, refs: Sequence[RefImage]) -> types.ContentListUnion:
    """Plain string with no refs (unchanged behaviour); text + image parts with refs."""
    if not refs:
        return prompt
    parts: list[types.PartUnion] = [types.Part(text=prompt)]
    parts.extend(types.Part.from_bytes(data=r.data, mime_type=r.mime_type) for r in refs)
    return parts


async def render_image(
    prompt: str,
    aspect_ratio: str = "9:16",
    *,
    reference_images: Sequence[RefImage] | None = None,
) -> ImageResult:
    """Core Nano Banana render — no DB, no metering. Used by tests + harnesses."""
    client = get_genai_client()
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
    )
    contents = _contents(prompt, reference_images or ())
    reason = "unknown"
    for attempt in range(1, _BLOCK_ATTEMPTS + 1):
        response = await with_retry(
            lambda: client.aio.models.generate_content(
                model=MODEL_IMAGE, contents=contents, config=config
            )
        )
        if not response.candidates:
            raise ToolError("Image model returned no candidates.")
        candidate = response.candidates[0]
        for part in (candidate.content.parts if candidate.content else None) or []:
            inline = part.inline_data
            if inline is not None and inline.data:
                return ImageResult(
                    model=MODEL_IMAGE,
                    cost_eur=pricing.image_cost(),
                    image_bytes=inline.data,
                    mime_type=inline.mime_type or "image/png",
                )
        reason = str(candidate.finish_reason or "empty")
        logger.warning("genai.image_blocked", attempt=attempt, finish_reason=reason)
    raise ToolError(
        f"Image model returned no image after {_BLOCK_ATTEMPTS} attempts "
        f"(last finish_reason={reason})."
    )


@meter("image")
async def generate_image(req: ImageRequest) -> ImageResult:
    """Metered image tool: render the prompt and record usage to `usage`."""
    return await render_image(
        req.prompt, req.aspect_ratio, reference_images=req.reference_images
    )
