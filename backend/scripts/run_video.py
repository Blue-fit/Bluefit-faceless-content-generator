"""Render a PostSpec video (starring the mascot) to a local MP4.

Usage (from the backend/ directory):

    uv run python scripts/run_video.py          # primary path: still -> image-to-video
    uv run python scripts/run_video.py --refs   # probe: Veo reference images instead

Primary path (what the pipeline does): Nano Banana renders the opening frame with
the mascot reference photos, Veo animates that still (image-to-video), then the
hook is burned on with ffmpeg (Veo can't render text reliably).

`--refs` is a paid probe of Veo's own reference-images ("ingredients") path at
9:16 on the Fast model. The Developer API has been reported to reject that
combination (16:9 / non-Fast only) — a 400 here is an acceptable outcome; record
it in docs/decisions/008. Real, paid, multi-minute Veo call (~€0.80 + €0.04).
Requires ffmpeg on PATH.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

OUT = Path(__file__).resolve().parent / "out"

# A video PostSpec in the new shape: scene = opening frame, motion = camera + beat payoff.
_SCENE = (
    "The Blue Fit mascot standing perfectly still in the middle of a quiet office "
    "floor at lunchtime, beside an empty desk chair, facing the camera; a wall clock "
    "reads 12:30. Two colleagues, seen from behind, are still at their screens. "
    "Bright, clean daylight through big windows."
)
_MOTION = (
    "Slow push-in on the mascot; it looks at the camera, taps an imaginary watch, "
    "then turns and walks briskly toward the exit door, beckoning the viewer to "
    "follow. Upbeat, light percussion; soft footsteps and office room tone."
)
_HOOK = "10 minuten lopen. Nu."


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY not found — create backend/.env first.")

    from app.agents.mascot import load_mascot_refs
    from app.agents.prompt_builder import build_image_prompt, build_video_prompt
    from app.tools import RefImage
    from app.tools.generate_image import render_image
    from app.tools.generate_video import render_video
    from app.tools.overlay_hook import overlay_hook

    probe_refs = "--refs" in sys.argv
    refs = load_mascot_refs()
    OUT.mkdir(exist_ok=True)
    prompt = build_video_prompt(_SCENE, _MOTION)

    if probe_refs:
        print(f"PROBE: Veo reference_images ({len(refs)} photos) at 9:16 on Fast ...")
        result = await render_video(
            prompt, aspect_ratio="9:16", duration_seconds=8, reference_images=refs
        )
        name = "office-refs-probe.mp4"
    else:
        print("Rendering the opening frame with Nano Banana ...")
        still = await render_image(
            build_image_prompt(_SCENE), aspect_ratio="9:16", reference_images=refs
        )
        (OUT / "office-first-frame.jpg").write_bytes(still.image_bytes)
        print("Animating it with Veo (a few minutes) ...")
        result = await render_video(
            prompt,
            aspect_ratio="9:16",
            duration_seconds=8,
            first_frame=RefImage(data=still.image_bytes, mime_type=still.mime_type),
        )
        name = "office.mp4"

    print("Burning in the hook (Montserrat) ...")
    final = await overlay_hook(result.video_bytes, _HOOK)
    path = OUT / name
    path.write_bytes(final)
    print(f"  saved {path}  ({len(final):,} bytes)")
    print(f"\nPlay it from: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
