"""Chat routes: POST /chat/{post_id}, GET /chat/{post_id}/history."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import require_auth
from app.db.connection import get_pool
from app.db.repositories.messages import get_messages_for_post, insert_message
from app.meter import SpendCapExceeded
from app.storage.r2 import R2Uploader
from app.tools import ToolError
from app.tools.edit_post import (
    EditError,
    EditNeedsClarification,
    EditRequest,
    edit_post,
)

logger = structlog.get_logger(__name__)

# Transient upstream statuses worth a retry; 429 is quota and is NOT.
_RETRYABLE = {500, 502, 503, 504}


# A failure can happen before (or instead of) a plan, so there is no classifier
# language to lean on. Two canned message sets is all this has to choose between,
# so a marker count is enough; anything unsure stays English.
_DUTCH_MARKERS = frozenset(
    "de het een en niet maar voor met van ook moet kan wat waarom hoe dit deze geen "
    "wel naar bij aan je ik zijn maak meer beter tekst foto filmpje post caption "
    "andere alleen nog even".split()
)


def reply_language(message: str) -> str:
    """"nl" when the client is clearly writing Dutch, else "en"."""
    words = {w.strip(".,!?;:\"'()").lower() for w in message.split()}
    return "nl" if len(words & _DUTCH_MARKERS) >= 2 else "en"


_FAILURES: dict[str, dict[str, str]] = {
    "en": {
        "cap": (
            "This month's generation budget has been reached, so your post was not "
            "changed. Nothing is broken — the cap resets next month, or it can be raised."
        ),
        "tool": (
            "That edit failed and your post is unchanged — the generation service hit a "
            "temporary error. Please try again in a moment."
        ),
        "quota": (
            "The generation service is out of credit right now, so your post was not "
            "changed. This is on our side, not your edit — we have been alerted."
        ),
        "busy": (
            "The generation service is busy right now and your post was not changed. "
            "Please try again in a minute."
        ),
        "unknown": (
            "Something went wrong applying that edit, so your post was not changed. "
            "It has been logged for us to look at."
        ),
        "edit_error": "I couldn't apply that edit, so your post is unchanged: {detail}",
    },
    "nl": {
        "cap": (
            "Het budget voor deze maand is bereikt, dus je post is niet gewijzigd. Er is "
            "niets kapot — het budget gaat volgende maand weer open, of we verhogen het."
        ),
        "tool": (
            "Die bewerking is mislukt en je post is ongewijzigd — de generatieservice gaf "
            "een tijdelijke fout. Probeer het zo nog eens."
        ),
        "quota": (
            "De generatieservice heeft op dit moment geen tegoed, dus je post is niet "
            "gewijzigd. Dat ligt aan ons, niet aan jouw bewerking — we zijn op de hoogte."
        ),
        "busy": (
            "De generatieservice is nu druk en je post is niet gewijzigd. Probeer het "
            "over een minuut nog eens."
        ),
        "unknown": (
            "Er ging iets mis bij het toepassen van die bewerking, dus je post is niet "
            "gewijzigd. We hebben het gelogd en kijken ernaar."
        ),
        "edit_error": "Ik kon die bewerking niet toepassen, je post is ongewijzigd: {detail}",
    },
}


def _http_status(exc: BaseException) -> int | None:
    """HTTP status of a google-genai error (`.code`) or an Interactions one."""
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None

router = APIRouter()


class ChatMessage(BaseModel):
    message: str


@router.get("/chat/{post_id}/history")
async def chat_history(
    post_id: UUID, _: None = Depends(require_auth)
) -> list[dict]:
    async with get_pool().acquire() as conn:
        messages = await get_messages_for_post(conn, post_id)
    return [{"role": m.role, "text": m.content} for m in messages]


@router.post("/chat/{post_id}")
async def chat(
    post_id: UUID,
    body: ChatMessage,
    _: None = Depends(require_auth),
) -> dict:
    pool = get_pool()

    async with pool.acquire() as conn:
        await insert_message(conn, post_id=post_id, role="user", content=body.message)

    # A failed edit must never leave the thread silent: catch every failure,
    # save a model reply explaining it, and return 200 so the UI always shows it.
    version: dict | None = None
    lang = reply_language(body.message)
    msg = _FAILURES[lang]
    try:
        result = await edit_post(
            EditRequest(post_id=post_id, instruction=body.message),
            uploader=R2Uploader(),
        )
        reply = result.summary
        version = {
            "id": str(result.version_id),
            "version_number": result.version_number,
            "asset_url": result.asset_url,
            "caption": result.caption,
            "cost_eur": float(result.cost_eur),
        }
    except EditNeedsClarification as exc:
        # Not a failure: the post is untouched and we ask what they meant.
        reply = exc.question
    except EditError as exc:
        reply = msg["edit_error"].format(detail=exc)
    except SpendCapExceeded as exc:
        # Budget, not breakage: "try again" would be a lie.
        logger.error("chat.edit_spend_cap", post_id=str(post_id), error=str(exc))
        reply = msg["cap"]
    except ToolError as exc:
        logger.warning("chat.edit_tool_error", post_id=str(post_id), error=str(exc))
        reply = msg["tool"]
    except Exception as exc:  # noqa: BLE001 — never leave the thread silent
        status = _http_status(exc)
        if status == 429:
            # Out of Google credit / rate limited. Retrying cannot help, and the
            # old "please try again" sent the client round a loop that never worked.
            logger.error("chat.edit_quota", post_id=str(post_id), error=str(exc)[:300])
            reply = msg["quota"]
        elif status in _RETRYABLE:
            logger.warning("chat.edit_upstream", post_id=str(post_id), status=status)
            reply = msg["busy"]
        else:
            logger.exception("chat.edit_failed", post_id=str(post_id))
            reply = msg["unknown"]

    async with pool.acquire() as conn:
        await insert_message(conn, post_id=post_id, role="model", content=reply)

    return {"role": "model", "text": reply, "version": version}
