"""Agent/pipeline tools. Each tool is one file; paid tools are @meter-wrapped."""

from __future__ import annotations

from pydantic import BaseModel


class ToolError(Exception):
    """Raised on a user-facing tool failure (tools/CLAUDE.md)."""


class RefImage(BaseModel):
    """An image handed to a generator as a reference (bytes + MIME type).

    Shared by the image tool (multimodal parts), the video tool (first frame /
    reference images) and the mascot loader — so it lives here, not in one tool.
    """

    data: bytes
    mime_type: str
