"""Edit a post: classify a free-text instruction, dispatch the right tool, version it.

The only place that knows the three edit modes (tweak / regenerate / rewrite) and
which of the asset / caption an edit touches -- one or both (tools/CLAUDE.md). Edits never
mutate — each produces a new `post_versions` row pointing at its parent. It
dispatches paid tools (each @meter-wrapped); `edit_post` itself is the orchestrator.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal, cast, get_args
from uuid import UUID

import asyncpg
import httpx
import structlog
from pydantic import BaseModel, ValidationInfo, field_validator

from app.agents.render import edit_still_text, render_base
from app.db.connection import get_pool
from app.db.models import Week
from app.db.repositories.post_versions import (
    count_versions_for_post,
    get_version,
    insert_version,
)
from app.db.repositories.posts import get_post, get_posts_for_week, set_current_version
from app.db.repositories.weeks import list_weeks
from app.genai_client import MODEL_FLASH, MODEL_PRO, generate_text
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.storage import AssetUploader
from app.tools import ToolError
from app.tools.generate_caption import CaptionRequest, Template, generate_caption
from app.tools.overlay_hook import overlay_hook, overlay_hook_image

logger = structlog.get_logger(__name__)

_SOFT_LIMIT = 5  # PRD §4.4: soft-warn
_HARD_LIMIT = 10  # PRD §4.4: hard-block unless overridden


class EditError(RuntimeError):
    """Raised on an invalid edit (missing post, version limit reached, bad plan)."""

    def __init__(self, message: str, language: str = "en") -> None:
        super().__init__(message)
        self.language = language


class EditNeedsClarification(RuntimeError):
    """The instruction was too vague (or not an edit) — ask before changing anything.

    Guessing at a vague request is how a post gets worse: "dit kan echt beter"
    regenerated the picture, and the question "wat is er verkeerd gegaan?" silently
    rewrote the caption. No version is created and nothing is rendered; the client
    just gets the question back.
    """

    def __init__(self, question: str) -> None:
        super().__init__(question)
        self.question = question


class EditPlan(BaseModel):
    # One OR BOTH. A single target was the biggest source of "it didn't edit
    # properly": the client routinely asks for the media AND the caption in one
    # sentence ("...ook in de caption") and only half of it was ever applied.
    targets: list[Literal["asset", "caption"]]
    # Defaulted: a clarification reply carries no mode, and a plan that fails to
    # validate surfaces to the client as "that edit failed".
    mode: Literal["tweak", "regenerate", "rewrite"] = "tweak"
    new_scene_prompt: str | None = None
    new_hook: str | None = None
    caption_template: Template | None = None
    caption_instruction: str | None = None
    text_scale: float | None = None
    # Set INSTEAD of a plan when the request is too vague or is a question.
    clarify: str | None = None
    # ISO 639-1 code of the request, so the reply speaks the client's language.
    language: str = "en"

    @field_validator("mode", "targets", mode="before")
    @classmethod
    def _tolerate_nulls(cls, value: object, info: ValidationInfo) -> object:
        """Accept an explicit null for these two fields.

        A clarification reply legitimately carries `"mode": null`, and the model
        sometimes nulls `targets` too. Pydantic validates a PROVIDED null against
        the Literal, so without this the whole plan fails to parse and the client
        sees "that edit failed" instead of the question.
        """
        if value is not None:
            return value
        return "tweak" if info.field_name == "mode" else []


# Reply phrasing per language. The client writes Dutch, so answering in English made
# the thread feel like a machine; `EditPlan.language` carries what they used.
# Anything we have no phrasing for falls back to English rather than guessing.
_PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "photo": "photo", "video": "video",
        "new_media": "made a new {media}",
        "set_hook": 'set the on-screen text to "{hook}"',
        "resized_smaller": "made the on-screen text smaller",
        "resized_bigger": "made the on-screen text bigger",
        "caption_match": "rewrote the caption to match",
        "caption": "rewrote the caption",
        "kept_media_and_hook": "the {media} and its on-screen text are unchanged",
        "kept_hook": "the on-screen text is unchanged",
        "kept_media": "the {media} itself is untouched",
        "kept_caption": "the caption is unchanged",
        "done": "Done. I {done}.",
        "and": " and ",
        "version": " This is version {n}.",
        "nothing": (
            "I could not change anything on this post (still version {n}). Tell me "
            "specifically what to change: the caption, the text in the image, or "
            "the {media} itself."
        ),
    },
    "nl": {
        "photo": "foto", "video": "video",
        "new_media": "een nieuwe {media} gemaakt",
        "set_hook": 'de tekst in beeld gewijzigd naar "{hook}"',
        "resized_smaller": "de tekst in beeld kleiner gemaakt",
        "resized_bigger": "de tekst in beeld groter gemaakt",
        "caption_match": "de caption daarop aangepast",
        "caption": "de caption herschreven",
        "kept_media_and_hook": "de {media} en de tekst in beeld zijn ongewijzigd",
        "kept_hook": "de tekst in beeld is ongewijzigd",
        "kept_media": "de {media} zelf is ongewijzigd",
        "kept_caption": "de caption is ongewijzigd",
        "done": "Klaar. Ik heb {done}.",
        "and": " en ",
        "version": " Dit is versie {n}.",
        "nothing": (
            "Ik heb niets kunnen wijzigen aan deze post (nog steeds versie {n}). Zeg "
            "precies wat ik moet aanpassen: de caption, de tekst in beeld, of de "
            "{media} zelf."
        ),
    },
}


def summarise_edit(
    *,
    post_type: str,
    media_rerendered: bool,
    hook_before: str | None,
    hook_after: str | None,
    caption_changed: bool,
    caption_followed_asset: bool,
    version_number: int,
    text_resized: float | None = None,  # <1 smaller, >1 bigger
    language: str = "en",
) -> str:
    """Say what actually changed, and what did not, in the client's own language.

    The old reply ("tweak applied to the asset") left the client guessing whether
    both halves of their request landed and whether the picture had been replaced.
    Built from facts rather than a model call: free, instant and always true.
    """
    p = _PHRASES.get(language.lower()[:2], _PHRASES["en"])
    media = p["video"] if post_type == "video" else p["photo"]
    did: list[str] = []
    kept: list[str] = []

    hook_changed = bool(hook_after) and hook_after != hook_before
    # A size change rewrites the asset without touching the wording, so it has to
    # be reported on its own or the reply claims nothing happened.
    resized = text_resized is not None and text_resized != 1.0
    if media_rerendered:
        did.append(p["new_media"].format(media=media))
    if hook_changed:
        first_line = (hook_after or "").splitlines()[0].strip() if hook_after else ""
        did.append(p["set_hook"].format(hook=first_line))
    if resized:
        did.append(p["resized_smaller"] if (text_resized or 1) < 1 else p["resized_bigger"])

    # Exactly one reassurance about the media, or they contradict each other.
    text_touched = hook_changed or resized
    if not media_rerendered and not text_touched:
        kept.append(p["kept_media_and_hook"].format(media=media))
    elif media_rerendered and not text_touched:
        kept.append(p["kept_hook"])
    elif not media_rerendered:
        kept.append(p["kept_media"].format(media=media))

    if caption_changed:
        did.append(p["caption_match"] if caption_followed_asset else p["caption"])
    else:
        kept.append(p["kept_caption"])

    if not did:  # nothing to report would be the vaguest answer of all
        return p["nothing"].format(n=version_number, media=media)
    done = did[0] if len(did) == 1 else ", ".join(did[:-1]) + p["and"] + did[-1]
    reply = p["done"].format(done=done)
    if kept:
        reply += " " + (kept[0] if len(kept) == 1 else "; ".join(kept)).capitalize() + "."
    return reply + p["version"].format(n=version_number)


class EditRequest(BaseModel):
    post_id: UUID
    instruction: str
    override_limit: bool = False


class EditResult(BaseModel):
    version_id: UUID
    summary: str  # what changed, in plain words, for the chat thread
    version_number: int
    target: str
    mode: str
    asset_url: str | None
    caption: str | None
    cost_eur: Decimal


_CLASSIFY = """You classify a free-text edit request for a Blue Fit social post and
return STRICT JSON only — no prose, no code fences.

Decide:
- "targets": a LIST naming everything the request touches. Include "asset" if the
  change is about the image/video itself OR the ON-SCREEN
  text overlaid on it — the "hook" burned into the media (e.g. "the text in the
  video", "de tekst in de video", "de tekst op de foto", "the words on screen",
  "change the on-screen text"). Use "caption" ONLY for the written caption /
  description shown BENEATH the post. Rule of thumb: text that is IN / ON the
  video or image is the ASSET hook, not the caption.
  **If the request mentions BOTH, return BOTH** — e.g. "de tekst in de video moet
  beter en ook de caption", "maak een nieuwe post en een nieuwe caption",
  "verwijs meer naar de blue zones, ook in de caption" -> ["asset","caption"].
  Never silently drop half of what was asked. When in doubt, include "asset".
- "language": the ISO 639-1 code of the language the REQUEST is written in
  ("nl" for Dutch, "en" for English, ...). The reply is written in that language.
- "clarify": use this INSTEAD of guessing. If the request is too vague to act on
  ("dit kan echt beter", "maak het mooier", "niet goed"), or is a QUESTION rather
  than an instruction ("wat is er verkeerd gegaan?", "waarom is dit zo?"), return
  "targets": [] and set "clarify" to a SHORT question in the SAME LANGUAGE as the
  request, naming the concrete options so they can just pick one — the caption, the
  text on the image/video, the image/video itself, or the colours/style. Example:
  "Wat zal ik precies aanpassen: de caption, de tekst in beeld, of de foto zelf?".
  Also use "clarify" when the message is NOT a change request at all: praise or an
  acknowledgement ("Deze is nu erg mooi en heb ik gebruikt!"), a bare command with no
  object ("doe het", "fix het"), or a complaint about a previous edit ("er verandert
  niks in de post"). Acknowledge briefly and ask what to change — never edit the post
  on the strength of a compliment.
  A request that names something concrete is NOT vague — act on it normally.
- "mode": "tweak" (small change to the same concept), "regenerate" (same concept,
  a fresh take), or "rewrite" (a meaningfully different concept).
- For an asset tweak/rewrite that should change the video/image itself, set
  "new_scene_prompt" to the full updated scene description: the Blue Fit mascot
  stays the subject (refer to it only as "the Blue Fit mascot" — never describe
  its appearance), keep the post's beat (the one scroll-stopping moment) unless the
  user changes it; action/setting/mood only, no style words; any real people
  faceless. To keep the same media and change ONLY the on-screen text, leave
  "new_scene_prompt" null. For "regenerate" leave it null.
- If the user wants DIFFERENT on-screen HOOK words (not merely resizing), set
  "new_hook" to the new short hook text — a few punchy words, in the SAME language
  as the post. Use target "asset". Leave "new_scene_prompt" null to keep the exact
  video/image and only swap the on-screen words (mode "tweak"); ALSO set
  "new_scene_prompt" if they want a new video/image too (it is regenerated with the
  new hook). The on-screen text is two lines: the hook line, then a caption
  call-to-action line ending in 👇 (e.g. "Lees de caption 👇"). When the user
  changes only the hook words, KEEP the existing call-to-action line as the last line
  (separated by a newline) unless they explicitly remove it. Otherwise "new_hook" is
  null.
- If the request is only to resize the on-image HOOK TEXT (e.g. "make the text
  smaller/bigger", "kleiner/groter maken"), set "text_scale" to a multiplier
  RELATIVE to the current text: 0.8 = a bit smaller, 0.65 = much smaller, 1.25 =
  bigger. Use target "asset", mode "tweak", and leave "new_scene_prompt" null so
  the scene is kept. Otherwise "text_scale" is null.
- When "caption" is among the targets, set "caption_instruction" to a concise
  directive capturing the caption part of the request; set
  "caption_template" only if the engagement style should change
  (question|hottake|observation), else null.
- If a "## Reference posts" section is present, the user is asking to emulate that
  past week's style (e.g. "make this like week two"). Base "new_scene_prompt" (asset)
  or "caption_instruction" (caption) on the referenced posts' setting/mood/caption
  style, adapted to THIS post's pillar — do not copy their subject verbatim, and
  the Blue Fit mascot remains the subject even if the referenced posts (older,
  pre-mascot weeks) show people or scenery instead.

Return exactly the keys:
{"targets","mode","new_scene_prompt","new_hook","caption_template","caption_instruction","text_scale","clarify","language"}"""


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
            f"| beat: {b.get('beat')} | hook: {b.get('hook')} | caption: {v.caption}"
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
    response = await generate_text(MODEL_FLASH, req.text, fallback_model=MODEL_PRO)
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
    post_type: str,
    scene: str,
    motion: str | None,
    hook: str | None,
    post_id: UUID,
    scale: float = 1.0,
) -> tuple[bytes, bytes, str, str, Decimal]:
    """Re-render an edited asset (metered, mascot in frame).

    Returns (final, base, ext, content_type, cost). Images draw the hook in-picture
    (final == base). Videos are rendered clean and get the hook overlaid at
    `scale`; the clean clip is the base kept for later text edits. For video the
    cost includes the mascot still Omni animates from.
    """
    asset = await render_base(
        post_type, scene, motion, post_id=post_id, trigger="edit",
        hook=hook if post_type == "image" else None,
    )
    base = asset.data
    if post_type == "image" or not hook:
        data = base
    else:
        data = await overlay_hook(base, hook, scale=scale)
    return data, base, asset.ext, asset.content_type, asset.cost_eur


def _size_hint(scale: float | None) -> str | None:
    """Turn a relative text-size edit into words the image model can act on."""
    if scale is None or scale == 1.0:
        return None
    pct = abs(round((1 - scale) * 100))
    direction = "smaller" if scale < 1 else "larger"
    return (
        f"Also make all the on-image text about {pct}% {direction} than it is now, "
        "keeping it at the top of the picture."
    )


def _ext_ctype(url: str) -> tuple[str, str]:
    """Infer (ext, content_type) from a stored asset URL's suffix."""
    if url.endswith((".jpg", ".jpeg")):
        return ".jpg", "image/jpeg"
    if url.endswith(".png"):
        return ".png", "image/png"
    return ".mp4", "video/mp4"


async def _fetch_bytes(url: str) -> bytes:
    """Download a stored asset (the public R2 URL) for in-place re-overlay."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def _reoverlay_from_base(
    base_url: str, post_type: str, hook: str | None, scale: float
) -> tuple[bytes, str, str]:
    """Re-apply the hook overlay to the stored base at a new text size.

    Keeps the exact image — no regeneration, no generation cost. Returns
    (composited_bytes, ext, content_type).
    """
    raw = await _fetch_bytes(base_url)
    ext, ctype = _ext_ctype(base_url)
    if not hook:
        return raw, ext, ctype
    if post_type == "image":
        return await overlay_hook_image(raw, hook, ext, scale=scale), ext, ctype
    return await overlay_hook(raw, hook, scale=scale), ext, ctype


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
        f"scene_prompt: {blob.get('scene_prompt')}\nbeat: {blob.get('beat')}\n"
        f"caption: {current.caption}"
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
    media_rerendered = False
    caption_followed_asset = False  # caption changed to track the asset, not by request
    wants_asset = "asset" in plan.targets
    wants_caption = "caption" in plan.targets
    # Ask rather than guess: a vague request costs only the classify call above.
    if plan.clarify or not plan.targets:
        raise EditNeedsClarification(
            plan.clarify
            or "Wat zal ik precies aanpassen: de caption, de tekst in beeld, "
            "of de foto/video zelf?"
        )

    # Asset first, so a caption written afterwards reflects the NEW scene/hook.
    if wants_asset:
        scene = plan.new_scene_prompt or blob.get("scene_prompt")
        if not scene:
            raise EditError("no scene_prompt available to edit this asset.")
        # Text size is relative to the current asset's; compound + clamp so repeated
        # "smaller" keeps shrinking within sane bounds.
        text_scale = float(blob.get("text_scale") or 1.0)
        if plan.text_scale:
            text_scale = min(2.0, max(0.4, text_scale * plan.text_scale))

        # New on-screen words if requested, else keep the existing hook. (Empty
        # string from the classifier means "no new hook", not "clear the hook".)
        hook = plan.new_hook if plan.new_hook else blob.get("hook")

        base_url: str | None = blob.get("base_asset_url")
        v_next = current.version_number + 1
        # A text-only edit keeps the exact media: no new scene, not a "regenerate"
        # (which wants a fresh take), and only the hook words and/or size change.
        # Treat an empty-string scene as "no new scene" so a text edit stays cheap.
        text_only = (
            not plan.new_scene_prompt
            and plan.mode != "regenerate"
            and (plan.text_scale is not None or bool(plan.new_hook))
        )
        media_rerendered = not (text_only and base_url)
        if post.type == "image":
            # Images carry their typography in-picture (decisions/010): a text edit
            # re-renders ONLY the text on the stored final (Pro Image edit mode);
            # anything else is a fresh render with the new hook drawn in.
            media_rerendered = not (text_only and base_url and hook)
            if text_only and base_url and hook:
                edited = await edit_still_text(
                    await _fetch_bytes(base_url),
                    _ext_ctype(base_url)[1],
                    hook,
                    post_id=req.post_id,
                    trigger="edit",
                    size_hint=_size_hint(plan.text_scale),
                )
                data, ext, ctype = edited.data, edited.ext, edited.content_type
                asset_cost = edited.cost_eur
            else:
                data, _, ext, ctype, asset_cost = await _render_asset(
                    post.type, scene, None, hook, req.post_id
                )
            cost += asset_cost
            new_asset_url = await uploader.upload(
                data=data,
                key=f"edits/{req.post_id}/v{v_next}{ext}",
                content_type=ctype,
            )
            base_url = new_asset_url  # for images the final IS the base
        else:
            if text_only and base_url:
                # Video: re-overlay the stored clean clip — no regeneration cost.
                data, ext, ctype = await _reoverlay_from_base(
                    base_url, post.type, hook, text_scale
                )
            else:
                # Regenerate the clip and store its clean base for future text edits.
                data, base, ext, ctype, asset_cost = await _render_asset(
                    post.type, scene, blob.get("motion"), hook, req.post_id,
                    scale=text_scale,
                )
                cost += asset_cost
                base_url = await uploader.upload(
                    data=base,
                    key=f"edits/{req.post_id}/v{v_next}-base{ext}",
                    content_type=ctype,
                )
            new_asset_url = await uploader.upload(
                data=data,
                key=f"edits/{req.post_id}/v{v_next}{ext}",
                content_type=ctype,
            )
        # Keep the caption bound to the post. The hook is the bait the caption pays
        # off, and the caption describes the scene — so a new hook or a new scene
        # means the old caption now tells a different story. Re-sync it (cheap Flash)
        # BEFORE the blob is overwritten, so "changed" compares against the original.
        hook_changed = bool(plan.new_hook) and hook != blob.get("hook")
        scene_changed = bool(plan.new_scene_prompt) and scene != blob.get("scene_prompt")
        # Skipped when the client also asked for a caption change: their own
        # instruction is applied below instead of this generic re-sync.
        if (hook_changed or scene_changed) and not wants_caption:
            raw_t = blob.get("engagement_template") or "observation"
            sync_template = cast(
                Template, raw_t if raw_t in get_args(Template) else "observation"
            )
            sync = await generate_caption(
                CaptionRequest(
                    template=sync_template,
                    brief=(
                        f"type: {post.type} | pillar: {post.pillar} | theme: {blob.get('theme')} | "
                        f"value: {blob.get('value')} | scene: {scene}"
                    ),
                    instruction=(
                        f'The on-screen hook is now: "{hook}". Rewrite the caption so it '
                        "PAYS OFF this hook — deliver the answer or insight it teases — "
                        f"and matches the scene: {scene}. Keep the same pillar and "
                        "Power-9 value."
                    ),
                    trigger="edit",
                    post_id=req.post_id,
                )
            )
            new_caption = sync.caption
            cost += sync.cost_eur
            caption_followed_asset = True

        blob = {
            **blob,
            "scene_prompt": scene,
            "hook": hook,
            "text_scale": text_scale,
            "base_asset_url": base_url,
        }


    if wants_caption:
        raw_template = plan.caption_template or blob.get("engagement_template") or "observation"
        template = cast(
            Template, raw_template if raw_template in get_args(Template) else "observation"
        )
        brief = (
            f"type: {post.type} | pillar: {post.pillar} | theme: {blob.get('theme')} | "
            f"value: {blob.get('value')} | scene: {blob.get('scene_prompt')} | "
            f"on-screen hook: {blob.get('hook')}"
        )
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
    new_blob = {
        **blob,
        "caption": new_caption,
        "edit_instruction": req.instruction,
        "edit_mode": plan.mode,
        "edit_target": list(plan.targets),
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
        "edit.done", post_id=str(req.post_id), targets=plan.targets,
        mode=plan.mode, version=version.version_number,
    )
    summary = summarise_edit(
        post_type=post.type,
        media_rerendered=wants_asset and media_rerendered,
        hook_before=(current.reasoning_blob or {}).get("hook"),
        hook_after=blob.get("hook"),
        caption_changed=(new_caption or "") != (current.caption or ""),
        caption_followed_asset=caption_followed_asset,
        version_number=version.version_number,
        text_resized=plan.text_scale if wants_asset else None,
        language=plan.language,
    )
    return EditResult(
        version_id=version.id,
        summary=summary,
        version_number=version.version_number,
        target=" and ".join(plan.targets),
        mode=plan.mode,
        asset_url=new_asset_url,
        caption=new_caption,
        cost_eur=cost,
    )
