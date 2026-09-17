"""Model-rendered typography on images: hook splitting, prompt tails, read-back
verification with re-roll, and in-place text edits (decisions/010)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.agents import render
from app.agents.prompt_builder import build_image_prompt, split_hook, typography_block
from app.tools import RefImage
from app.tools.generate_image import ImageRequest, ImageResult
from app.tools.read_image_text import ReadImageTextRequest, ReadImageTextResult

DOWN = "\U0001F447"
HOOK = f"Is natuurlijk eten de 80% regel?\nLees de caption {DOWN}"
_REFS = (RefImage(data=b"ref", mime_type="image/jpeg"),)


# ---- prompt side ---------------------------------------------------------------


def test_split_hook_separates_headline_and_cta_and_strips_pointers() -> None:
    assert split_hook(HOOK) == ("Is natuurlijk eten de 80% regel?", "Lees de caption")
    assert split_hook("Alleen een kop") == ("Alleen een kop", "Lees de caption")  # default CTA
    assert split_hook("Kop\nAntwoord ↓") == ("Kop", "Antwoord")


def test_image_prompt_with_hook_renders_typography_and_no_clean_top_rule() -> None:
    prompt = build_image_prompt("The Blue Fit mascot at a market.", hook=HOOK)
    assert '"Is natuurlijk eten de 80% regel?"' in prompt
    assert '"Lees de caption"' in prompt and "hand-drawn curved arrow" in prompt
    assert DOWN not in prompt  # the model draws its own arrow
    assert "No on-image text" not in prompt


def test_image_prompt_without_hook_keeps_the_top_clean() -> None:
    prompt = build_image_prompt("The Blue Fit mascot at a desk.")
    assert "No on-image text" in prompt and "top quarter" in prompt
    assert "highlight pill" not in prompt


def test_typography_block_has_no_unfilled_placeholders() -> None:
    block = typography_block(HOOK)
    assert "{hook_line}" not in block and "{cta}" not in block


# ---- verification + re-roll ------------------------------------------------------


def test_text_matches_is_whitespace_and_case_tolerant() -> None:
    assert render.text_matches(HOOK, "IS NATUURLIJK ETEN\nDE 80% REGEL?\nlees de caption\nLOKAAL")
    assert not render.text_matches(HOOK, "Is natuurlijk eten de 80% regels?\nLees de caption")
    assert not render.text_matches(HOOK, "Is natuurlijk eten de 80% regel?")  # CTA missing


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"images": [], "reads": [], "transcripts": []}

    async def fake_image(req: ImageRequest) -> ImageResult:
        state["images"].append(req)
        return ImageResult(
            model="img", cost_eur=Decimal("0.134"),
            image_bytes=f"still{len(state['images'])}".encode(), mime_type="image/jpeg",
        )

    async def fake_read(req: ReadImageTextRequest) -> ReadImageTextResult:
        state["reads"].append(req)
        text = state["transcripts"].pop(0)
        return ReadImageTextResult(model="flash", cost_eur=Decimal("0.001"), text=text)

    monkeypatch.setattr(render, "load_mascot_refs", lambda: _REFS)
    monkeypatch.setattr(render, "generate_image", fake_image)
    monkeypatch.setattr(render, "read_image_text", fake_read)
    return state


@pytest.mark.asyncio
async def test_image_with_hook_is_verified_and_accepted_first_time(fakes: dict[str, Any]) -> None:
    fakes["transcripts"] = ["Is natuurlijk eten\nde 80% regel?\nLees de caption"]
    asset = await render.render_base("image", "scene", None, post_id=uuid4(), trigger="cron", hook=HOOK)

    assert len(fakes["images"]) == 1 and len(fakes["reads"]) == 1
    assert '"Is natuurlijk eten de 80% regel?"' in fakes["images"][0].prompt
    assert fakes["reads"][0].image == b"still1"
    assert asset.data == b"still1"
    assert asset.cost_eur == Decimal("0.135")  # one image + one read-back


@pytest.mark.asyncio
async def test_misspelled_text_rerolls_until_exact(fakes: dict[str, Any]) -> None:
    fakes["transcripts"] = [
        "Is natuurlijk eten de 80% regels?\nLees de caption",  # typo -> re-roll
        "Is natuurlijk eten de 80% regel?\nLees de caption",   # exact -> accept
    ]
    asset = await render.render_base("image", "scene", None, post_id=None, trigger="edit", hook=HOOK)

    assert len(fakes["images"]) == 2 and asset.data == b"still2"
    assert asset.cost_eur == Decimal("0.134") * 2 + Decimal("0.001") * 2


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts_but_returns_last_image(fakes: dict[str, Any]) -> None:
    fakes["transcripts"] = ["wrong"] * render._TEXT_ATTEMPTS
    asset = await render.render_base("image", "scene", None, post_id=None, trigger="cron", hook=HOOK)
    assert len(fakes["images"]) == render._TEXT_ATTEMPTS
    assert asset.data == f"still{render._TEXT_ATTEMPTS}".encode()


@pytest.mark.asyncio
async def test_video_still_never_carries_the_hook(fakes: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    from app.tools.generate_video import VideoRequest, VideoResult

    async def fake_video(req: VideoRequest) -> VideoResult:
        return VideoResult(model="omni", cost_eur=Decimal("0.8"), video_bytes=b"clip", mime_type="video/mp4")

    monkeypatch.setattr(render, "generate_video", fake_video)
    await render.render_base("video", "scene", "push-in", post_id=None, trigger="cron", hook=None)
    assert "top quarter" in fakes["images"][0].prompt and fakes["reads"] == []


@pytest.mark.asyncio
async def test_edit_still_text_edits_the_current_image_in_place(fakes: dict[str, Any]) -> None:
    fakes["transcripts"] = ["Nieuwe kop\nLees de caption"]
    asset = await render.edit_still_text(
        b"current", "image/jpeg", f"Nieuwe kop\nLees de caption {DOWN}",
        post_id=None, trigger="edit", size_hint="Also make the text 20% smaller.",
    )
    req = fakes["images"][0]
    assert req.reference_images == [RefImage(data=b"current", mime_type="image/jpeg")]
    assert "exactly identical" in req.prompt and '"Nieuwe kop"' in req.prompt
    assert "20% smaller" in req.prompt
    assert asset.data == b"still1"
