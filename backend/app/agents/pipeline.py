"""Production weekly pipeline: researcher -> retrieve -> generator -> render -> persist.

The single entry point the scheduler/trigger calls. Orchestrates the RAG-grounded
weekly run and writes versioned posts to the DB. Storage (R2) is Jacob's domain, so
the pipeline takes an injected `AssetUploader`; it never implements R2 itself.

`run_all.py` stays as the offline (no-DB/no-R2) smoke test; this is the DB-backed,
metered production twin.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, NamedTuple
from uuid import UUID

import asyncpg
import httpx
import structlog
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.agents.generator import build_generator
from app.agents.mascot import mascot_refs_version
from app.agents.render import render_base
from app.agents.researcher import build_researcher
from app.agents.schemas import SCHEMA_VERSION, GeneratorOutput, PostSpec, TrendBrief
from app.db.connection import get_pool
from app.db.repositories.brand_chunks import count_chunks
from app.db.repositories.post_versions import get_version, insert_version
from app.db.repositories.posts import get_posts_for_week, insert_post, set_current_version
from app.db.repositories.rules import get_active_rules
from app.db.repositories.weeks import (
    get_week_by_start,
    insert_week,
    list_weeks,
    set_week_brief,
    set_week_status,
)
from app.genai_client import MODEL_EMBED, MODEL_FLASH, MODEL_PRO, embed
from app.meter import MeteredResult, MeterRequest, meter, pricing
from app.storage import AssetUploader
from app.tools.brand_rag import BrandRagRequest, brand_rag
from app.tools.memory_search import MemorySearchRequest, RecentPost, memory_search
from app.tools.overlay_hook import overlay_hook
from app.tools.search_demand import SearchDemandResult, search_demand

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


# ---- metered research -------------------------------------------------------

_RESEARCH_MESSAGE = "Produce this week's Blue Fit content themes."
_DEMAND_HEADING = (
    "## What our audience is actually struggling with right now\n"
    "Real Google autocomplete queries (national NL) — the PROBLEMS people are typing,\n"
    "in their own words, grouped by theme. They are deliberately NOT filtered through\n"
    "our brand. Your job: take a real problem from this list, decide which pillar and\n"
    "Power-9 value speaks to it, and build the theme around the SOLUTION Blue Fit can\n"
    "offer. Skip anything medical, about another gym, or otherwise off-brand.\n\n"
)
# Google returns citations as short-lived redirects through this host; they 404
# within hours, so they must be resolved to the real article NOW, at generation
# time, or the stored provenance is worthless.
_GROUNDING_HOST = "vertexaisearch.cloud.google.com"
_RESOLVE_TIMEOUT = 10.0


class _ResearchRequest(MeterRequest):
    week_start: date
    demand: str = ""


class _ResearchResult(MeteredResult):
    brief: TrendBrief | None  # None when the researcher never returned valid JSON
    raw: str  # the text handed to retrieval + the generator either way


def _parse_brief(text: str, week_start: date) -> TrendBrief | None:
    """Validate the researcher's JSON into a `TrendBrief` (None if it doesn't fit).

    The researcher doesn't know the week, so `week_start` is supplied here.
    """
    try:
        data = json.loads(_strip(text))
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        data = {"themes": data}
    if not isinstance(data, dict):
        return None
    try:
        return TrendBrief.model_validate({**data, "week_start": data.get("week_start") or week_start})
    except ValidationError as exc:
        logger.warning("research.invalid_brief", error=str(exc)[:300])
        return None


async def _resolve_source(client: httpx.AsyncClient, url: str) -> str:
    """The article a grounding redirect points at (the original URL on failure).

    A 4xx from the publisher still redirects first, so the final URL is usable even
    when the page itself refuses our request.
    """
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        logger.warning("research.source_unresolved", url=url[:80], error=str(exc)[:120])
        return url
    final = str(resp.url)
    return url if _GROUNDING_HOST in final else final


async def _resolve_sources(brief: TrendBrief) -> TrendBrief:
    """Replace grounding redirects in `brief` with the real article URLs.

    Best-effort and never fatal: a theme keeps its redirect if resolution fails.
    """
    targets = sorted({t.source_url for t in brief.themes if _GROUNDING_HOST in t.source_url})
    if not targets:
        return brief
    async with httpx.AsyncClient(follow_redirects=True, timeout=_RESOLVE_TIMEOUT) as client:
        resolved = await asyncio.gather(*(_resolve_source(client, u) for u in targets))
    mapping = dict(zip(targets, resolved, strict=True))
    logger.info("research.sources_resolved", resolved=sum(1 for u in targets if mapping[u] != u),
                total=len(targets))
    return brief.model_copy(
        update={
            "themes": [
                t.model_copy(update={"source_url": mapping.get(t.source_url, t.source_url)})
                for t in brief.themes
            ]
        }
    )


async def _safe_demand() -> SearchDemandResult:
    """Mine search demand, degrading to nothing if the endpoint misbehaves.

    `suggestqueries` is undocumented and free; it must never be able to stop a
    weekly run. With no data the agents fall back to their own judgement, exactly
    as they did before keyword mining existed.
    """
    try:
        return await search_demand()
    except Exception as exc:  # noqa: BLE001 — never fatal
        logger.warning("pipeline.search_demand_failed", error=str(exc)[:160])
        return SearchDemandResult(queries=[])


@meter("research")
async def _research(req: _ResearchRequest) -> _ResearchResult:
    """Run the researcher and validate its brief, repairing once if malformed.

    Metered from the agent's real token counts. Note: `google_search` grounding is
    billed separately by Google and is not captured here — this records the model
    tokens, which is what our pricing table covers.

    A brief that is still invalid after the repair does NOT fail the week: the raw
    text is passed through (the generator can usually still use it) and the failure
    is logged loudly. A missing week of posts would be worse than a loose brief.
    """
    message = (
        f"{_DEMAND_HEADING}{req.demand}\n\n{_RESEARCH_MESSAGE}"
        if req.demand
        else _RESEARCH_MESSAGE
    )
    run = await _run_agent(build_researcher(), message, f"wk-{req.week_start}-r")
    in_tokens, out_tokens = run.input_tokens, run.output_tokens
    brief = _parse_brief(run.text, req.week_start)

    if brief is None:
        logger.info("research.repairing")
        repair = await _run_agent(
            build_researcher(),
            f"{message}\n\n## CORRECTION\nYour previous reply was not valid "
            "JSON in the required shape. Return ONLY the JSON object described in your "
            'instructions — keys "themes" -> a list of {title, summary, why_relevant, '
            'source_url} — with no prose and no markdown fences.',
            f"wk-{req.week_start}-r2",
        )
        in_tokens += repair.input_tokens
        out_tokens += repair.output_tokens
        brief = _parse_brief(repair.text, req.week_start)
        if brief is not None:
            run = repair
        else:
            logger.warning("research.brief_unvalidated", raw=run.text[:200])

    if brief is not None:
        brief = await _resolve_sources(brief)
    return _ResearchResult(
        model=MODEL_FLASH,
        cost_eur=pricing.text_cost(MODEL_FLASH, in_tokens, out_tokens),
        brief=brief,
        raw=run.text,
    )


# ---- metered generation -----------------------------------------------------


class _GenerateRequest(MeterRequest):
    message: str
    session_id: str


class _GenerateResult(MeteredResult):
    text: str


@meter("generation")
async def _generate(req: _GenerateRequest) -> _GenerateResult:
    """One generator turn, priced from its real token counts."""
    run = await _run_agent(build_generator(), req.message, req.session_id)
    return _GenerateResult(
        model=MODEL_PRO,
        cost_eur=pricing.text_cost(MODEL_PRO, run.input_tokens, run.output_tokens),
        text=run.text,
    )


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


class _AgentRun(NamedTuple):
    """An agent's final text plus the tokens it actually used (for metering)."""

    text: str
    input_tokens: int
    output_tokens: int


async def _run_agent(agent: LlmAgent, message: str, session_id: str) -> _AgentRun:
    """Run `agent` to its final response, summing token usage across its events.

    An agent may take several model turns (a tool call, then the answer), so the
    counts are accumulated rather than read from the final event alone.
    """
    runner = InMemoryRunner(agent=agent, app_name=_APP)
    await runner.session_service.create_session(
        app_name=_APP, user_id=_USER, session_id=session_id
    )
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final = ""
    in_tokens = out_tokens = 0
    async for ev in runner.run_async(
        user_id=_USER, session_id=session_id, new_message=content
    ):
        usage = ev.usage_metadata
        if usage is not None:
            in_tokens += usage.prompt_token_count or 0
            out_tokens += usage.candidates_token_count or 0
        if ev.is_final_response() and ev.content and ev.content.parts:
            final = ev.content.parts[0].text or ""
    return _AgentRun(final, in_tokens, out_tokens)


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
        if p.beat:
            line += f" | beat: {p.beat}"
        if scene:
            line += f" | scene: {scene}"
        lines.append(line)
    return "\n".join(lines)


def _generator_message(
    themes: str,
    brand_chunks: list[str],
    rule_texts: list[str],
    recent: list[RecentPost],
    forbidden_values: frozenset[str] = frozenset(),
    demand: str = "",
) -> str:
    brand = "\n\n---\n\n".join(brand_chunks) if brand_chunks else "(none retrieved)"
    rules = "\n".join(f"- {t}" for t in rule_texts) if rule_texts else "(none)"
    avoid = sorted(_recent_scene_families(recent))
    avoid_line = (
        f"Recently used visual settings — do NOT reuse these: {', '.join(avoid)}. "
        if avoid
        else ""
    )
    forbidden = (
        ", ".join(sorted(forbidden_values)) if forbidden_values else "(none — first week)"
    )
    demand_block = (
        (
            "## Real search queries to target (what our audience is searching)\n"
            "These are the audience's own words for their problems — unfiltered by our "
            "brand. Build each post as the SOLUTION to one of them, told through its "
            "pillar and Power-9 value and acted out by Bluey. Take the hook/caption "
            "keyword FROM this list — do not invent one. Skip anything medical, about "
            "another gym, or off-brand.\n"
            f"{demand}\n\n"
        )
        if demand
        else ""
    )
    return (
        f"## This week's themes (from the researcher)\n{themes}\n\n"
        f"{demand_block}"
        "## Brand context (retrieved from the requirements doc) — use it for VALUES, "
        "VOICE and PILLARS only; ignore any visual/photography/pacing direction in it. "
        "The visual world is fixed by the mascot brief in your instructions.\n"
        f"{brand}\n\n"
        f"## Active rules\n{rules}\n\n"
        f"## Recently covered (make this week DIFFERENT)\n{_recent_block(recent)}\n\n"
        "## Forbidden Power-9 values (used LAST week — do NOT use any of these)\n"
        f"{forbidden}\n\n"
        "Produce the 3 PostSpecs now (2 image, 1 video). WEEKLY ANCHOR RULE: each post "
        "is anchored to exactly ONE Power-9 value bound to exactly ONE pillar; across "
        "the 3 posts use 3 DIFFERENT values and 3 DIFFERENT pillars, and NONE of the "
        "forbidden values above, each starring the Blue Fit mascot with one "
        "explicit `beat`. "
        "Make them clearly different from the recently covered posts above — "
        "different themes, values, settings AND beats. "
        f"{avoid_line}"
        "Give each post a DISTINCT visual setting, and do NOT default to water/ocean "
        "scenes just because the brand is 'Blue' — vary the setting (park, gym, home, "
        "kitchen, city, forest, studio, market, ...). The video in particular MUST use "
        "a setting not seen in the recent posts above."
    )


async def _last_week_values(conn: asyncpg.Connection, week_start: date) -> frozenset[str]:
    """The Power-9 values used by the most recent week BEFORE `week_start`.

    Client rule: the 3 values picked in a week cannot repeat in the next (a one-week
    cooldown; they return the week after). Empty on cold start. A re-run of the
    current week is excluded so it never forbids its own values.
    """
    earlier = [w for w in await list_weeks(conn) if w.week_start < week_start]
    if not earlier:
        return frozenset()
    prev = max(earlier, key=lambda w: w.week_start)
    values: set[str] = set()
    for p in await get_posts_for_week(conn, prev.id):
        if p.current_version_id is None:
            continue
        v = await get_version(conn, p.current_version_id)
        val = (v.reasoning_blob or {}).get("value") if v else None
        if val:
            values.add(str(val))
    return frozenset(values)


def _value_rule_violations(out: GeneratorOutput, forbidden: frozenset[str]) -> list[str]:
    """Why the week breaks the anchor rule (empty list = OK). Pure, unit-testable.

    Rule: 3 different Power-9 values, 3 different pillars (1 value <-> 1 pillar per
    post), and none of the values used last week.
    """
    values = [p.references_used.value for p in out.posts]
    pillars = [p.pillar for p in out.posts]
    problems: list[str] = []
    if len(set(values)) != len(values):
        problems.append(f"values repeat within the week: {values}")
    if len(set(pillars)) != len(pillars):
        problems.append(f"pillars repeat within the week: {pillars}")
    # Case-insensitive: weeks generated before the typed Power9Value stored free text.
    banned = {f.lower() for f in forbidden}
    used_forbidden = sorted(v for v in set(values) if v.lower() in banned)
    if used_forbidden:
        problems.append(f"values used last week (forbidden): {used_forbidden}")
    return problems


async def _enforce_value_rules(
    out: GeneratorOutput, forbidden: frozenset[str], base_message: str, week_start: date
) -> tuple[GeneratorOutput, Decimal]:
    """Re-prompt once if the week breaks the value/pillar anchor rule.

    Runs before any rendering, so no asset spend is wasted. Best-effort: if the
    correction still violates the rule we keep whichever attempt is closer and log
    it — variety never blocks a weekly run.
    """
    problems = _value_rule_violations(out, forbidden)
    if not problems:
        return out, Decimal(0)
    logger.info("pipeline.value_rule_violation", problems=problems)
    correction = (
        f"{base_message}\n\n## CORRECTION\nYour 3 posts break the weekly anchor rule: "
        f"{'; '.join(problems)}. Regenerate all 3 posts so they use 3 DIFFERENT Power-9 "
        "values and 3 DIFFERENT pillars, and use NONE of the forbidden values."
    )
    gen = await _generate(
        _GenerateRequest(trigger="cron", message=correction, session_id=f"wk-{week_start}-v2")
    )
    try:
        retried = GeneratorOutput.model_validate_json(_strip(gen.text))
    except Exception:  # noqa: BLE001 — rule retry is best-effort, never fatal
        logger.warning("pipeline.value_rule_retry_failed", problems=problems)
        return out, gen.cost_eur
    remaining = _value_rule_violations(retried, forbidden)
    if remaining:
        logger.warning("pipeline.value_rule_unresolved", problems=remaining)
    best = retried if len(remaining) <= len(problems) else out
    return best, gen.cost_eur


def _prompt_version() -> str:
    """The generator prompt's git blob SHA (matches `git hash-object`) for the blob."""
    data = _PROMPT.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def _reasoning_blob(
    spec: PostSpec,
    brand_chunk_ids: list[UUID],
    rule_ids: list[UUID],
    asset_model: str,
    base_asset_url: str,
    theme_sources: dict[str, str] | None = None,
) -> dict:
    r = spec.references_used
    return {
        "schema_version": SCHEMA_VERSION,
        "pillar": spec.pillar,
        "theme": r.theme,
        # Which researched article backed this post (None if the brief was invalid
        # or the generator named a theme the researcher didn't return).
        "theme_source_url": (theme_sources or {}).get(r.theme or ""),
        "value": r.value,
        "hook": spec.hook,
        "beat": spec.beat,
        "scene_prompt": spec.scene_prompt,
        "base_asset_url": base_asset_url,
        "motion": spec.motion,
        "caption": spec.caption,
        "brand_cues": r.brand_cues,
        "rule_applied": r.rule_applied,
        "brand_chunk_ids": [str(i) for i in brand_chunk_ids],
        "active_rule_ids": [str(i) for i in rule_ids],
        "engagement_template": spec.caption_template,
        "models": {"generator": MODEL_PRO, "researcher": MODEL_FLASH, "asset": asset_model},
        "prompt_version": _prompt_version(),
        "mascot_refs_version": mascot_refs_version(),
    }


def _reason_text(spec: PostSpec) -> str:
    r = spec.references_used
    return (
        f"{spec.pillar} | {r.theme} | {r.value} | {spec.hook} | {spec.beat} | "
        f"{spec.scene_prompt} | {spec.caption}"
    )


@dataclass
class _Asset:
    data: bytes  # composited (hook burned in)
    base: bytes  # pre-overlay original — stored so text-size edits keep the image
    model: str
    cost_eur: Decimal
    ext: str
    content_type: str


async def _render(spec: PostSpec, post_id: UUID) -> _Asset:
    """Render one PostSpec (metered, mascot in frame).

    Images carry their hook in-picture (model typography, read-back verified), so
    the render IS the final and the base. Videos are rendered clean and get the
    hook overlaid; the clean clip is kept as the base for cheap text edits.
    """
    asset = await render_base(
        spec.type,
        spec.scene_prompt,
        spec.motion,
        post_id=post_id,
        trigger="cron",
        duration_seconds=spec.duration_seconds or 8,
        hook=spec.hook if spec.type == "image" else None,
    )
    base = asset.data
    if spec.type == "image" or not spec.hook:
        data = base
    else:
        data = await overlay_hook(base, spec.hook)
    return _Asset(data, base, asset.model, asset.cost_eur, asset.ext, asset.content_type)


async def _enforce_scene_variety(
    out: GeneratorOutput,
    recent_families: set[str],
    base_message: str,
    week_start: date,
) -> tuple[GeneratorOutput, Decimal]:
    """Re-prompt once if the video reuses a recent visual setting (e.g. ocean).

    The video is the worst repeat offender, so we hard-guard it: if its setting
    family was used in the recent posts, we ask the generator to redo all 3 with a
    different video setting. Runs before any rendering, so no asset spend is wasted.
    Best-effort — if the correction call fails we keep the original output; variety
    never blocks a weekly run.
    """
    video = next((p for p in out.posts if p.type == "video"), None)
    if video is None:
        return out, Decimal(0)
    family = _scene_family(video.scene_prompt)
    if family == "other" or family not in recent_families:
        return out, Decimal(0)

    logger.info("pipeline.scene_repeat", family=family, scene=video.scene_prompt[:80])
    banned = ", ".join(sorted(recent_families | {family}))
    correction = (
        f"{base_message}\n\n## CORRECTION\nThe VIDEO you produced uses a '{family}' "
        "setting, which was used in the recent posts above. Regenerate all 3 posts; "
        "the video MUST use a completely different setting — do NOT use any of: "
        f"{banned}."
    )
    gen = await _generate(
        _GenerateRequest(trigger="cron", message=correction, session_id=f"wk-{week_start}-g2")
    )
    try:
        retried = GeneratorOutput.model_validate_json(_strip(gen.text))
    except Exception:  # noqa: BLE001 — variety retry is best-effort, never fatal
        logger.warning("pipeline.scene_repeat_retry_failed", family=family)
        return out, gen.cost_eur
    new_video = next((p for p in retried.posts if p.type == "video"), None)
    if new_video is None:
        return out, gen.cost_eur
    if _scene_family(new_video.scene_prompt) in recent_families:
        logger.warning("pipeline.scene_repeat_unresolved", family=family)
    return retried, gen.cost_eur


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

    # 1. what people are really searching (free, fail-soft), then research
    demand = await _safe_demand()
    research = await _research(
        _ResearchRequest(
            trigger="cron", week_start=week_start, demand=demand.as_lines()
        )
    )
    themes = _strip(research.raw)
    theme_sources = (
        {t.title: t.source_url for t in research.brief.themes} if research.brief else {}
    )
    brief: dict[str, Any] = (
        research.brief.model_dump(mode="json")
        if research.brief
        else {"themes_raw": themes}
    )
    # Keep the week's real search demand next to its themes: it's the evidence for
    # why these topics, and what the hooks/captions were told to target.
    brief["search_queries"] = [q.text for q in demand.queries]
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
        forbidden = await _last_week_values(conn, week_start)
    rule_ids = [r.id for r in rules]
    logger.info("pipeline.forbidden_values", values=sorted(forbidden))
    total = research.cost_eur + brand.cost_eur + recent.cost_eur

    # 3. generate 3 specs grounded in the retrieved context
    message = _generator_message(
        themes,
        brand.chunks,
        [r.text for r in rules],
        recent.versions,
        forbidden,
        demand.as_lines(),
    )
    generated = await _generate(
        _GenerateRequest(trigger="cron", message=message, session_id=f"wk-{week_start}-g")
    )
    total += generated.cost_eur
    out = GeneratorOutput.model_validate_json(_strip(generated.text))
    out, value_retry_cost = await _enforce_value_rules(out, forbidden, message, week_start)
    out, scene_retry_cost = await _enforce_scene_variety(
        out, _recent_scene_families(recent.versions), message, week_start
    )
    total += value_retry_cost + scene_retry_cost

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
            # Images: the final is the base (typography is in the picture) — one object.
            base_url = (
                url
                if asset.data == asset.base
                else await uploader.upload(
                    data=asset.base,
                    key=f"weeks/{week_start}/{post.id}-base{asset.ext}",
                    content_type=asset.content_type,
                )
            )
            blob = _reasoning_blob(
                spec, brand.chunk_ids, rule_ids, asset.model, base_url, theme_sources
            )
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
