"""Explain why a post was made — Flash renders its reasoning_blob into prose.

Phase 2 transparency tool (PRD §4.6). Reads a post version's structured
reasoning_blob (written at generation time) and has Gemini Flash turn it into a
plain-English "why we made this" for the client. Paid (Flash) -> @meter("explain").
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from app.db.connection import get_pool
from app.db.repositories.post_versions import get_version
from app.genai_client import MODEL_FLASH, get_genai_client
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.tools import ToolError

_PROMPT = Path(__file__).resolve().parents[1] / "agents" / "prompts" / "explain_render.md"


class ExplainRequest(MeterRequest):
    post_version_id: UUID


class ExplainResult(MeteredResult):
    explanation: str


@meter("explain")
async def explain(req: ExplainRequest) -> ExplainResult:
    """Render the post version's reasoning_blob into a human-readable explanation."""
    async with get_pool().acquire() as conn:
        version = await get_version(conn, req.post_version_id)
    if version is None:
        raise ToolError(f"post_version {req.post_version_id} not found.")
    if not version.reasoning_blob:
        raise ToolError(f"post_version {req.post_version_id} has no reasoning_blob.")

    blob_json = json.dumps(version.reasoning_blob, ensure_ascii=False, indent=2)
    contents = f"{_PROMPT.read_text(encoding='utf-8')}\n\n## Reasoning record (JSON)\n{blob_json}"
    response = await get_genai_client().aio.models.generate_content(
        model=MODEL_FLASH, contents=contents
    )
    text = (response.text or "").strip()
    if not text:
        raise ToolError("explain: Flash returned no text.")

    usage = response.usage_metadata
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    return ExplainResult(
        model=MODEL_FLASH,
        cost_eur=pricing.text_cost(MODEL_FLASH, in_tok, out_tok),
        explanation=text,
    )
