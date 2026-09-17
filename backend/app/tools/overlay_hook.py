"""Burn the hook onto images and video clips as designed typography.

The look mirrors what the image model draws in-picture for image posts
(decisions/010): a bold brand-blue headline with the key word on a pale-blue pill,
a smaller handwritten call-to-action and a hand-drawn arrow, in the open space at
the top. Text stays a static graphic layer, so video text edits are free and the
letters never warp under camera motion. A soft glow keeps it legible; if the top
of the frame is dark the palette flips to white.

Images: Pillow draws text directly (no ffmpeg font dependency).
Videos: Pillow renders the text as a transparent PNG overlay; ffmpeg
        composites it onto the clip using the `overlay` filter (no
        `drawtext` / libfreetype required).

Deploy dependency: ffmpeg must be on PATH (for video only).
"""

from __future__ import annotations

import asyncio
import io
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.tools.hook_text import pick_highlight, split_hook

_FONT = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "Montserrat-Bold.ttf"
# Colour-emoji font for the caption call-to-action's pointer (e.g. "Lees de caption
# \U0001F447"). Montserrat has no emoji glyphs, so emoji runs are drawn from this font.
# First the bundled Noto (what Render/Linux uses), then the Windows dev-box font.
_EMOJI_FONTS = (
    _FONT.parent / "NotoColorEmoji.ttf",
    Path("C:/Windows/Fonts/seguiemj.ttf"),
)
_NOTO_STRIKE = 109  # Noto Color Emoji is a CBDT bitmap font: only this size loads
_SCRIPT_FONT = _FONT.parent / "Caveat-Variable.ttf"  # handwritten CTA (OFL)
_PILL = (214, 232, 250)          # pale blue behind the highlighted word
_HEADLINE_MAX_CHARS = 20         # wider lines than the old sticker style
_DARK_LUMA = 110                 # mean luma of the top band below this -> white text
_VS16 = "\ufe0f"  # emoji variation selector: never drawn, never counted

_MAX_CHARS = 16
# Vertical anchor for the hook (fraction of height). Upper third for both stills
# and clips: inside Instagram's safe zone and clear of the mascot, which fills
# the centre of every frame (the style block reserves headroom for it).
_HOOK_Y_FRAC = 0.22
_FILL = (255, 255, 255)        # white
_BRAND_BLUE = (30, 110, 180)   # #1E6EB4 — ocean blue, not navy
_SHADOW = (0, 0, 0, 100)       # semi-transparent black drop shadow


class OverlayError(RuntimeError):
    """Raised when the hook overlay fails."""


def _is_emoji(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF


def _text_width(s: str) -> int:
    """Characters that count toward wrapping (emoji + selectors are free)."""
    return sum(1 for c in s if not _is_emoji(c) and c != _VS16)


def _wrap(text: str, max_chars: int = _MAX_CHARS) -> str:
    """Word-wrap each line to `max_chars`.

    Explicit newlines are hard breaks (the hook line vs the caption call-to-action
    line). Emoji don't count toward the width: they're drawn separately and must
    never be wrapped off the end of their line.
    """
    lines: list[str] = []
    for para in text.split("\n"):
        current = ""
        for word in para.split():
            if current and _text_width(current) + 1 + _text_width(word) > max_chars:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)
    return "\n".join(lines)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    if not _FONT.exists():
        raise OverlayError(f"Brand font not found: {_FONT}")
    return ImageFont.truetype(str(_FONT), size)


@lru_cache
def _load_emoji_font() -> ImageFont.FreeTypeFont | None:
    """The colour-emoji font, or None (emoji then degrade to a plain arrow)."""
    for path in _EMOJI_FONTS:
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), _NOTO_STRIKE if "Noto" in path.name else 96)
        except OSError:
            continue
    return None


@lru_cache(maxsize=64)
def _emoji_glyph(ch: str, size: int) -> Image.Image | None:
    """Render one emoji as an RGBA tile `size` px tall (None if it can't be drawn)."""
    font = _load_emoji_font()
    if font is None:
        return None
    strike = int(font.size)
    tile = Image.new("RGBA", (strike * 2, strike * 2), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((0, 0), ch, font=font, embedded_color=True)
    bbox = tile.getbbox()
    if not bbox:
        return None
    glyph = tile.crop(bbox)
    return glyph.resize((max(1, round(glyph.width * size / glyph.height)), size), Image.Resampling.LANCZOS)


def _runs(line: str) -> list[tuple[str, bool]]:
    """Split a line into (text, is_emoji) runs; each emoji is its own run."""
    runs: list[tuple[str, bool]] = []
    for ch in line:
        if ch == _VS16:
            continue
        if _is_emoji(ch):
            runs.append((ch, True))
        elif runs and not runs[-1][1]:
            runs[-1] = (runs[-1][0] + ch, False)
        else:
            runs.append((ch, False))
    return runs


def _draw_hook(
    canvas: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont,
    y_frac: float,
    line_spacing: int = 12,
) -> None:
    """Draw `text` centred horizontally at `y_frac` of the canvas height.

    Text runs use the brand font (drop shadow + blue outline + white fill); emoji
    runs are pasted from the colour-emoji font, scaled to the text height. With no
    emoji font available, emoji degrade to a plain "\u2193" so a missing font can
    never break a post.
    """
    if _load_emoji_font() is None:
        text = "".join("\u2193" if _is_emoji(c) else c for c in text if c != _VS16)
    draw = ImageDraw.Draw(canvas)
    img_w, img_h = canvas.size
    size = int(font.size)
    line_h = size + line_spacing
    gap = size // 5  # breathing room before an emoji
    lines = text.split("\n")
    total_h = line_h * len(lines) - line_spacing
    y = int(img_h * y_frac - total_h / 2)

    def run_width(run: str, is_emoji: bool) -> int:
        if is_emoji:
            glyph = _emoji_glyph(run, size)
            return glyph.width + gap if glyph is not None else 0
        bbox = draw.textbbox((0, 0), run, font=font)
        return int(bbox[2] - bbox[0])

    for line in lines:
        runs = _runs(line)
        widths = [run_width(t, e) for t, e in runs]
        x = (img_w - sum(widths)) // 2
        for (t, is_emoji), w in zip(runs, widths, strict=True):
            if is_emoji:
                glyph = _emoji_glyph(t, size)
                if glyph is not None:
                    canvas.alpha_composite(glyph, (x + gap, y))
            else:
                # Drop shadow
                draw.text((x + 2, y + 2), t, font=font, fill=_SHADOW)
                # Outline (simulate border)
                for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
                    draw.text((x + dx, y + dy), t, font=font, fill=(*_BRAND_BLUE, 255))
                # White fill
                draw.text((x, y), t, font=font, fill=(*_FILL, 255))
            x += w
        y += line_h



def _load_script_font(size: int) -> ImageFont.FreeTypeFont:
    """The handwritten CTA font (Caveat Bold); falls back to the brand font."""
    if not _SCRIPT_FONT.exists():
        return _load_font(size)
    font = ImageFont.truetype(str(_SCRIPT_FONT), size)
    try:
        font.set_variation_by_name("Bold")
    except (OSError, ValueError):
        try:
            font.set_variation_by_name(b"Bold")
        except (OSError, ValueError):
            pass
    return font


def is_dark_top(image: Image.Image, band: float = 0.3) -> bool:
    """True when the top `band` of the image is dark (mean luma below threshold)."""
    w, h = image.size
    top = image.convert("L").crop((0, 0, w, max(1, int(h * band)))).resize((32, 8))
    return sum(top.getdata()) / (32 * 8) < _DARK_LUMA


def _bezier(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float],
            steps: int = 24) -> list[tuple[float, float]]:
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        pts.append((x, y))
    return pts


def _draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[float, float], size: int,
                color: tuple[int, int, int, int]) -> None:
    """A hand-drawn-looking curved arrow from `start`, sweeping down toward the mascot."""
    sx, sy = start
    end = (sx + size * 0.55, sy + size * 1.7)
    ctrl = (sx + size * 0.95, sy + size * 0.55)
    pts = _bezier((sx, sy), ctrl, end)
    width = max(3, size // 13)
    draw.line(pts, fill=color, width=width, joint="curve")
    # arrowhead along the final tangent
    tx, ty = end[0] - pts[-3][0], end[1] - pts[-3][1]
    norm = max(1e-6, (tx * tx + ty * ty) ** 0.5)
    tx, ty = tx / norm, ty / norm
    head = size * 0.42
    for side in (-1, 1):
        # rotate the reversed tangent by ~28 degrees to each side
        c, s_ = 0.883, 0.469 * side
        vx, vy = (-tx * c - (-ty) * s_), (-ty * c + (-tx) * s_)
        draw.line([end, (end[0] + vx * head, end[1] + vy * head)], fill=color, width=width)


def render_designed(media: Image.Image, hook: str, scale: float = 1.0) -> Image.Image:
    """Return a transparent RGBA layer the size of `media` with the hook designed on it."""
    w, h = media.size
    dark = is_dark_top(media)
    blue = (30, 110, 180, 255)
    color = (255, 255, 255, 255) if dark else blue
    pill_fill = (255, 255, 255, 95) if dark else (*_PILL, 255)
    glow_color = (0, 0, 0, 150) if dark else (255, 255, 255, 190)

    headline, cta = split_hook(hook)
    key = pick_highlight(headline)
    lines = _wrap(headline, _HEADLINE_MAX_CHARS).split("\n")
    size = max(16, int((h // 26) * scale))
    if len(lines) > 3:  # a long headline: shrink so the block still clears the mascot
        size = max(16, int(size * 3 / len(lines)))
    head_font = _load_font(size)
    cta_font = _load_script_font(int(size * 1.05))
    line_h = int(size * 1.12)
    space = head_font.getlength(" ")

    # ---- layout: (word, x, y, is_key) for the headline
    layout: list[tuple[str, float, float, bool]] = []
    y = float(int(h * 0.065))
    for line in lines:
        words = line.split(" ")
        widths = [head_font.getlength(wd) for wd in words]
        x = (w - (sum(widths) + space * (len(words) - 1))) / 2
        for wd, ww in zip(words, widths, strict=True):
            is_key = bool(key) and wd.strip(".,?!:;\"'()").casefold() == key
            layout.append((wd, x, y, is_key))
            x += ww + space
        y += line_h
    cta_y = y + size * 0.12
    cta_w = cta_font.getlength(cta)
    cta_x = (w - cta_w) / 2 - size * 0.55  # nudge left so the arrow fits on the right

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # ---- pass 1: glow (text drawn in the glow colour, blurred) for legibility
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for wd, x, yy, _ in layout:
        gd.text((x, yy), wd, font=head_font, fill=glow_color)
    gd.text((cta_x, cta_y), cta, font=cta_font, fill=glow_color)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(2, size * 0.16)))
    layer.alpha_composite(glow)

    # ---- pass 2: the highlight pill behind the key word
    draw = ImageDraw.Draw(layer)
    pad = size * 0.14
    for wd, x, yy, is_key in layout:
        if is_key:
            ww = head_font.getlength(wd)
            draw.rounded_rectangle(
                (x - pad, yy - pad * 0.2, x + ww + pad, yy + size * 1.0 + pad * 0.2),
                radius=size * 0.55, fill=pill_fill,
            )

    # ---- pass 3: headline, CTA, arrow
    for wd, x, yy, _ in layout:
        draw.text((x, yy), wd, font=head_font, fill=color)
    draw.text((cta_x, cta_y), cta, font=cta_font, fill=color)
    _draw_arrow(draw, (cta_x + cta_w + size * 0.4, cta_y + size * 0.5), size, color)
    return layer


def _render_overlay_png(first_frame: Image.Image, hook: str, scale: float = 1.0) -> bytes:
    """Return a transparent RGBA PNG (frame-sized) with the hook designed on it."""
    layer = render_designed(first_frame, hook, scale=scale)
    buf = io.BytesIO()
    layer.save(buf, format="PNG")
    return buf.getvalue()


async def overlay_hook_image(
    image_bytes: bytes, hook: str, ext: str = ".jpg", scale: float = 1.0
) -> bytes:
    """Return the still with `hook` burned in (Montserrat, white, upper third).

    `scale` multiplies the auto-computed font size (1.0 = default; <1 smaller).
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    composited = Image.alpha_composite(img, render_designed(img, hook, scale=scale))

    out_mode = "RGB" if ext.lower() in (".jpg", ".jpeg") else "RGBA"
    result = composited.convert(out_mode)
    buf = io.BytesIO()
    fmt = "JPEG" if out_mode == "RGB" else "PNG"
    result.save(buf, format=fmt, quality=95)
    return buf.getvalue()


async def overlay_hook(video_bytes: bytes, hook: str, scale: float = 1.0) -> bytes:
    """Return the clip with `hook` burned in (Montserrat, white, upper third, full clip).

    Uses Pillow to render the text as a transparent PNG overlay, then ffmpeg
    `overlay` to composite it — no libfreetype / drawtext needed. `scale`
    multiplies the auto-computed font size (1.0 = default; <1 smaller).
    """
    # Probe the video dimensions first so the overlay PNG matches.
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        shutil.copy(_FONT, d / "font.ttf")
        (d / "in.mp4").write_bytes(video_bytes)

        # First frame: gives the overlay its exact size and the top-band luma that
        # decides blue-on-light vs white-on-dark.
        grab = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-v", "error", "-i", "in.mp4", "-frames:v", "1", "first.png",
            cwd=d,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await grab.communicate()
        first_png = d / "first.png"
        if first_png.exists():
            first = Image.open(first_png).convert("RGB")
        else:
            first = Image.new("RGB", (720, 1280), (200, 200, 200))  # 9:16 fallback, light

        (d / "overlay.png").write_bytes(_render_overlay_png(first, hook, scale=scale))

        # Composite: show the hook for the entire clip
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-i", "in.mp4",
            "-i", "overlay.png",
            "-filter_complex",
            "[0:v][1:v]overlay=0:0[vout]",
            "-map", "[vout]",
            "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            "out.mp4",
            cwd=d,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        out = d / "out.mp4"
        if proc.returncode != 0 or not out.exists():
            raise OverlayError((err or b"").decode("utf-8", "replace")[-400:])
        return out.read_bytes()
