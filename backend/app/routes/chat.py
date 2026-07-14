"""Chat routes: POST /chat/{post_id}, GET /chat/{post_id}/history."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import require_auth
from app.db.connection import get_pool
from app.db.repositories.messages import get_messages_for_post, insert_message
from app.storage.r2 import R2Uploader
from app.tools import ToolError
from app.tools.edit_post import EditError, EditRequest, edit_post

logger = structlog.get_logger(__name__)

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
    except EditError as exc:
        reply = f"I couldn't apply that edit: {exc}"
    except ToolError as exc:
        logger.warning("chat.edit_tool_error", post_id=str(post_id), error=str(exc))
        reply = (
            "That edit failed — the generation service hit a temporary error. "
            "Please try again in a moment."
        )
    except Exception:  # noqa: BLE001 — never leave the thread silent on an unexpected error
        logger.exception("chat.edit_failed", post_id=str(post_id))
        reply = "Something went wrong applying that edit. Please try again."

    async with pool.acquire() as conn:
        await insert_message(conn, post_id=post_id, role="model", content=reply)

    return {"role": "model", "text": reply, "version": version}
