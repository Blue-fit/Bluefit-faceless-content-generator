"""Distill recent edit instructions into durable brand rules (learning loop).

Phase 2, PRD §4.5: Gemini Flash reads the client's recent edit requests and extracts
standing preferences as rule candidates. Paid (Flash) -> @meter("extraction").
The candidates are upserted into the `rules` table by `apply.py`.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.genai_client import MODEL_FLASH, get_genai_client
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.tools import ToolError

_PROMPT = Path(__file__).resolve().parents[1] / "agents" / "prompts" / "learning_extract.md"


class RuleCandidate(BaseModel):
    text: str
    confidence: float


class ExtractRequest(MeterRequest):
    instructions: list[str]


class ExtractResult(MeteredResult):
    candidates: list[RuleCandidate]


@meter("extraction")
async def extract_rules(req: ExtractRequest) -> ExtractResult:
    """Extract durable rule candidates from recent edit instructions."""
    if not req.instructions:
        return ExtractResult(model=MODEL_FLASH, cost_eur=Decimal("0"), candidates=[])

    listing = "\n".join(f"- {i}" for i in req.instructions)
    contents = (
        f"{_PROMPT.read_text(encoding='utf-8')}\n\n"
        f"## Recent edit instructions\n{listing}"
    )
    response = await get_genai_client().aio.models.generate_content(
        model=MODEL_FLASH, contents=contents
    )
    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(raw)
        candidates = [RuleCandidate.model_validate(c) for c in data]
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ToolError(f"learning extract: bad candidate JSON: {exc}") from exc

    usage = response.usage_metadata
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    return ExtractResult(
        model=MODEL_FLASH,
        cost_eur=pricing.text_cost(MODEL_FLASH, in_tok, out_tok),
        candidates=candidates,
    )
