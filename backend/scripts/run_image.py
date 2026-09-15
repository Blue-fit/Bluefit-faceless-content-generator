"""Render real PostSpec scenes (starring the mascot) to local files you can open.

Usage (from the backend/ directory):

    uv run python scripts/run_image.py

Takes a couple of brand-real image scenes, builds the final prompt (scene + style
block), renders via Nano Banana with the mascot reference photos, burns in the
hook, and saves both the clean and the hooked image to scripts/out/. Uses the
no-DB render core (no DB / R2 / meter). Real paid image calls (~€0.04 each).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

OUT = Path(__file__).resolve().parent / "out"

# Mascot scenes in the shape the generator now produces: (name, scene_prompt, hook).
# The mascot is referred to as "the Blue Fit mascot" only — its look comes from the
# reference photos + style block, never from the scene.
_SCENES: list[tuple[str, str, str]] = [
    (
        "natural_eating",
        "The Blue Fit mascot at a bright home kitchen counter, carefully pouring "
        "water from a glass carafe into the smallest glass on the table, a bowl of "
        "colourful salad beside it; an untouched espresso cup waits further back. "
        "It glances up at the camera mid-pour. Clean daylight, shallow depth of field.",
        "Eerst hydratatie, dan koffie.",
    ),
    (
        "keep_moving",
        "The Blue Fit mascot at the bottom of a wide outdoor stone staircase in a "
        "Dutch city park, one paw on the railing, looking up the steps and back at "
        "the viewer as if to say 'coming?'. An adult jogger, seen from behind, is already "
        "halfway up. Fresh overcast morning light.",
        "Trap of lift? De beer weet het.",
    ),
]


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY not found — create backend/.env first.")

    from app.agents.mascot import load_mascot_refs
    from app.agents.prompt_builder import build_image_prompt
    from app.tools.generate_image import render_image
    from app.tools.overlay_hook import overlay_hook_image

    refs = load_mascot_refs()
    print(f"Using {len(refs)} mascot reference photo(s).")
    OUT.mkdir(exist_ok=True)
    for name, scene, hook in _SCENES:
        print(f"Rendering {name} ...")
        result = await render_image(
            build_image_prompt(scene), aspect_ratio="9:16", reference_images=refs
        )
        ext = ".jpg" if "jpeg" in result.mime_type else ".png"
        base = OUT / f"{name}-base{ext}"
        base.write_bytes(result.image_bytes)
        hooked = OUT / f"{name}{ext}"
        hooked.write_bytes(await overlay_hook_image(result.image_bytes, hook, ext))
        print(f"  saved {hooked}  ({len(result.image_bytes):,} bytes, {result.mime_type})")

    print(f"\nOpen the images in: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
