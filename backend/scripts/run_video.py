"""Render a PostSpec video to a local MP4: clean Veo footage + Montserrat hook.

Usage (from the backend/ directory):

    uv run python scripts/run_video.py

Veo renders clean, faceless footage; the hook is then burned on with ffmpeg
(correctly spelled, brand font) — Veo can't render text reliably. Real, paid,
multi-minute Veo call (~€1-3). Requires ffmpeg on PATH.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

OUT = Path(__file__).resolve().parent / "out"

# A real video PostSpec (Keep Moving), faceless-composed.
_SCENE = (
    "A candid, wide landscape view from behind of a small, multi-generational group "
    "walking together along a riverside trail at sunrise; one wears an ocean blue "
    "windbreaker. Seen from a distance, no faces visible — a vast, natural "
    "environment, shared experience over exertion."
)
_MOTION = "Slow, smooth lateral tracking shot alongside the group; calm, gentle pace."
# Hook teases the caption's payoff (curiosity gap).
_HOOK = "Movement isn't punishment."


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY not found — create backend/.env first.")

    from app.agents.prompt_builder import build_video_prompt
    from app.tools.generate_video import render_video
    from app.tools.overlay_hook import overlay_hook

    OUT.mkdir(exist_ok=True)
    print("Rendering clean Veo footage (a few minutes) ...")
    result = await render_video(
        build_video_prompt(_SCENE, _MOTION), aspect_ratio="9:16", duration_seconds=8
    )
    print("Burning in the hook (Montserrat) ...")
    final = await overlay_hook(result.video_bytes, _HOOK)

    path = OUT / "community.mp4"
    path.write_bytes(final)
    print(f"  saved {path}  ({len(final):,} bytes)")
    print(f"\nPlay it from: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
