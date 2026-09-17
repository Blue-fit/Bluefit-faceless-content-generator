"""Read back the text visible in a rendered image (Gemini Flash vision).

The one guard that makes model-rendered typography safe: after the image model
draws the hook in-picture, this transcribes what it actually wrote so the caller
can re-roll a misspelling instead of shipping it. Paid (Flash) -> @meter
("extraction" — it extracts text from pixels; keeps the usage CHECK constraint
unchanged).
"""

from __future__ import annotations

from google.genai import types

from app.genai_client import MODEL_FLASH, MODEL_PRO, get_genai_client, with_retry
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.tools import ToolError

_PROMPT = (
    "Transcribe every piece of text visible in this image exactly as written, one "
    "item per line. Preserve spelling and punctuation; do not correct anything. "
    "If there is no text, reply with NONE."
)


class ReadImageTextRequest(MeterRequest):
    image: bytes
    mime_type: str


class ReadImageTextResult(MeteredResult):
    text: str


@meter("extraction")
async def read_image_text(req: ReadImageTextRequest) -> ReadImageTextResult:
    """Transcribe the text in `req.image` (empty string when there is none)."""
    client = get_genai_client()
    contents = types.Content(
        role="user",
        parts=[
            types.Part.from_bytes(data=req.image, mime_type=req.mime_type),
            types.Part(text=_PROMPT),
        ],
    )
    try:
        response = await with_retry(
            lambda: client.aio.models.generate_content(model=MODEL_FLASH, contents=contents),
            attempts=3,
        )
    except Exception as exc:  # noqa: BLE001 — fall back to Pro once, then surface
        try:
            response = await with_retry(
                lambda: client.aio.models.generate_content(model=MODEL_PRO, contents=contents),
                attempts=2,
            )
        except Exception:
            raise ToolError(f"read_image_text: {exc}") from exc
    text = (response.text or "").strip()
    usage = response.usage_metadata
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    return ReadImageTextResult(
        model=MODEL_FLASH,
        cost_eur=pricing.text_cost(MODEL_FLASH, in_tok, out_tok),
        text="" if text.upper() == "NONE" else text,
    )
