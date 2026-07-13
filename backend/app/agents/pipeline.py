"""Production weekly pipeline: researcher -> retrieve -> generator -> render -> persist.

The single entry point the scheduler/trigger calls. Orchestrates the RAG-grounded
weekly run and writes versioned posts to the DB. Storage (R2) is Jacob's domain, so
the pipeline takes an injected `AssetUploader`; it never implements R2 itself.

`run_all.py` stays as the offline (no-DB/no-R2) smoke test; this is the DB-backed,
metered production twin.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import structlog
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from app.agents.generator import build_generator
from app.agents.prompt_builder import build_image_prompt, build_video_prompt
from app.agents.researcher import build_researcher
from app.agents.schemas import GeneratorOutput, PostSpec
from app.db.connection import get_pool
from app.db.repositories.brand_chunks import count_chunks
from app.db.repositories.post_versions import insert_version
from app.db.repositories.posts import insert_post, set_current_version
from app.db.repositories.rules import get_active_rules
from app.db.repositories.weeks import (
    get_week_by_start,
    insert_week,
    set_week_brief,
    set_week_status,
)
from app.genai_client import MODEL_EMBED, MODEL_FLASH, MODEL_PRO, embed
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.storage import AssetUploader
from app.tools.brand_rag import BrandRagRequest, brand_rag
from app.tools.generate_image import ImageRequest, generate_image
from app.tools.generate_video import VideoRequest, generate_video
from app.tools.memory_search import MemorySearchRequest, RecentPost, memory_search
from app.tools.overlay_hook import overlay_hook, overlay_hook_image

logger = structlog.get_logger(__name__)

_APP, _USER = "content-agent", "client"
_PROMPT = Path(__file__).resolve().parent / "prompts" / "generator.md"


class PipelineError(RuntimeError):
    """Raised on a fatal pipeline precondition (e.g. brand doc not ingested)."""


class WeekResult(BaseModel):
    week_id: UUID
    post_ids: list[UUID]
    asset_urls: list[str]
    cost_eur: Decimal
    status: str


# ---- metered reasoning embedding -------------------------------------------


class _ReasonEmbedRequest(MeterRequest):
    text: str


class _ReasonEmbedResult(MeteredResult):
    vector: list[float]


@meter("embedding")
async def _embed_reasoning(req: _ReasonEmbedRequest) -> _ReasonEmbedResult:
    """Embed a post's reasoning for the memory_search surface."""
    vector = await embed(req.text)
    tokens = max(1, len(req.text) // 4)
    return _ReasonEmbedResult(
        model=MODEL_EMBED,
        cost_eur=pricing.embedding_cost(MODEL_EMBED, tokens),
        vector=vector,
    )


# ---- helpers ----------------------------------------------------------------


def _strip(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return t


async def _run_agent(agent: LlmAgent, message: str, session_id: str) -> str:
    runner = InMemoryRunner(agent=agent, app_name=_APP)
    await runner.session_service.create_session(
        app_name=_APP, user_id=_USER, session_id=session_id
    )
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final = ""
    async for ev in runner.run_async(
        user_id=_USER, session_id=session_id, new_message=content
    ):
        if ev.is_final_response() and ev.content and ev.content.parts:
            final = ev.content.parts[0].text or ""
    return final


# Coarse visual "setting" families — used to stop the same scene (e.g. ocean
# swimming) recurring week over week. Keyword match against the scene_prompt.
_SCENE_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("water", ("ocean", "beach", "swim", "water", "pool", "wave", "surf",
               "coast", "shore", "lake", "river", "seaside", "underwater")),
    ("gym", ("gym", "weight", "dumbbell", "barbell", "treadmill", "fitness",
             "sportschool", "yoga studio")),
    ("kitchen", ("kitchen", "cook", "meal", "food", "plate", "salad", "keuken")),
    ("home", ("home", "living room", "bedroom", "couch", "sofa", "indoor", "desk")),
    ("nature", ("forest", "park", "trail", "mountain", "hik", "garden", "field",
                "woods", "meadow", "hill", "trees")),
    ("urban", ("city", "street", "urban", "rooftop", "cafe", "market", "plaza")),
)


def _scene_family(scene: str | None) -> str:
    """Map a scene_prompt to a coarse setting family (or 'other' if unrecognised)."""
    s = (scene or "").lower()
    for family, keys in _SCENE_FAMILIES:
        if any(k in s for k in keys):
            return family
    return "other"


def _recent_scene_families(recent: list[RecentPost]) -> set[str]:
    """The identifiable setting families used by recent posts (excludes 'other')."""
    fams = {_scene_family(p.scene_prompt) for p in recent}
    fams.discard("other")
    return fams


def _recent_block(recent: list[RecentPost]) -> str:
    if not recent:
        return "(none yet — first week)"
    lines: list[str] = []
    for p in recent:
        scene = (p.scene_prompt or "").strip().replace("\n", " ")
        if len(scene) > 140:
            scene = scene[:140] + "…"
        line = f"- {p.pillar} | theme: {p.theme} | value: {p.value} | hook: {p.hook}"
        if scene:
            line += f" | scene: {scene}"
        lines.append(line)
    return "\n".join(lines)


def _generator_message(
    themes: str, brand_chunks: list[str], rule_texts: list[str], recent: list[RecentPost]
) -> str:
    brand = "\n\n---\n\n".join(brand_chunks) if brand_chunks else "(none retrieved)"
    rules = "\n".join(f"- {t}" for t in rule_texts) if rule_texts else "(none)"
    avoid = sorted(_recent_scene_families(recent))
    avoid_line = (
        f"Recently used visual settings — do NOT reuse these: {', '.join(avoid)}. "
        if avoid
        else ""
    )
    return (
        f"## This week's themes (from the researcher)\n{themes}\n\n"
        f"## Brand context (retrieved from the requirements doc)\n{brand}\n\n"
        f"## Active rules\n{rules}\n\n"
        f"## Recently covered (make this week DIFFERENT)\n{_recent_block(recent)}\n\n"
        "Produce the 3 PostSpecs now (2 image, 1 video, distinct pillars). "
        "Make them clearly different from the recently covered posts above. "
        f"{avoid_line}"
        "Give each post a DISTINCT visual setting, and do NOT default to water/ocean "
        "scenes just because the brand is 'Blue' — vary the setting (park, gym, home, "
        "kitchen, city, forest, studio, market, ...). The video in particular MUST use "
        "a setting not seen in the recent posts above."
    )


def _prompt_version() -> str:
    """The generator prompt's git blob SHA (matches `git hash-object`) for the blob."""
    data = _PROMPT.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def _reasoning_blob(
    spec: PostSpec, brand_chunk_ids: list[UUID], rule_ids: list[UUID], asset_model: str
) -> dict:
    r = spec.references_used
    return {
        "schema_version": 1,
        "pillar": spec.pillar,
        "theme": r.theme,
        "value": r.value,
        "hook": spec.hook,
        "scene_prompt": spec.scene_prompt,
        "motion": spec.motion,
        "caption": spec.caption,
        "brand_cues": r.brand_cues,
        "rule_applied": r.rule_applied,
        "brand_chunk_ids": [str(i) for i in brand_chunk_ids],
        "active_rule_ids": [str(i) for i in rule_ids],
        "engagement_template": spec.caption_template,
        "models": {"generator": MODEL_PRO, "researcher": MODEL_FLASH, "asset": asset_model},
        "prompt_version": _prompt_version(),
    }


def _reason_text(spec: PostSpec) -> str:
    r = spec.references_used
    return f"{spec.pillar} | {r.theme} | {r.value} | {spec.hook} | {spec.scene_prompt} | {spec.caption}"


@dataclass
class _Asset:
    data: bytes
    model: str
    cost_eur: Decimal
    ext: str
    content_type: str


async def _render(spec: PostSpec, post_id: UUID) -> _Asset:
    """Render one PostSpec (metered) and burn in its hook."""
    if spec.type == "image":
        res = await generate_image(
            ImageRequest(
                prompt=build_image_prompt(spec.scene_prompt),
                aspect_ratio="9:16",
                trigger="cron",
                post_id=post_id,
            )
        )
        ext = ".jpg" if "jpeg" in res.mime_type else ".png"
        data = (
            await overlay_hook_image(res.image_bytes, spec.hook, ext)
            if spec.hook
            else res.image_bytes
        )
        return _Asset(data, res.model, res.cost_eur, ext, res.mime_type)

    vid = await generate_video(
        VideoRequest(
            prompt=build_video_prompt(spec.scene_prompt, spec.motion),
            aspect_ratio="9:16",
            duration_seconds=spec.duration_seconds or 8,
            trigger="cron",
            post_id=post_id,
        )
    )
    data = await overlay_hook(vid.video_bytes, spec.hook) if spec.hook else vid.video_bytes
    return _Asset(data, vid.model, vid.cost_eur, ".mp4", vid.mime_type or "video/mp4")


async def _enforce_scene_variety(
    out: GeneratorOutput,
    recent_families: set[str],
    base_message: str,
    week_start: date,
) -> GeneratorOutput:
    """Re-prompt once if the video reuses a recent visual setting (e.g. ocean).

    The video is the worst repeat offender, so we hard-guard it: if its setting
    family was used in the recent posts, we ask the generator to redo all 3 with a
    different video setting. Runs before any rendering, so no asset spend is wasted.
    Best-effort — if the correction call fails we keep the original output; variety
    never blocks a weekly run.
    """
    video = next((p for p in out.posts if p.type == "video"), None)
    if video is None:
        return out
    family = _scene_family(video.scene_prompt)
    if family == "other" or family not in recent_families:
        return out

    logger.info("pipeline.scene_repeat", family=family, scene=video.scene_prompt[:80])
    banned = ", ".join(sorted(recent_families | {family}))
    correction = (
        f"{base_message}\n\n## CORRECTION\nThe VIDEO you produced uses a '{family}' "
        "setting, which was used in the recent posts above. Regenerate all 3 posts; "
        "the video MUST use a completely different setting — do NOT use any of: "
        f"{banned}."
    )
    try:
        retried = GeneratorOutput.model_validate_json(
            _strip(await _run_agent(build_generator(), correction, f"wk-{week_start}-g2"))
        )
    except Exception:  # noqa: BLE001 — variety retry is best-effort, never fatal
        logger.warning("pipeline.scene_repeat_retry_failed", family=family)
        return out
    new_video = next((p for p in retried.posts if p.type == "video"), None)
    if new_video is None:
        return out
    if _scene_family(new_video.scene_prompt) in recent_families:
        logger.warning("pipeline.scene_repeat_unresolved", family=family)
    return retried


# ---- entry point ------------------------------------------------------------


async def run_weekly(week_start: date, *, uploader: AssetUploader) -> WeekResult:
    """Run the full weekly flow for `week_start` and persist 3 versioned posts."""
    pool = get_pool()

    async with pool.acquire() as conn:
        if await count_chunks(conn) == 0:
            raise PipelineError(
                "brand_chunks is empty — run scripts/ingest_brand.py first."
            )
        week = await get_week_by_start(conn, week_start) or await insert_week(
            conn, week_start
        )

    logger.info("pipeline.start", week_start=str(week_start), week_id=str(week.id))

    # 1. research -> themes
    themes = _strip(
        await _run_agent(
            build_researcher(),
            "Produce this week's Blue Fit content themes.",
            f"wk-{week_start}-r",
        )
    )
    try:
        parsed = json.loads(themes)
        brief = parsed if isinstance(parsed, dict) else {"themes": parsed}
    except json.JSONDecodeError:
        brief = {"themes_raw": themes}
    async with pool.acquire() as conn:
        await set_week_brief(conn, week.id, brief)

    # 2. retrieve: brand grounding + variety memory + active rules
    query = themes[:1000]
    brand = await brand_rag(BrandRagRequest(query=query, limit=5, trigger="cron"))
    recent = await memory_search(
        MemorySearchRequest(query=query, limit=6, trigger="cron")
    )
    async with pool.acquire() as conn:
        rules = await get_active_rules(conn)
    rule_ids = [r.id for r in rules]
    total = brand.cost_eur + recent.cost_eur

    # 3. generate 3 specs grounded in the retrieved context
    message = _generator_message(
        themes, brand.chunks, [r.text for r in rules], recent.versions
    )
    out = GeneratorOutput.model_validate_json(
        _strip(await _run_agent(build_generator(), message, f"wk-{week_start}-g"))
    )
    out = await _enforce_scene_variety(
        out, _recent_scene_families(recent.versions), message, week_start
    )

    # 4. render images first, video last; isolate each post so one failure survives
    specs = sorted(out.posts, key=lambda s: s.type == "video")
    post_ids: list[UUID] = []
    urls: list[str] = []
    for spec in specs:
        try:
            async with pool.acquire() as conn:
                post = await insert_post(
                    conn, week_id=week.id, type=spec.type, pillar=spec.pillar
                )
            asset = await _render(spec, post.id)
            total += asset.cost_eur
            url = await uploader.upload(
                data=asset.data,
                key=f"weeks/{week_start}/{post.id}{asset.ext}",
                content_type=asset.content_type,
            )
            blob = _reasoning_blob(spec, brand.chunk_ids, rule_ids, asset.model)
            reason = await _embed_reasoning(
                _ReasonEmbedRequest(
                    text=_reason_text(spec), trigger="cron", post_id=post.id
                )
            )
            total += reason.cost_eur
            async with pool.acquire() as conn, conn.transaction():
                version = await insert_version(
                    conn,
                    post_id=post.id,
                    parent_version_id=None,
                    version_number=1,
                    asset_url=url,
                    caption=spec.caption,
                    edit_instruction=None,
                    reasoning_blob=blob,
                    reasoning_embedding=reason.vector,
                )
                await set_current_version(conn, post.id, version.id)
            post_ids.append(post.id)
            urls.append(url)
            logger.info("pipeline.post_done", pillar=spec.pillar, type=spec.type, url=url)
        except Exception as exc:  # noqa: BLE001 — isolate: keep the other posts
            logger.error(
                "pipeline.post_failed", pillar=spec.pillar, type=spec.type, error=str(exc)
            )

    status = "ready" if len(post_ids) == len(specs) else "failed"
    async with pool.acquire() as conn:
        await set_week_status(conn, week.id, status)
    logger.info("pipeline.done", status=status, posts=len(post_ids), cost_eur=str(total))
    return WeekResult(
        week_id=week.id,
        post_ids=post_ids,
        asset_urls=urls,
        cost_eur=total,
        status=status,
    )
