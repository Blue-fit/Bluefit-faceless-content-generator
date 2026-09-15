"""The Blue Fit mascot reference photos — the character every post is built around.

The photos live in `backend/assets/mascot/` (committed, pre-resized to ~1024 px).
They are handed to Nano Banana as reference images so the generated mascot is
*this* plush costume, not a generic blue bear; the video then animates the
resulting still (see `app.agents.render`). Loaded once per process, like the
brand font in `tools/overlay_hook.py`.
"""

from __future__ import annotations

import functools
import hashlib
from pathlib import Path

from app.tools import RefImage

_DIR = Path(__file__).resolve().parents[2] / "assets" / "mascot"
_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


class MascotAssetsMissing(RuntimeError):
    """Raised when no mascot reference photo is deployed — a fatal precondition."""


@functools.cache
def load_mascot_refs() -> tuple[RefImage, ...]:
    """All mascot photos, sorted by filename (so `01-front.jpg` leads)."""
    files = sorted(p for p in _DIR.glob("*") if p.suffix.lower() in _MIME)
    if not files:
        raise MascotAssetsMissing(
            f"No mascot reference photos in {_DIR} — add the resized JPEG/PNG files."
        )
    return tuple(
        RefImage(data=p.read_bytes(), mime_type=_MIME[p.suffix.lower()]) for p in files
    )


@functools.cache
def mascot_refs_version() -> str:
    """Short fingerprint of the deployed photos, stamped into each post's reasoning."""
    digest = hashlib.sha1()
    for ref in load_mascot_refs():
        digest.update(ref.data)
    return digest.hexdigest()[:12]
