"""Burn an attractive hook caption onto images and video clips.

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
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "Montserrat-Bold.ttf"

_MAX_CHARS = 16
_FILL = (255, 255, 255)        # white
_BRAND_BLUE = (30, 110, 180)   # #1E6EB4 — ocean blue, not navy
_SHADOW = (0, 0, 0, 100)       # semi-transparent black drop shadow


class OverlayError(RuntimeError):
    """Raised when the hook overlay fails."""


def _wrap(text: str, max_chars: int = _MAX_CHARS) -> str:
    lines: list[str] = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > max_chars:
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


def _draw_hook(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    img_w: int,
    img_h: int,
    y_frac: float,
    line_spacing: int = 12,
) -> None:
    """Draw `text` centred horizontally at `y_frac` of image height."""
    lines = text.split("\n")
    line_h = int(font.size) + line_spacing
    total_h = line_h * len(lines) - line_spacing
    y = int(img_h * y_frac - total_h / 2)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (img_w - text_w) // 2

        # Drop shadow
        draw.text((x + 2, y + 2), line, font=font, fill=_SHADOW)
        # Outline (simulate border)
        for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
            draw.text((x + dx, y + dy), line, font=font, fill=(*_BRAND_BLUE, 255))
        # White fill
        draw.text((x, y), line, font=font, fill=(*_FILL, 255))
        y += line_h


def _render_overlay_png(
    width: int, height: int, hook: str, y_frac: float, scale: float = 1.0
) -> bytes:
    """Return a transparent RGBA PNG with the hook text drawn on it."""
    font_size = max(14, int((height // 20) * scale))
    font = _load_font(font_size)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    _draw_hook(draw, _wrap(hook), font, width, height, y_frac)
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


async def overlay_hook_image(
    image_bytes: bytes, hook: str, ext: str = ".jpg", scale: float = 1.0
) -> bytes:
    """Return the still with `hook` burned in centred (Montserrat, white).

    `scale` multiplies the auto-computed font size (1.0 = default; <1 smaller).
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    font_size = max(14, int((img.height // 20) * scale))
    font = _load_font(font_size)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    _draw_hook(draw, _wrap(hook), font, img.width, img.height, 0.5)
    composited = Image.alpha_composite(img, overlay)

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

        # Get dimensions via ffprobe
        probe = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            "in.mp4",
            cwd=d,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await probe.communicate()
        try:
            w, h = (int(x) for x in stdout.decode().strip().split(","))
        except ValueError:
            w, h = 720, 1280  # fallback for 9:16

        overlay_png = _render_overlay_png(w, h, hook, y_frac=0.22, scale=scale)
        (d / "overlay.png").write_bytes(overlay_png)

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
