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
    try:
        result = await edit_post(
            EditRequest(post_id=post_id, instruction=body.message),
            uploader=R2Uploader(),
        )
        reply = (
            f"Done — {result.mode} applied to the {result.target}. "
            f"This is version {result.version_number}."
        )
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
        reply = f"I couldn't apply that edit, so your post is unchanged: {exc}"
    except SpendCapExceeded as exc:
        # Budget, not breakage: "try again" would be a lie.
        logger.error("chat.edit_spend_cap", post_id=str(post_id), error=str(exc))
        reply = (
            "This month's generation budget has been reached, so your post was not "
            "changed. Nothing is broken — the cap resets next month, or it can be "
            "raised."
        )
    except ToolError as exc:
        logger.warning("chat.edit_tool_error", post_id=str(post_id), error=str(exc))
        reply = (
            "That edit failed and your post is unchanged — the generation service "
            "hit a temporary error. Please try again in a moment."
        )
    except Exception as exc:  # noqa: BLE001 — never leave the thread silent
        status = _http_status(exc)
        if status == 429:
            # Out of Google credit / rate limited. Retrying cannot help, and the
            # old "please try again" sent the client round a loop that never worked.
            logger.error("chat.edit_quota", post_id=str(post_id), error=str(exc)[:300])
            reply = (
                "The generation service is out of credit right now, so your post was "
                "not changed. This is on our side, not your edit — we have been "
                "alerted and will top it up."
            )
        elif status in _RETRYABLE:
            logger.warning("chat.edit_upstream", post_id=str(post_id), status=status)
            reply = (
                "The generation service is busy right now and your post was not "
                "changed. Please try again in a minute."
            )
        else:
            logger.exception("chat.edit_failed", post_id=str(post_id))
            reply = (
                "Something went wrong applying that edit, so your post was not "
                "changed. It has been logged for us to look at."
            )

    async with pool.acquire() as conn:
        await insert_message(conn, post_id=post_id, role="model", content=reply)

    return {"role": "model", "text": reply, "version": version}
