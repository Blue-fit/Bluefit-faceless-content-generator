"""GET /posts/{post_id}/explain — strategic-transparency "why this post" endpoint.

Resolves the post's current version and renders its structured reasoning_blob into
prose via the explain tool (Flash, @meter). This is the REAL per-post reasoning
(brand chunks cited, theme/value, rule applied) — not boilerplate.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth
from app.db.connection import get_pool
from app.db.repositories.posts import get_post
from app.tools import ToolError
from app.tools.explain import ExplainRequest, explain

router = APIRouter()


@router.get("/posts/{post_id}/explain")
async def explain_post(post_id: UUID, _: None = Depends(require_auth)) -> dict[str, str]:
    async with get_pool().acquire() as conn:
        post = await get_post(conn, post_id)
    if post is None or post.current_version_id is None:
        raise HTTPException(status_code=404, detail="post or current version not found")
    try:
        result = await explain(
            ExplainRequest(
                post_version_id=post.current_version_id,
                trigger="explain",
                post_id=post_id,
            )
        )
    except ToolError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"explanation": result.explanation}
