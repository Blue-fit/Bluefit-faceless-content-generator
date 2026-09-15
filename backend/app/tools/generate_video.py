"""Video generation via Veo 3.1 Fast (veo-3.1-fast-generate-preview).

`render_video` is the no-DB core: it starts the Veo operation and polls to
completion (minutes). That blocking poll is fine on Render (long-running); it is
NOT serverless-safe. `generate_video` is the public @meter-wrapped tool.

Character consistency: the primary path is **image-to-video** — the caller passes
a mascot still (rendered by Nano Banana with the reference photos) as
`first_frame`, and Veo animates those pixels, so the mascot in frame 1 is the
mascot for the whole clip. `reference_images` (Veo "ingredients", ASSET type) is
implemented as a probe/fallback only: as of 2026-09 the Developer API has been
reported to accept it only for 16:9 on the non-Fast model, so it is not wired
into the pipeline until `scripts/run_video.py --refs` proves it at 9:16 on Fast.

Per the agreed split, this returns asset **bytes** + metadata; the R2 upload is
the storage/pipeline layer's job (Jacob's), not this tool's. Intentionally
deviates from tools/CLAUDE.md ("upload to R2 / don't return bytes").

Note: `generate_audio` is a Vertex-only param (rejected by the Developer API), so
Veo applies its own default here (3.1 generates audio).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from google.genai import types

from app.genai_client import MODEL_VIDEO, get_genai_client, with_retry
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.tools import RefImage, ToolError

_POLL_SECONDS = 10
_DEFAULT_DURATION = 8
# Veo 3.1 Fast (preview) latency is highly variable (~90s to many minutes). Cap
# the poll so a stuck operation raises a clear error instead of hanging forever.
_TIMEOUT_SECONDS = 360
_MAX_REFERENCE_IMAGES = 3  # Veo limit for ASSET reference images


class VideoRequest(MeterRequest):
    prompt: str
    aspect_ratio: str = "9:16"
    duration_seconds: int = _DEFAULT_DURATION
    first_frame: RefImage | None = None
    reference_images: list[RefImage] = []


class VideoResult(MeteredResult):
    video_bytes: bytes
    mime_type: str


def _to_image(ref: RefImage) -> types.Image:
    return types.Image(image_bytes=ref.data, mime_type=ref.mime_type)


async def render_video(
    prompt: str,
    aspect_ratio: str = "9:16",
    duration_seconds: int = _DEFAULT_DURATION,
    *,
    first_frame: RefImage | None = None,
    reference_images: Sequence[RefImage] | None = None,
) -> VideoResult:
    """Core Veo render — start the operation, poll to completion. No DB / meter.

    `first_frame` → image-to-video (primary). `reference_images` → Veo ASSET
    references (probe only). The API rejects the two together, so we do too.
    """
    refs = list(reference_images or ())
    if first_frame is not None and refs:
        raise ToolError("Veo accepts either a first frame or reference images, not both.")
    if len(refs) > _MAX_REFERENCE_IMAGES:
        raise ToolError(f"Veo accepts at most {_MAX_REFERENCE_IMAGES} reference images.")

    client = get_genai_client()
    config = types.GenerateVideosConfig(
        number_of_videos=1,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        reference_images=[
            types.VideoGenerationReferenceImage(
                image=_to_image(r), reference_type=types.VideoGenerationReferenceType.ASSET
            )
            for r in refs
        ]
        or None,
    )
    image = _to_image(first_frame) if first_frame is not None else None
    operation = await with_retry(
        lambda: client.aio.models.generate_videos(
            model=MODEL_VIDEO, prompt=prompt, image=image, config=config
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
    return await render_video(
        req.prompt,
        req.aspect_ratio,
        req.duration_seconds,
        first_frame=req.first_frame,
        reference_images=req.reference_images,
    )
