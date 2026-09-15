"""render_base: the one place the mascot enters a render (pipeline + edits)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.agents import render
from app.tools import RefImage
from app.tools.generate_image import ImageRequest, ImageResult
from app.tools.generate_video import VideoRequest, VideoResult

_REFS = (RefImage(data=b"ref", mime_type="image/jpeg"),)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    seen: list[Any] = []

    async def fake_image(req: ImageRequest) -> ImageResult:
        seen.append(req)
        return ImageResult(
            model="img", cost_eur=Decimal("0.039"), image_bytes=b"still", mime_type="image/jpeg"
        )

    async def fake_video(req: VideoRequest) -> VideoResult:
        seen.append(req)
        return VideoResult(
            model="veo", cost_eur=Decimal("0.80"), video_bytes=b"clip", mime_type="video/mp4"
        )

    monkeypatch.setattr(render, "load_mascot_refs", lambda: _REFS)
    monkeypatch.setattr(render, "generate_image", fake_image)
    monkeypatch.setattr(render, "generate_video", fake_video)
    return seen


@pytest.mark.asyncio
async def test_image_render_passes_mascot_refs(calls: list[Any]) -> None:
    asset = await render.render_base("image", "scene", None, post_id=uuid4(), trigger="cron")

    assert len(calls) == 1 and isinstance(calls[0], ImageRequest)
    assert calls[0].reference_images == list(_REFS)
    assert calls[0].prompt.startswith("scene")
    assert (asset.data, asset.ext, asset.cost_eur) == (b"still", ".jpg", Decimal("0.039"))


@pytest.mark.asyncio
async def test_video_render_is_still_then_first_frame(calls: list[Any]) -> None:
    pid = uuid4()
    asset = await render.render_base("video", "scene", "push-in", post_id=pid, trigger="edit")

    assert [type(c) for c in calls] == [ImageRequest, VideoRequest]
    still, vid = calls
    assert still.reference_images == list(_REFS) and still.trigger == "edit"
    assert vid.first_frame == RefImage(data=b"still", mime_type="image/jpeg")
    assert vid.reference_images == [] and vid.post_id == pid
    assert "Camera & motion: push-in" in vid.prompt
    assert (asset.data, asset.ext) == (b"clip", ".mp4")
    assert asset.cost_eur == Decimal("0.839")  # still + clip
