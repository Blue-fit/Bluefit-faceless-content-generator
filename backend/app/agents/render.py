"""Render one post's base asset (pre-overlay) with the mascot in it.

Shared by the weekly pipeline and chat edits — the one place that knows how the
mascot gets into a render, so an edit can never quietly regress to a mascot-less
asset:

- image: Nano Banana, prompt + the mascot reference photos.
- video: the same still first, then Veo image-to-video from that still. The
  still is what pins the mascot's likeness; Veo animates its pixels.

Both underlying tools stay @meter-wrapped; this is orchestration, not a tool.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.agents.mascot import load_mascot_refs
from app.agents.prompt_builder import build_image_prompt, build_video_prompt
from app.meter import Trigger
from app.tools import RefImage
from app.tools.generate_image import ImageRequest, ImageResult, generate_image
from app.tools.generate_video import VideoRequest, generate_video

_ASPECT = "9:16"


class BaseAsset(BaseModel):
    data: bytes
    model: str
    cost_eur: Decimal
    ext: str
    content_type: str


async def _still(scene: str, *, post_id: UUID, trigger: Trigger) -> ImageResult:
    return await generate_image(
        ImageRequest(
            prompt=build_image_prompt(scene),
            aspect_ratio=_ASPECT,
            reference_images=list(load_mascot_refs()),
            trigger=trigger,
            post_id=post_id,
        )
    )


async def render_base(
    post_type: str,
    scene: str,
    motion: str | None,
    *,
    post_id: UUID,
    trigger: Trigger,
    duration_seconds: int = 8,
) -> BaseAsset:
    """Render the clean asset for `scene` (hook overlay is the caller's job)."""
    still = await _still(scene, post_id=post_id, trigger=trigger)
    if post_type == "image":
        return BaseAsset(
            data=still.image_bytes,
            model=still.model,
            cost_eur=still.cost_eur,
            ext=".jpg" if "jpeg" in still.mime_type else ".png",
            content_type=still.mime_type,
        )

    vid = await generate_video(
        VideoRequest(
            prompt=build_video_prompt(scene, motion),
            aspect_ratio=_ASPECT,
            duration_seconds=duration_seconds,
            first_frame=RefImage(data=still.image_bytes, mime_type=still.mime_type),
            trigger=trigger,
            post_id=post_id,
        )
    )
    return BaseAsset(
        data=vid.video_bytes,
        model=vid.model,
        cost_eur=still.cost_eur + vid.cost_eur,
        ext=".mp4",
        content_type=vid.mime_type or "video/mp4",
    )
