"""Assemble final generation prompts: a PostSpec scene + the brand style block.

The generator writes the *scene only*; this appends the immutable brand style
block so brand consistency lives in code rather than the LLM. To avoid
duplication, the brand visual core is one shared base (`style_block.md`) and each
format adds a short tail (`style_block_image.md` / `style_block_video.md`). Source
of the style text: docs/references/brand-style-kit.md.
"""

from __future__ import annotations

from pathlib import Path

_PROMPTS = Path(__file__).parent / "prompts"
_STYLE_BASE = (_PROMPTS / "style_block.md").read_text(encoding="utf-8").strip()
_STYLE_IMAGE = (_PROMPTS / "style_block_image.md").read_text(encoding="utf-8").strip()
_STYLE_VIDEO = (_PROMPTS / "style_block_video.md").read_text(encoding="utf-8").strip()


def build_image_prompt(scene_prompt: str) -> str:
    """Final Nano Banana prompt: scene + shared base + image tail."""
    return f"{scene_prompt.strip()}\n\n{_STYLE_BASE}\n\n{_STYLE_IMAGE}"


def build_video_prompt(scene_prompt: str, motion: str | None = None) -> str:
    """Final Veo prompt: scene (+ motion) + shared base + video tail.

    Footage stays clean — the hook is burned on afterward by `tools.overlay_hook`
    (Veo can't render text reliably), not requested from Veo here.
    """
    motion_line = f"\nCamera & motion: {motion.strip()}" if motion else ""
    return f"{scene_prompt.strip()}{motion_line}\n\n{_STYLE_BASE}\n\n{_STYLE_VIDEO}"
