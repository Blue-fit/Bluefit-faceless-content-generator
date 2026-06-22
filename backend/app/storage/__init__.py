"""Asset storage seam. Jacob's R2 impl lives in r2.py; pipeline/edit take this.

The `AssetUploader` Protocol is the boundary between content generation (ours) and
binary storage (Jacob's R2). Producers depend on this interface; tests pass a fake,
production passes the R2 implementation.
"""

from __future__ import annotations

from typing import Protocol


class AssetUploader(Protocol):
    """Stores a binary asset and returns its URL."""

    async def upload(self, *, data: bytes, key: str, content_type: str) -> str: ...
