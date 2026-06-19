"""Render real PostSpec scenes to local PNGs you can open.

Usage (from the backend/ directory):

    uv run python scripts/run_image.py

Takes a couple of brand-real image scenes, builds the final prompt (scene + style
block), renders via Nano Banana, and saves the images to scripts/out/. Uses the
no-DB render core (no DB / R2 / meter). Real paid image calls.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

OUT = Path(__file__).resolve().parent / "out"

# Real image scene_prompts taken from a generator run.
_SCENES: list[tuple[str, str]] = [
    (
        "keep_moving",
        "A lone figure seen from behind in an ocean blue (not navy) lightweight "
        "jacket, pausing at the edge of the Waal river at sunrise to look out over "
        "the open water. Soft morning light on the water; calm and unhurried. Shot "
        "from behind — no face visible.",
    ),
    (
        "natural_eating",
        "A rustic table setting outdoors by the water at golden hour. A vibrant, "
        "plant-rich meal on a ceramic plate with ocean blue glazed edges (not navy); "
        "calm, mindful, abundant.",
    ),
]


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY not found — create backend/.env first.")

    from app.agents.prompt_builder import build_image_prompt
    from app.tools.generate_image import render_image

    OUT.mkdir(exist_ok=True)
    for name, scene in _SCENES:
        print(f"Rendering {name} ...")
        result = await render_image(build_image_prompt(scene), aspect_ratio="9:16")
        ext = ".jpg" if "jpeg" in result.mime_type else ".png"
        path = OUT / f"{name}{ext}"
        path.write_bytes(result.image_bytes)
        print(f"  saved {path}  ({len(result.image_bytes):,} bytes, {result.mime_type})")

    print(f"\nOpen the images in: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())