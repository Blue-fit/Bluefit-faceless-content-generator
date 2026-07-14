"""Image generation via Nano Banana (gemini-2.5-flash-image).

`render_image` is the no-DB core (used by tests + standalone harnesses);
`generate_image` is the public @meter-wrapped tool the pipeline calls.

NOTE: per the agreed split, this returns asset **bytes** + metadata and stops —
the R2 upload is the storage/pipeline layer's job (Jacob's), not this tool's.
This intentionally deviates from tools/CLAUDE.md ("upload to R2 / don't return
bytes") for that division of labor.
"""

from __future__ import annotations

from google.genai import types

from app.genai_client import MODEL_IMAGE, get_genai_client, with_retry
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.tools import ToolError


class ImageRequest(MeterRequest):
    prompt: str
    aspect_ratio: str = "9:16"


class ImageResult(MeteredResult):
    image_bytes: bytes
    mime_type: str


async def render_image(prompt: str, aspect_ratio: str = "9:16") -> ImageResult:
    """Core Nano Banana render — no DB, no metering. Used by tests + harnesses."""
    client = get_genai_client()
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
    )
    response = await with_retry(
        lambda: client.aio.models.generate_content(
            model=MODEL_IMAGE, contents=prompt, config=config
        )
    )
    if not response.candidates:
        raise ToolError("Image model returned no candidates.")
    candidate = response.candidates[0]
    if candidate.content is None or not candidate.content.parts:
        raise ToolError("Image model returned no content parts.")
    for part in candidate.content.parts:
        inline = part.inline_data
        if inline is not None and inline.data:
            return ImageResult(
                model=MODEL_IMAGE,
                cost_eur=pricing.image_cost(),
                image_bytes=inline.data,
                mime_type=inline.mime_type or "image/png",
            )
    raise ToolError("Image model returned no image bytes.")


@meter("image")
async def generate_image(req: ImageRequest) -> ImageResult:
    """Metered image tool: render the prompt and record usage to `usage`."""
    return await render_image(req.prompt, req.aspect_ratio)