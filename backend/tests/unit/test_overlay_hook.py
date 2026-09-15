"""Hook overlay text layout: line breaks, emoji-aware wrapping, and the no-emoji-font fallback."""

import io

import pytest
from PIL import Image

from app.tools import overlay_hook
from app.tools.overlay_hook import _runs, _wrap

DOWN = "\U0001F447"


def test_wrap_honours_explicit_line_break_between_hook_and_cta() -> None:
    lines = _wrap(f"Waarom de trap gratis krachttraining is?\nLees de caption {DOWN}").split("\n")
    assert lines[-1] == f"Lees de caption {DOWN}"  # CTA is its own, last line
    assert all(len(line) <= 16 + 2 for line in lines)  # +2: emoji + space are free


def test_wrap_does_not_count_emoji_toward_width() -> None:
    # "Lees de caption" is 15 chars; with the emoji it must NOT wrap the emoji off.
    assert _wrap(f"Lees de caption {DOWN}") == f"Lees de caption {DOWN}"
    assert _wrap("Lees de caption ↓ ↓") != "Lees de caption ↓ ↓"  # plain chars still count


def test_runs_split_text_and_emoji() -> None:
    assert _runs(f"Lees de caption {DOWN}") == [("Lees de caption ", False), (DOWN, True)]
    assert _runs("Lees de caption \u2b07\ufe0f") == [("Lees de caption ", False), ("\u2b07", True)]


def test_emoji_font_is_bundled_and_loads() -> None:
    font = overlay_hook._load_emoji_font()
    assert font is not None and "NotoColorEmoji" in font.path


def test_fallback_to_plain_arrow_without_emoji_font(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overlay_hook, "_load_emoji_font", lambda: None)
    canvas = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    font = overlay_hook._load_font(32)
    # Must not raise, and must draw *something* (the ↓ substitute) rather than nothing.
    overlay_hook._draw_hook(canvas, f"Lees de caption {DOWN}", font, 0.5)
    assert canvas.getbbox() is not None


@pytest.mark.asyncio
async def test_overlay_image_renders_emoji_pixels() -> None:
    base = Image.new("RGB", (360, 640), (30, 110, 180))
    buf = io.BytesIO()
    base.save(buf, "JPEG")
    out = Image.open(io.BytesIO(await overlay_hook.overlay_hook_image(buf.getvalue(), f"Hook\nLees de caption {DOWN}", ".jpg")))
    # The pointing-hand emoji is yellow/orange: assert some warm pixels exist (text is white/blue only).
    px = [p for p in out.convert("RGB").getdata() if p[0] > 200 and 120 < p[1] < 210 and p[2] < 90]
    assert len(px) > 50
