"""Agent/pipeline tools. Each tool is one file; paid tools are @meter-wrapped."""

from __future__ import annotations


class ToolError(Exception):
    """Raised on a user-facing tool failure (tools/CLAUDE.md)."""