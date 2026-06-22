"""Chat routes: POST /chat/{post_id}, GET /chat/{post_id}/history."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import require_auth
from app.db.connection import get_pool
from app.db.repositories.messages import get_messages_for_post, insert_message
from app.storage.r2 import R2Uploader
from app.tools.edit_post import EditError, EditRequest, edit_post

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

    try:
        result = await edit_post(
            EditRequest(post_id=post_id, instruction=body.message),
            uploader=R2Uploader(),
        )
    except EditError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    reply = (
        f"Done — {result.mode} applied to the {result.target}. "
        f"This is version {result.version_number}."
    )
    async with pool.acquire() as conn:
        await insert_message(conn, post_id=post_id, role="model", content=reply)

    return {
        "role": "model",
        "text": reply,
        "version": {
            "id": str(result.version_id),
            "version_number": result.version_number,
            "asset_url": result.asset_url,
            "caption": result.caption,
            "cost_eur": float(result.cost_eur),
        },
    }
