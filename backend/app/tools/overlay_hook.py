"""Burn an attractive hook caption onto a video clip with ffmpeg drawtext.

The hook is overlaid in post (not rendered by Veo, which can't spell reliably) so
it is always correctly spelled in the brand font (Montserrat). This is a local
ffmpeg call — not a paid API, so no @meter.

Deploy dependency (Render): ffmpeg must be on PATH.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

_FONT = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "Montserrat-Bold.ttf"

# Max characters per line — keeps the hook inside a narrow 9:16 (Reel) frame.
_MAX_CHARS = 16

# Brand text colours: white fill + ocean-blue outline from the Blue Fit logo
# (ocean blue, not navy — matches the requirements doc's primary palette).
_FILL = "white"
_BRAND_BLUE = "0x1E6EB4"


class OverlayError(RuntimeError):
    """Raised when the ffmpeg hook overlay fails."""


def _wrap(text: str, max_chars: int = _MAX_CHARS) -> str:
    """Greedily wrap the hook so every line fits the narrow vertical frame width."""
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


async def _run_ffmpeg(args: list[str], cwd: Path, out: Path) -> bytes:
    """Run ffmpeg in `cwd` and return `out` bytes, raising OverlayError on failure."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", *args,
        cwd=cwd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0 or not out.exists():
        raise OverlayError((err or b"").decode("utf-8", "replace")[-400:])
    return out.read_bytes()


async def overlay_hook(video_bytes: bytes, hook: str) -> bytes:
    """Return the clip with `hook` burned in (Montserrat, white, upper third, first 3s).

    Sized and wrapped for a 9:16 Reel; runs ffmpeg in a temp dir with bare
    filenames (cwd-relative) so there is no cross-platform path escaping.
    """
    if not _FONT.exists():
        raise OverlayError(f"Brand font not found: {_FONT}")

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        shutil.copy(_FONT, d / "font.ttf")
        (d / "in.mp4").write_bytes(video_bytes)
        (d / "hook.txt").write_text(_wrap(hook), encoding="utf-8")

        draw = (
            f"drawtext=fontfile=font.ttf:textfile=hook.txt:fontcolor={_FILL}:"
            f"bordercolor={_BRAND_BLUE}:borderw=3:"
            "fontsize=h/22:shadowcolor=black@0.4:shadowx=2:shadowy=2:line_spacing=12:"
            "x=(w-text_w)/2:y=h*0.20:enable='lt(t,3)'"
        )
        return await _run_ffmpeg(
            ["-i", "in.mp4", "-vf", draw, "-c:a", "copy", "out.mp4"], d, d / "out.mp4"
        )


async def overlay_hook_image(image_bytes: bytes, hook: str, ext: str = ".jpg") -> bytes:
    """Return the still with `hook` burned in centered (Montserrat, white).

    The brand wants a "pakkende oneliner centraal in beeld" on posts, so the
    image hook sits in the centre of the 9:16 frame (vs the video's upper third).
    """
    if not _FONT.exists():
        raise OverlayError(f"Brand font not found: {_FONT}")

    name = f"out{ext}"
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        shutil.copy(_FONT, d / "font.ttf")
        (d / f"in{ext}").write_bytes(image_bytes)
        (d / "hook.txt").write_text(_wrap(hook), encoding="utf-8")

        draw = (
            f"drawtext=fontfile=font.ttf:textfile=hook.txt:fontcolor={_FILL}:"
            f"bordercolor={_BRAND_BLUE}:borderw=4:"
            "fontsize=h/20:shadowcolor=black@0.4:shadowx=2:shadowy=2:line_spacing=14:"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        )
        return await _run_ffmpeg(
            ["-i", f"in{ext}", "-vf", draw, "-frames:v", "1", name], d, d / name
        )
