"""Hook overlay: line breaks, emoji-aware wrapping, the no-emoji-font fallback, and
the designed video typography (brand-blue headline, pill, handwritten CTA, arrow)."""

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
    assert _runs("Lees de caption ⬇️") == [("Lees de caption ", False), ("⬇", True)]


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


# ---- designed typography (what video overlays use) --------------------------------


@pytest.mark.asyncio
async def test_overlay_image_renders_designed_typography() -> None:
    """Blue headline + pale-blue pill on a light image; no emoji drawn."""
    light = Image.new("RGB", (360, 640), (235, 240, 245))
    buf = io.BytesIO()
    light.save(buf, "JPEG")
    hook = f"Is natuurlijk eten de 80% regel?\nLees de caption {DOWN}"
    out = Image.open(
        io.BytesIO(await overlay_hook.overlay_hook_image(buf.getvalue(), hook, ".jpg"))
    ).convert("RGB")
    px = list(out.getdata())
    blue = [p for p in px if p[2] > 150 and p[0] < 80 and p[1] < 140]  # brand-blue text
    pill = [p for p in px if 200 < p[0] < 225 and 225 < p[1] < 240 and p[2] > 240]
    assert len(blue) > 300 and len(pill) > 100
    assert not [p for p in px if p[0] > 200 and 120 < p[1] < 210 and p[2] < 90]  # no emoji


def test_designed_layer_flips_to_white_on_a_dark_frame() -> None:
    dark = Image.new("RGB", (360, 640), (20, 30, 45))
    layer = overlay_hook.render_designed(dark, "Kop\nLees de caption")
    top = layer.crop((0, 0, 360, 200)).convert("RGBA").getdata()
    assert any(p[3] > 200 and p[0] > 240 and p[1] > 240 and p[2] > 240 for p in top)


def test_designed_layer_stays_in_the_top_band() -> None:
    """The block must clear the mascot: nothing drawn below ~30% of the height."""
    light = Image.new("RGB", (720, 1280), (240, 240, 240))
    layer = overlay_hook.render_designed(
        light, f"De beste wellness routine gebeurt gewoon doordeweeks.\nMeer in caption {DOWN}"
    )
    bbox = layer.getbbox()
    assert bbox is not None and bbox[3] <= 1280 * 0.30


def test_is_dark_top_threshold() -> None:
    assert overlay_hook.is_dark_top(Image.new("RGB", (100, 100), (20, 20, 20)))
    assert not overlay_hook.is_dark_top(Image.new("RGB", (100, 100), (230, 230, 230)))
    # only the top band matters: dark bottom, light top -> not dark
    img = Image.new("RGB", (100, 100), (10, 10, 10))
    img.paste((240, 240, 240), (0, 0, 100, 30))
    assert not overlay_hook.is_dark_top(img)
