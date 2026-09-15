"""Video generation via Gemini Omni Flash (Interactions API).

`render_video` is the no-DB core: it starts a background interaction and polls it
to completion (typically well under a minute). `generate_video` is the public
@meter-wrapped tool.

Character consistency: the primary path is **image-to-video** — the caller passes a
mascot still (rendered by the image model with the reference photos) as
`first_frame`; Omni animates that exact frame, so the mascot in frame 1 is the
mascot for the whole clip. `reference_images` maps to Omni's `reference_to_video`
task (kept for probes; the pipeline uses the first-frame path).

Why Omni over Veo (decisions/009): same ~$0.10/s at 720p, native image-to-video
that keeps the still pixel-exact as frame 1, works from the EEA with an uploaded
still, and renders in ~40 s instead of 90 s–6 min. Omni is called through the
Interactions API, not `generate_videos`; its errors carry `.status_code`, which
`with_retry` understands.

Per the agreed split, this returns asset **bytes** + metadata; the R2 upload is
the storage/pipeline layer's job, not this tool's. Intentionally deviates from
tools/CLAUDE.md ("upload to R2 / don't return bytes").
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Sequence
from typing import Any

import httpx

from app.genai_client import MODEL_VIDEO, get_genai_client, with_retry
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.tools import RefImage, ToolError

_POLL_SECONDS = 5
_DEFAULT_DURATION = 8
# Omni usually finishes in ~40 s; cap the poll so a stuck interaction raises a clear
# error instead of hanging forever.
_TIMEOUT_SECONDS = 360
_MAX_REFERENCE_IMAGES = 3
_PENDING = {"in_progress", "queued", "requires_action"}


class VideoRequest(MeterRequest):
    prompt: str
    aspect_ratio: str = "9:16"
    duration_seconds: int = _DEFAULT_DURATION
    first_frame: RefImage | None = None
    reference_images: list[RefImage] = []


class VideoResult(MeteredResult):
    video_bytes: bytes
    mime_type: str


def _image_input(ref: RefImage) -> dict[str, str]:
    return {
        "type": "image",
        "data": base64.b64encode(ref.data).decode(),
        "mime_type": ref.mime_type,
    }


async def render_video(
    prompt: str,
    aspect_ratio: str = "9:16",
    duration_seconds: int = _DEFAULT_DURATION,
    *,
    first_frame: RefImage | None = None,
    reference_images: Sequence[RefImage] | None = None,
) -> VideoResult:
    """Core Omni render — start the interaction, poll to completion. No DB / meter.

    `first_frame` → `image_to_video` (primary). `reference_images` →
    `reference_to_video`. Neither → `text_to_video`. Both together is rejected.
    """
    refs = list(reference_images or ())
    if first_frame is not None and refs:
        raise ToolError("Omni accepts either a first frame or reference images, not both.")
    if len(refs) > _MAX_REFERENCE_IMAGES:
        raise ToolError(f"Omni accepts at most {_MAX_REFERENCE_IMAGES} reference images.")

    if first_frame is not None:
        task, images = "image_to_video", [first_frame]
    elif refs:
        task, images = "reference_to_video", refs
    else:
        task, images = "text_to_video", []
    inputs: list[dict[str, str]] = [{"type": "text", "text": prompt}]
    inputs.extend(_image_input(img) for img in images)

    client = get_genai_client()
    interaction: Any = await with_retry(
        lambda: client.aio.interactions.create(
            model=MODEL_VIDEO,
            input=inputs,
            response_modalities=["video"],
            response_format={
                "type": "video",
                "aspect_ratio": aspect_ratio,
                "duration": f"{duration_seconds}s",
                "delivery": "inline",
            },
            generation_config={"video_config": {"task": task}},
            background=True,
        )
    )
    waited = 0
    while interaction.status in _PENDING:
        if waited >= _TIMEOUT_SECONDS:
            raise ToolError(
                f"Omni did not finish within {_TIMEOUT_SECONDS}s — the interaction is "
                "still running or stuck. Try again or shorten the clip."
            )
        await asyncio.sleep(_POLL_SECONDS)
        waited += _POLL_SECONDS
        interaction = await client.aio.interactions.get(interaction.id)

    if interaction.status != "completed":
        raise ToolError(f"Omni video {interaction.status}: {interaction.errors}")
    video = interaction.output_video
    if video is None:
        raise ToolError("Omni returned no video.")

    if video.data:
        data = base64.b64decode(video.data)
    elif video.uri:
        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.get(video.uri)
            resp.raise_for_status()
            data = resp.content
    else:
        raise ToolError("Omni returned a video with neither data nor uri.")

    return VideoResult(
        model=MODEL_VIDEO,
        cost_eur=pricing.video_cost(duration_seconds),
        video_bytes=data,
        mime_type=video.mime_type or "video/mp4",
    )


@meter("video")
async def generate_video(req: VideoRequest) -> VideoResult:
    """Metered video tool: render the clip and record usage to `usage`."""
    return await render_video(
        req.prompt,
        req.aspect_ratio,
        req.duration_seconds,
        first_frame=req.first_frame,
        reference_images=req.reference_images,
    )
