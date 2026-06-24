"""Edit a post: classify a free-text instruction, dispatch the right tool, version it.

The only place that knows the three edit modes (tweak / regenerate / rewrite) and
whether an edit targets the asset or the caption (tools/CLAUDE.md). Edits never
mutate — each produces a new `post_versions` row pointing at its parent. It
dispatches paid tools (each @meter-wrapped); `edit_post` itself is the orchestrator.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal, cast, get_args
from uuid import UUID

import asyncpg
import structlog
from pydantic import BaseModel

from app.agents.prompt_builder import build_image_prompt, build_video_prompt
from app.db.connection import get_pool
from app.db.models import Week
from app.db.repositories.post_versions import (
    count_versions_for_post,
    get_version,
    insert_version,
)
from app.db.repositories.posts import get_post, get_posts_for_week, set_current_version
from app.db.repositories.weeks import list_weeks
from app.genai_client import MODEL_FLASH, generate_text
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.storage import AssetUploader
from app.tools import ToolError
from app.tools.generate_caption import CaptionRequest, Template, generate_caption
from app.tools.generate_image import ImageRequest, generate_image
from app.tools.generate_video import VideoRequest, generate_video
from app.tools.overlay_hook import overlay_hook, overlay_hook_image

logger = structlog.get_logger(__name__)

_SOFT_LIMIT = 5  # PRD §4.4: soft-warn
_HARD_LIMIT = 10  # PRD §4.4: hard-block unless overridden


class EditError(RuntimeError):
    """Raised on an invalid edit (missing post, version limit reached, bad plan)."""


class EditPlan(BaseModel):
    target: Literal["asset", "caption"]
    mode: Literal["tweak", "regenerate", "rewrite"]
    new_scene_prompt: str | None = None
    caption_template: Template | None = None
    caption_instruction: str | None = None


class EditRequest(BaseModel):
    post_id: UUID
    instruction: str
    override_limit: bool = False


class EditResult(BaseModel):
    version_id: UUID
    version_number: int
    target: str
    mode: str
    asset_url: str | None
    caption: str | None
    cost_eur: Decimal


_CLASSIFY = """You classify a free-text edit request for a Blue Fit social post and
return STRICT JSON only — no prose, no code fences.

Decide:
- "target": "asset" if the change is about the image/video itself; "caption" if it
  is about the written caption.
- "mode": "tweak" (small change to the same concept), "regenerate" (same concept,
  a fresh take), or "rewrite" (a meaningfully different concept).
- For an asset tweak/rewrite, set "new_scene_prompt" to the full updated scene
  description (faceless; subject/action/setting/mood only, no style words). For
  "regenerate" leave it null.
- For a caption edit, set "caption_instruction" to a concise directive; set
  "caption_template" only if the engagement style should change
  (question|hottake|observation), else null.
- If a "## Reference posts" section is present, the user is asking to emulate that
  past week's style (e.g. "make this like week two"). Base "new_scene_prompt" (asset)
  or "caption_instruction" (caption) on the referenced posts' scene/caption style,
  adapted to THIS post's pillar — do not copy their subject verbatim.

Return exactly the keys:
{"target","mode","new_scene_prompt","caption_template","caption_instruction"}"""


# ---- "make this like week N" reference resolution ---------------------------

_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_WEEK_ORDINAL = re.compile(r"\bweek\s+(\d+|" + "|".join(_NUM_WORDS) + r")\b", re.IGNORECASE)
_WEEK_RELATIVE = re.compile(r"\b(?:last|previous|prior)\s+week\b|\bweek\s+before\b", re.IGNORECASE)


def _referenced_week_id(
    instruction: str, weeks: list[Week], current_week_id: UUID
) -> UUID | None:
    """Resolve 'week two' / 'last week' to a past week's id (weeks oldest-first)."""
    if _WEEK_RELATIVE.search(instruction):
        cur = next((w for w in weeks if w.id == current_week_id), None)
        earlier = [w for w in weeks if cur is not None and w.week_start < cur.week_start]
        return earlier[-1].id if earlier else None
    m = _WEEK_ORDINAL.search(instruction)
    if m:
        tok = m.group(1).lower()
        n = int(tok) if tok.isdigit() else _NUM_WORDS[tok]
        if 1 <= n <= len(weeks):
            return weeks[n - 1].id
    return None


async def _reference_block(
    conn: asyncpg.Connection, current_week_id: UUID, instruction: str
) -> str | None:
    """If the instruction names a past week, return that week's posts' style for
    the classifier to emulate. None if no reference (the common case)."""
    weeks = await list_weeks(conn)
    target_id = _referenced_week_id(instruction, weeks, current_week_id)
    if target_id is None or target_id == current_week_id:
        return None
    lines: list[str] = []
    for p in await get_posts_for_week(conn, target_id):
        if p.current_version_id is None:
            continue
        v = await get_version(conn, p.current_version_id)
        if v is None:
            continue
        b = v.reasoning_blob or {}
        lines.append(
            f"- pillar: {b.get('pillar') or p.pillar} | scene: {b.get('scene_prompt')} "
            f"| hook: {b.get('hook')} | caption: {v.caption}"
        )
    if not lines:
        return None
    target = next((w for w in weeks if w.id == target_id), None)
    label = f"week of {target.week_start}" if target else "referenced week"
    return f"## Reference posts ({label})\n" + "\n".join(lines)


# ---- metered instruction classifier ----------------------------------------


class _ClassifyRequest(MeterRequest):
    text: str


class _ClassifyResult(MeteredResult):
    plan: EditPlan


@meter("edit")
async def _classify(req: _ClassifyRequest) -> _ClassifyResult:
    response = await generate_text(MODEL_FLASH, req.text)
    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        plan = EditPlan.model_validate_json(raw)
    except ValueError as exc:
        raise ToolError(f"edit classify: could not parse plan JSON: {exc}") from exc
    usage = response.usage_metadata
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    return _ClassifyResult(
        model=MODEL_FLASH,
        cost_eur=pricing.text_cost(MODEL_FLASH, in_tok, out_tok),
        plan=plan,
    )


async def _render_asset(
    post_type: str, scene: str, motion: str | None, hook: str | None, post_id: UUID
) -> tuple[bytes, str, str, Decimal]:
    """Re-render an edited asset (metered) and burn in its hook. Returns bytes+meta."""
    if post_type == "image":
        img = await generate_image(
            ImageRequest(
                prompt=build_image_prompt(scene),
                aspect_ratio="9:16",
                trigger="edit",
                post_id=post_id,
            )
        )
        ext = ".jpg" if "jpeg" in img.mime_type else ".png"
        data = (
            await overlay_hook_image(img.image_bytes, hook, ext)
            if hook
            else img.image_bytes
        )
        return data, ext, img.mime_type, img.cost_eur

    vid = await generate_video(
        VideoRequest(
            prompt=build_video_prompt(scene, motion),
            aspect_ratio="9:16",
            duration_seconds=8,
            trigger="edit",
            post_id=post_id,
        )
    )
    data = await overlay_hook(vid.video_bytes, hook) if hook else vid.video_bytes
    return data, ".mp4", vid.mime_type or "video/mp4", vid.cost_eur


async def edit_post(req: EditRequest, *, uploader: AssetUploader) -> EditResult:
    """Classify the instruction, dispatch the right tool, and write a new version."""
    pool = get_pool()
    async with pool.acquire() as conn:
        post = await get_post(conn, req.post_id)
        if post is None:
            raise EditError(f"post {req.post_id} not found.")
        if post.current_version_id is None:
            raise EditError(f"post {req.post_id} has no current version.")
        current = await get_version(conn, post.current_version_id)
        count = await count_versions_for_post(conn, req.post_id)
        reference = await _reference_block(conn, post.week_id, req.instruction)
    if current is None:
        raise EditError("current version is missing.")

    if count >= _HARD_LIMIT and not req.override_limit:
        raise EditError(
            f"post is at v{count}: hard limit {_HARD_LIMIT} reached — set override_limit."
        )
    if count >= _SOFT_LIMIT:
        logger.warning("edit.soft_limit", post_id=str(req.post_id), versions=count)

    blob = current.reasoning_blob or {}
    summary = (
        f"type: {post.type}\npillar: {post.pillar}\n"
        f"scene_prompt: {blob.get('scene_prompt')}\ncaption: {current.caption}"
    )
    ref_section = f"\n\n{reference}" if reference else ""
    classify = await _classify(
        _ClassifyRequest(
            text=(
                f"{_CLASSIFY}\n\n## Current post\n{summary}{ref_section}"
                f"\n\n## Instruction\n{req.instruction}"
            ),
            trigger="edit",
            post_id=req.post_id,
        )
    )
    plan = classify.plan
    cost = classify.cost_eur

    new_caption = current.caption
    new_asset_url = current.asset_url

    if plan.target == "caption":
        raw_template = plan.caption_template or blob.get("engagement_template") or "observation"
        template = cast(
            Template, raw_template if raw_template in get_args(Template) else "observation"
        )
        brief = f"{post.pillar} | {blob.get('theme')} | {blob.get('value')} | {blob.get('scene_prompt')}"
        caption = await generate_caption(
            CaptionRequest(
                template=template,
                brief=brief,
                instruction=plan.caption_instruction or req.instruction,
                trigger="edit",
                post_id=req.post_id,
            )
        )
        new_caption = caption.caption
        cost += caption.cost_eur
    else:
        scene = plan.new_scene_prompt or blob.get("scene_prompt")
        if not scene:
            raise EditError("no scene_prompt available to edit this asset.")
        data, ext, ctype, asset_cost = await _render_asset(
            post.type, scene, blob.get("motion"), blob.get("hook"), req.post_id
        )
        cost += asset_cost
        new_asset_url = await uploader.upload(
            data=data,
            key=f"edits/{req.post_id}/v{current.version_number + 1}{ext}",
            content_type=ctype,
        )
        blob = {**blob, "scene_prompt": scene}

    new_blob = {
        **blob,
        "caption": new_caption,
        "edit_instruction": req.instruction,
        "edit_mode": plan.mode,
        "edit_target": plan.target,
        "parent_version": str(current.id),
    }
    async with pool.acquire() as conn, conn.transaction():
        version = await insert_version(
            conn,
            post_id=req.post_id,
            parent_version_id=current.id,
            version_number=current.version_number + 1,
            asset_url=new_asset_url,
            caption=new_caption,
            edit_instruction=req.instruction,
            reasoning_blob=new_blob,
            reasoning_embedding=current.reasoning_embedding,  # carried over (v1 follow-up: re-embed)
        )
        await set_current_version(conn, req.post_id, version.id)

    logger.info(
        "edit.done", post_id=str(req.post_id), target=plan.target,
        mode=plan.mode, version=version.version_number,
    )
    return EditResult(
        version_id=version.id,
        version_number=version.version_number,
        target=plan.target,
        mode=plan.mode,
        asset_url=new_asset_url,
        caption=new_caption,
        cost_eur=cost,
    )
