"""Assemble final generation prompts: a PostSpec scene + the brand style block.

The generator writes the *scene only*; this appends the immutable brand style
block so brand consistency lives in code rather than the LLM. To avoid
duplication, the brand visual core is one shared base (`style_block.md`) and each
format adds a short tail:

- image with a hook  -> `style_block_image.md` + `style_block_typography.md`: the
  image model renders the headline / highlighted keyword / handwritten CTA and a
  hand-drawn arrow in-picture (decisions/010).
- image without hook -> `style_block_image.md` + `style_block_clean_top.md`: a
  video's opening frame stays text-free; the hook is overlaid after Omni.
- video              -> `style_block_video.md`.

Source of the style text: docs/references/brand-style-kit.md.
"""

from __future__ import annotations

from pathlib import Path

from app.tools.hook_text import split_hook

_PROMPTS = Path(__file__).parent / "prompts"
_STYLE_BASE = (_PROMPTS / "style_block.md").read_text(encoding="utf-8").strip()
_STYLE_IMAGE = (_PROMPTS / "style_block_image.md").read_text(encoding="utf-8").strip()
_STYLE_VIDEO = (_PROMPTS / "style_block_video.md").read_text(encoding="utf-8").strip()
_STYLE_TYPOGRAPHY = (_PROMPTS / "style_block_typography.md").read_text(encoding="utf-8").strip()
_STYLE_CLEAN_TOP = (_PROMPTS / "style_block_clean_top.md").read_text(encoding="utf-8").strip()

__all__ = ["build_image_prompt", "build_video_prompt", "split_hook", "typography_block"]


def typography_block(hook: str) -> str:
    """The in-picture typography spec for `hook` (headline + CTA)."""
    headline, cta = split_hook(hook)
    return _STYLE_TYPOGRAPHY.replace("{hook_line}", headline).replace("{cta}", cta)


def build_image_prompt(scene_prompt: str, hook: str | None = None) -> str:
    """Final image prompt: scene + shared base + image tail (+ typography or clean top)."""
    tail = typography_block(hook) if hook else _STYLE_CLEAN_TOP
    return f"{scene_prompt.strip()}\n\n{_STYLE_BASE}\n\n{_STYLE_IMAGE}\n\n{tail}"


def build_video_prompt(scene_prompt: str, motion: str | None = None) -> str:
    """Final video prompt: scene (+ motion) + shared base + video tail.

    Footage stays clean — the hook is burned on afterward by `tools.overlay_hook`,
    not requested from the video model here.
    """
    motion_line = f"\nCamera & motion: {motion.strip()}" if motion else ""
    return f"{scene_prompt.strip()}{motion_line}\n\n{_STYLE_BASE}\n\n{_STYLE_VIDEO}"
