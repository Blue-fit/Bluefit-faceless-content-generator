"""Video generation via Veo 3.1 Fast (veo-3.1-fast-generate-preview).

`render_video` is the no-DB core: it starts the Veo operation and polls to
completion (minutes). That blocking poll is fine on Render (long-running); it is
NOT serverless-safe. `generate_video` is the public @meter-wrapped tool.

Per the agreed split, this returns asset **bytes** + metadata; the R2 upload is
the storage/pipeline layer's job (Jacob's), not this tool's. Intentionally
deviates from tools/CLAUDE.md ("upload to R2 / don't return bytes").

Note: `generate_audio` is a Vertex-only param (rejected by the Developer API), so
Veo applies its own default here (3.1 generates audio).
"""

from __future__ import annotations

import asyncio

from google.genai import types

from app.genai_client import MODEL_VIDEO, get_genai_client, with_retry
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.tools import ToolError

_POLL_SECONDS = 10
_DEFAULT_DURATION = 8
# Veo 3.1 Fast (preview) latency is highly variable (~90s to many minutes). Cap
# the poll so a stuck operation raises a clear error instead of hanging forever.
_TIMEOUT_SECONDS = 360


class VideoRequest(MeterRequest):
    prompt: str
    aspect_ratio: str = "9:16"
    duration_seconds: int = _DEFAULT_DURATION


class VideoResult(MeteredResult):
    video_bytes: bytes
    mime_type: str


async def render_video(
    prompt: str,
    aspect_ratio: str = "9:16",
    duration_seconds: int = _DEFAULT_DURATION,
) -> VideoResult:
    """Core Veo render — start the operation, poll to completion. No DB / meter."""
    client = get_genai_client()
    config = types.GenerateVideosConfig(
        number_of_videos=1,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
    )
    operation = await with_retry(
        lambda: client.aio.models.generate_videos(
            model=MODEL_VIDEO, prompt=prompt, config=config
        )
    )
    waited = 0
    while not operation.done:
        if waited >= _TIMEOUT_SECONDS:
            raise ToolError(
                f"Veo did not finish within {_TIMEOUT_SECONDS}s — the operation is "
                "still running or stuck. Try again or shorten the clip."
            )
        await asyncio.sleep(_POLL_SECONDS)
        waited += _POLL_SECONDS
        operation = await client.aio.operations.get(operation)

    response = operation.response
    if response is None or not response.generated_videos:
        raise ToolError("Veo returned no video.")
    video = response.generated_videos[0].video
    if video is None:
        raise ToolError("Veo returned no video object.")

    data = video.video_bytes
    if data is None:
        data = await client.aio.files.download(file=video)  # type: ignore[arg-type]
    return VideoResult(
        model=MODEL_VIDEO,
        cost_eur=pricing.video_cost(duration_seconds),
        video_bytes=data,
        mime_type=video.mime_type or "video/mp4",
    )


@meter("video")
async def generate_video(req: VideoRequest) -> VideoResult:
    """Metered video tool: render the clip and record usage to `usage`."""
    return await render_video(req.prompt, req.aspect_ratio, req.duration_seconds)
