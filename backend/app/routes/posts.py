"""GET /weeks — returns all weeks + posts shaped for the frontend."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.db.connection import get_pool

router = APIRouter()


def _week_label(week_start) -> str:
    return f"Week of {week_start.strftime('%B')} {week_start.day}"


def _date_range(week_start) -> str:
    week_end = week_start + timedelta(days=6)
    if week_start.month == week_end.month:
        return f"{week_start.day} – {week_end.day} {week_end.strftime('%b %Y')}"
    return f"{week_start.day} {week_start.strftime('%b')} – {week_end.day} {week_end.strftime('%b %Y')}"


def _month_id(week_start) -> str:
    return week_start.strftime("%Y-%m")


def _month_label(week_start) -> str:
    return week_start.strftime("%B %Y")


@router.get("/weeks")
async def list_weeks(_: None = Depends(require_auth)) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        week_rows = await conn.fetch(
            "SELECT id, week_start, status FROM weeks ORDER BY week_start DESC"
        )
        if not week_rows:
            return {"months": [], "weeks": []}

        week_ids = [r["id"] for r in week_rows]

        post_rows = await conn.fetch(
            """
            SELECT
                p.id, p.week_id, p.type, p.pillar,
                pv.caption, pv.version_number AS current_version_number,
                pv.asset_url,
                (SELECT COUNT(*) FROM post_versions pv2
                 WHERE pv2.post_id = p.id) AS total_versions
            FROM posts p
            LEFT JOIN post_versions pv ON p.current_version_id = pv.id
            WHERE p.week_id = ANY($1)
            ORDER BY p.week_id, p.created_at
            """,
            week_ids,
        )

        post_ids: list[UUID] = [r["id"] for r in post_rows]
        msg_rows = await conn.fetch(
            "SELECT post_id, role, content FROM messages WHERE post_id = ANY($1) ORDER BY created_at",
            post_ids,
        ) if post_ids else []

    # group messages by post_id
    messages_by_post: dict[UUID, list[dict]] = {}
    for m in msg_rows:
        messages_by_post.setdefault(m["post_id"], []).append(
            {"role": m["role"], "text": m["content"]}
        )

    # group posts by week_id
    posts_by_week: dict[UUID, list[dict]] = {}
    for p in post_rows:
        posts_by_week.setdefault(p["week_id"], []).append(
            {
                "id": str(p["id"]),
                "type": p["type"],
                "pillar": p["pillar"],
                "caption": p["caption"] or "",
                "asset_url": p["asset_url"],
                "currentVersion": p["current_version_number"] or 1,
                "totalVersions": p["total_versions"],
                "messages": messages_by_post.get(p["id"], []),
            }
        )

    # build weeks + collect months
    months_seen: dict[str, str] = {}
    weeks = []
    for w in week_rows:
        mid = _month_id(w["week_start"])
        months_seen[mid] = _month_label(w["week_start"])
        weeks.append(
            {
                "id": str(w["id"]),
                "monthId": mid,
                "label": _week_label(w["week_start"]),
                "dateRange": _date_range(w["week_start"]),
                "status": w["status"],
                "posts": posts_by_week.get(w["id"], []),
            }
        )

    months = [{"id": mid, "label": label} for mid, label in months_seen.items()]
    return {"months": months, "weeks": weeks}
