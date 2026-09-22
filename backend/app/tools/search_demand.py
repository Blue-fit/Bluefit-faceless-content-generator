"""What Dutch people actually type into search — real queries, not guessed keywords.

Mines Google's autocomplete endpoint (`suggestqueries`, no key, no cost) for the
PROBLEMS the audience is searching about, in their own words. This step is
deliberately brand-blind: it asks only what viewers struggle with, not how Blue Fit
would answer. The researcher and generator then combine a real problem with a pillar
and a Power-9 value to produce the solution Bluei acts out.

Scope is **national NL** (`hl=nl, gl=nl`), not the club's city: local seeds return
almost nothing (`fitness lent nijmegen` -> 1 suggestion) and would cap reach.

Free, so no `@meter`. The endpoint is undocumented, so this is **fail-soft** by
design: a seed that errors is skipped and an empty result just means the week runs
exactly as it did before keyword mining existed.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

_ENDPOINT = "https://suggestqueries.google.com/complete/search"
_TIMEOUT = 8.0
_CONCURRENCY = 8
_MAX_LEN = 80  # drop rambling suggestions

# The viewer's PROBLEMS, in their own words — deliberately NOT derived from the four
# pillars or the Power-9 values. This step only asks "what is our audience struggling
# with and searching for"; the brand lens is applied afterwards, when the researcher
# and generator turn a problem + a value into the solution Bluei acts out.
#
# Everyday Dutch only, never brand jargon: "gezond eten blue zones" returns 0
# suggestions and "natuurlijk bewegen" returns physiotherapy practices.
_TOPICS: tuple[str, ...] = (
    "altijd moe",
    "geen energie",
    "geen tijd om te sporten",
    "geen motivatie om te sporten",
    "weer beginnen met sporten",
    "slecht slapen",
    "te veel stress",
    "de hele dag zitten",
    "stijve spieren",
    "conditie opbouwen",
    "fit blijven als je ouder wordt",
    "gezond eten volhouden",
)
# Question words put the mining where the audience's curiosity is.
_PREFIXES: tuple[str, ...] = ("hoe", "waarom", "wat", "welke")

_QUESTION_WORDS = ("hoe", "waarom", "wat", "welke", "wanneer", "hoeveel", "is", "moet")

# Real demand that is off-brand for a fitness club: medical/clinical situations (the
# brand makes no medical claims) and queries about other countries. The agents are
# told to skip anything else that doesn't fit; this only catches the clear cases.
_BLOCK: tuple[str, ...] = (
    # medical / clinical
    "zwanger", "menopauze", "overgang", "adhd", "autisme", "burn out", "burnout",
    "depressie", "griep", "ziek", "kanker", "diabetes", "medicijn", "pillen",
    "operatie", "corona", "bevalling", "blessure",
    # other countries / pets — real demand, wrong audience
    "amerika", "china", "japan", "hond", "kat", "baby",
    # rival clubs: never build a post around a competitor's search term
    "sportcity", "basic fit", "basic-fit", "basicfit", "fit for free", "fitforfree",
    "anytime fitness", "trainmore", "sportcity",
    # price / product intent, not wellness ("wat kost meer energie" is energy bills)
    "kost", "prijs", "korting", "abonnement", "boek", "kopen",
)


class DemandQuery(BaseModel):
    text: str
    topic: str  # the everyday-Dutch topic that surfaced it
    seed_count: int  # how many of that topic's seeds surfaced it
    is_question: bool


class SearchDemandResult(BaseModel):
    queries: list[DemandQuery]

    def as_lines(self, limit: int = 25) -> str:
        """The block handed to the agents, grouped by topic so no theme dominates."""
        if not self.queries:
            return "(no search data this week — use your own judgement)"
        by_topic: dict[str, list[str]] = {}
        for q in self.queries[:limit]:
            by_topic.setdefault(q.topic, []).append(q.text)
        blocks = [
            "**{}**\n{}".format(topic, "\n".join(f"- {t}" for t in texts))
            for topic, texts in by_topic.items()
        ]
        return "\n".join(blocks)


def _seed_pairs() -> list[tuple[str, str]]:
    """(topic, seed) pairs so every suggestion can be traced back to its topic."""
    pairs = [(topic, topic) for topic in _TOPICS]
    pairs += [(topic, f"{prefix} {topic}") for topic in _TOPICS for prefix in _PREFIXES]
    return pairs


def build_seeds() -> list[str]:
    """The flat seed list (national, no city terms)."""
    return [seed for _, seed in _seed_pairs()]


async def _suggest(client: httpx.AsyncClient, seed: str) -> list[str]:
    """Autocomplete suggestions for one seed ([] on any failure — never fatal)."""
    try:
        resp = await client.get(
            _ENDPOINT, params={"client": "firefox", "hl": "nl", "gl": "nl", "q": seed}
        )
        resp.raise_for_status()
        payload = json.loads(resp.text)
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("search_demand.seed_failed", seed=seed, error=str(exc)[:120])
        return []
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        return []
    return [str(s) for s in payload[1]]


def _keep(suggestion: str, seeds: set[str]) -> bool:
    text = suggestion.strip().lower()
    if not text or len(text) > _MAX_LEN or text in seeds or " " not in text:
        return False
    return not any(bad in text for bad in _BLOCK)


async def search_demand(limit: int = 40) -> SearchDemandResult:
    """Mine real queries per topic, balanced so every topic is represented.

    Autocomplete gives no volumes, and nearly every suggestion appears under a single
    seed — so a flat ranking degenerates into alphabetical order and one topic floods
    the list. Instead each topic is ranked internally (questions first: a question
    makes a better hook than a noun phrase) and the topics are then interleaved.
    """
    pairs = _seed_pairs()
    semaphore = asyncio.Semaphore(_CONCURRENCY)
    lowered = {seed.lower() for _, seed in pairs} | {t.lower() for t in _TOPICS}

    async def one(client: httpx.AsyncClient, seed: str) -> list[str]:
        async with semaphore:
            return await _suggest(client, seed)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        results = await asyncio.gather(*(one(client, seed) for _, seed in pairs))

    # topic -> query -> how many of that topic's seeds surfaced it
    per_topic: dict[str, dict[str, int]] = {topic: {} for topic in _TOPICS}
    for (topic, _seed), suggestions in zip(pairs, results, strict=True):
        for raw in suggestions:
            text = raw.strip().lower()
            if _keep(text, lowered):
                per_topic[topic][text] = per_topic[topic].get(text, 0) + 1

    ranked: dict[str, list[DemandQuery]] = {}
    for topic, counts in per_topic.items():
        queries = [
            DemandQuery(
                text=text,
                topic=topic,
                seed_count=count,
                is_question=text.split()[0] in _QUESTION_WORDS,
            )
            for text, count in counts.items()
        ]
        queries.sort(key=lambda q: (not q.is_question, -q.seed_count, len(q.text)))
        ranked[topic] = queries

    # Round-robin, so a week always has material for several different pillars.
    picked: list[DemandQuery] = []
    depth = max((len(v) for v in ranked.values()), default=0)
    for rank in range(depth):
        for topic in _TOPICS:
            if len(picked) >= limit:
                break
            if rank < len(ranked[topic]):
                picked.append(ranked[topic][rank])
        if len(picked) >= limit:
            break

    logger.info(
        "search_demand.done",
        seeds=len(pairs),
        topics_with_data=sum(1 for v in ranked.values() if v),
        picked=len(picked),
        questions=sum(1 for q in picked if q.is_question),
    )
    return SearchDemandResult(queries=picked)
