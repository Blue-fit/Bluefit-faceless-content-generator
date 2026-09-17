"""Render one post's base asset with the mascot in it.

Shared by the weekly pipeline and chat edits — the one place that knows how the
mascot gets into a render, so an edit can never quietly regress to a mascot-less
asset:

- image: Gemini 3 Pro Image, prompt + the mascot reference photos. When a `hook`
  is given the model renders it in-picture as designed typography (headline,
  highlighted keyword, handwritten CTA, hand-drawn arrow — decisions/010), and a
  Flash read-back verifies the words are spelled exactly; a mismatch re-rolls.
- video: a text-free still first (clean top), then Omni image-to-video from that
  still. The still pins the mascot's likeness; the hook is overlaid afterwards.

Both underlying tools stay @meter-wrapped; this is orchestration, not a tool.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from decimal import Decimal
from uuid import UUID

import structlog
from pydantic import BaseModel

from app.agents.mascot import load_mascot_refs
from app.agents.prompt_builder import (
    build_image_prompt,
    build_video_prompt,
    split_hook,
    typography_block,
)
from app.meter import Trigger
from app.tools import RefImage
from app.tools.generate_image import ImageRequest, ImageResult, generate_image
from app.tools.generate_video import VideoRequest, generate_video
from app.tools.read_image_text import ReadImageTextRequest, read_image_text

logger = structlog.get_logger(__name__)

_ASPECT = "9:16"
# Model-rendered text is occasionally misspelled; each extra attempt is one image
# call, so keep this small — the read-back usually passes first time.
_TEXT_ATTEMPTS = 3


class BaseAsset(BaseModel):
    data: bytes
    model: str
    cost_eur: Decimal
    ext: str
    content_type: str


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def text_matches(hook: str, transcript: str) -> bool:
    """True when the headline and CTA of `hook` both appear verbatim in `transcript`."""
    headline, cta = split_hook(hook)
    seen = _norm(transcript)
    return _norm(headline) in seen and _norm(cta) in seen


def _ext(mime_type: str) -> str:
    return ".jpg" if "jpeg" in mime_type else ".png"


async def _still(
    scene: str, *, post_id: UUID | None, trigger: Trigger, hook: str | None = None
) -> ImageResult:
    return await generate_image(
        ImageRequest(
            prompt=build_image_prompt(scene, hook=hook),
            aspect_ratio=_ASPECT,
            reference_images=list(load_mascot_refs()),
            trigger=trigger,
            post_id=post_id,
        )
    )


async def _verified(
    render: Callable[[], Awaitable[ImageResult]],
    hook: str,
    *,
    post_id: UUID | None,
    trigger: Trigger,
) -> tuple[ImageResult, Decimal]:
    """Run `render` until the read-back shows `hook` spelled exactly (or attempts run out).

    Returns the last image and the total spend (every image attempt + every read-back).
    Best-effort: after the last attempt the image is kept even if the text still
    mismatches — a slightly off headline beats no post, and the warning is logged.
    """
    total = Decimal(0)
    still: ImageResult | None = None
    for attempt in range(1, _TEXT_ATTEMPTS + 1):
        still = await render()
        total += still.cost_eur
        check = await read_image_text(
            ReadImageTextRequest(
                image=still.image_bytes, mime_type=still.mime_type, trigger=trigger, post_id=post_id
            )
        )
        total += check.cost_eur
        if text_matches(hook, check.text):
            return still, total
        logger.warning(
            "render.text_mismatch", attempt=attempt, expected=hook, read=check.text[:160]
        )
    assert still is not None
    return still, total


async def render_base(
    post_type: str,
    scene: str,
    motion: str | None,
    *,
    post_id: UUID | None,
    trigger: Trigger,
    duration_seconds: int = 8,
    hook: str | None = None,
) -> BaseAsset:
    """Render the asset for `scene`.

    Image: with `hook`, the typography is in the picture (verified); this IS the
    final asset. Video: a clean still is animated; the caller overlays the hook.
    """
    if post_type == "image":
        if hook:
            still, cost = await _verified(
                lambda: _still(scene, post_id=post_id, trigger=trigger, hook=hook),
                hook,
                post_id=post_id,
                trigger=trigger,
            )
        else:
            still = await _still(scene, post_id=post_id, trigger=trigger)
            cost = still.cost_eur
        return BaseAsset(
            data=still.image_bytes,
            model=still.model,
            cost_eur=cost,
            ext=_ext(still.mime_type),
            content_type=still.mime_type,
        )

    still = await _still(scene, post_id=post_id, trigger=trigger)  # text-free opening frame
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


async def edit_still_text(
    image: bytes,
    mime_type: str,
    hook: str,
    *,
    post_id: UUID | None,
    trigger: Trigger,
    size_hint: str | None = None,
) -> BaseAsset:
    """Change ONLY the on-image typography of an existing image (Pro Image edit mode).

    The current final is passed as the image to edit with an instruction to keep the
    mascot, scene, props and layout identical and re-render the text as `hook`.
    Verified by read-back like a fresh render. Used for hook / text-size edits on
    images, where the text lives in the picture rather than in an overlay.
    """
    instruction = (
        "Edit this image. Keep the mascot, the scene, every prop, the lighting, the "
        "colours and the layout exactly identical. Change ONLY the on-image text so it "
        f"matches this specification:\n\n{typography_block(hook)}"
        + (f"\n\n{size_hint}" if size_hint else "")
    )

    async def render() -> ImageResult:
        return await generate_image(
            ImageRequest(
                prompt=instruction,
                aspect_ratio=_ASPECT,
                reference_images=[RefImage(data=image, mime_type=mime_type)],
                trigger=trigger,
                post_id=post_id,
            )
        )

    still, cost = await _verified(render, hook, post_id=post_id, trigger=trigger)
    return BaseAsset(
        data=still.image_bytes,
        model=still.model,
        cost_eur=cost,
        ext=_ext(still.mime_type),
        content_type=still.mime_type,
    )
