"""How reference images reach the generators (no network: the client is faked)."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

import pytest
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


# ---- video (Omni via the Interactions API) -----------------------------------


class _FakeInteractions:
    """Fake `client.aio.interactions`: records create() kwargs, completes on first get()."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(id="ix-1", status="in_progress", errors=None, output_video=None)

    async def get(self, _id: str) -> Any:
        video = SimpleNamespace(data=base64.b64encode(b"mp4").decode(), uri=None, mime_type="video/mp4")
        return SimpleNamespace(id=_id, status="completed", errors=None, output_video=video)


@pytest.fixture
def interactions(monkeypatch: pytest.MonkeyPatch) -> _FakeInteractions:
    fake = _FakeInteractions()
    client = SimpleNamespace(aio=SimpleNamespace(interactions=fake))
    monkeypatch.setattr(generate_video, "get_genai_client", lambda: client)
    monkeypatch.setattr(generate_video, "_POLL_SECONDS", 0)
    return fake


@pytest.mark.asyncio
async def test_video_first_frame_is_image_to_video(interactions: _FakeInteractions) -> None:
    result = await generate_video.render_video("motion", first_frame=_REF)

    call = interactions.calls[0]
    assert call["generation_config"] == {"video_config": {"task": "image_to_video"}}
    assert call["input"][0] == {"type": "text", "text": "motion"}
    assert call["input"][1]["type"] == "image"
    assert base64.b64decode(call["input"][1]["data"]) == _REF.data
    assert call["input"][1]["mime_type"] == "image/jpeg"
    assert call["response_format"]["aspect_ratio"] == "9:16"
    assert call["response_format"]["duration"] == "8s"
    assert call["response_modalities"] == ["video"]
    assert result.video_bytes == b"mp4"  # decoded from the inline base64 payload


@pytest.mark.asyncio
async def test_video_reference_images_use_reference_task(interactions: _FakeInteractions) -> None:
    await generate_video.render_video("motion", reference_images=[_REF, _REF])

    call = interactions.calls[0]
    assert call["generation_config"] == {"video_config": {"task": "reference_to_video"}}
    assert [i["type"] for i in call["input"]] == ["text", "image", "image"]


@pytest.mark.asyncio
async def test_video_without_images_is_text_to_video(interactions: _FakeInteractions) -> None:
    await generate_video.render_video("motion")
    assert interactions.calls[0]["generation_config"] == {"video_config": {"task": "text_to_video"}}


@pytest.mark.asyncio
async def test_video_rejects_both_and_too_many(interactions: _FakeInteractions) -> None:
    with pytest.raises(ToolError):
        await generate_video.render_video("m", first_frame=_REF, reference_images=[_REF])
    with pytest.raises(ToolError):
        await generate_video.render_video("m", reference_images=[_REF] * 4)
    assert interactions.calls == []
