"""How reference images reach the generators (no network: the client is faked)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import types

from app.tools import RefImage, ToolError
from app.tools import generate_image, generate_video

_REF = RefImage(data=b"\xff\xd8jpeg", mime_type="image/jpeg")


# ---- image ------------------------------------------------------------------


class _FakeImageModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        part = SimpleNamespace(inline_data=SimpleNamespace(data=b"img", mime_type="image/jpeg"))
        return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])


@pytest.fixture
def image_models(monkeypatch: pytest.MonkeyPatch) -> _FakeImageModels:
    models = _FakeImageModels()
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    monkeypatch.setattr(generate_image, "get_genai_client", lambda: client)
    return models


@pytest.mark.asyncio
async def test_image_without_refs_sends_plain_prompt(image_models: _FakeImageModels) -> None:
    await generate_image.render_image("a scene")
    assert image_models.calls[0]["contents"] == "a scene"


@pytest.mark.asyncio
async def test_image_with_refs_sends_text_then_image_parts(
    image_models: _FakeImageModels,
) -> None:
    result = await generate_image.render_image("a scene", reference_images=[_REF, _REF])

    contents = image_models.calls[0]["contents"]
    assert isinstance(contents, list) and len(contents) == 3
    assert contents[0].text == "a scene"
    assert contents[1].inline_data.data == _REF.data
    assert contents[1].inline_data.mime_type == "image/jpeg"
    assert result.image_bytes == b"img"


# ---- video ------------------------------------------------------------------


class _FakeVideoModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_videos(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        video = SimpleNamespace(video_bytes=b"mp4", mime_type="video/mp4")
        return SimpleNamespace(
            done=True, response=SimpleNamespace(generated_videos=[SimpleNamespace(video=video)])
        )


@pytest.fixture
def video_models(monkeypatch: pytest.MonkeyPatch) -> _FakeVideoModels:
    models = _FakeVideoModels()
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    monkeypatch.setattr(generate_video, "get_genai_client", lambda: client)
    return models


@pytest.mark.asyncio
async def test_video_first_frame_goes_in_image_kwarg(video_models: _FakeVideoModels) -> None:
    result = await generate_video.render_video("motion", first_frame=_REF)

    call = video_models.calls[0]
    assert call["prompt"] == "motion"
    assert isinstance(call["image"], types.Image)
    assert call["image"].image_bytes == _REF.data
    assert call["config"].reference_images is None
    assert result.video_bytes == b"mp4"


@pytest.mark.asyncio
async def test_video_reference_images_are_asset_typed(video_models: _FakeVideoModels) -> None:
    await generate_video.render_video("motion", reference_images=[_REF])

    call = video_models.calls[0]
    assert call["image"] is None
    refs = call["config"].reference_images
    assert len(refs) == 1
    assert refs[0].reference_type == types.VideoGenerationReferenceType.ASSET
    assert refs[0].image.image_bytes == _REF.data


@pytest.mark.asyncio
async def test_video_rejects_both_and_too_many(video_models: _FakeVideoModels) -> None:
    with pytest.raises(ToolError):
        await generate_video.render_video("m", first_frame=_REF, reference_images=[_REF])
    with pytest.raises(ToolError):
        await generate_video.render_video("m", reference_images=[_REF] * 4)
    assert video_models.calls == []
