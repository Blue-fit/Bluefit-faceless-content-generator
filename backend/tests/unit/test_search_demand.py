"""Mining the audience's real problems: noise filtering, topic balance, fail-soft."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.agents import pipeline
from app.tools import search_demand as sd


def test_seeds_are_problems_not_brand_jargon() -> None:
    """Brand words return 0 suggestions or physio practices — seeds stay everyday."""
    seeds = " ".join(sd.build_seeds()).lower()
    for jargon in ("blue zone", "power-9", "pillar", "natural eating", "keep moving"):
        assert jargon not in seeds
    # ...and no city narrowing, which capped reach
    for city in ("nijmegen", "lent", "arnhem"):
        assert city not in seeds


def test_every_topic_is_seeded_bare_and_with_question_prefixes() -> None:
    pairs = sd._seed_pairs()
    for topic in sd._TOPICS:
        seeds = {seed for t, seed in pairs if t == topic}
        assert topic in seeds
        assert {f"{p} {topic}" for p in sd._PREFIXES} <= seeds


@pytest.mark.parametrize(
    "query",
    [
        "hoe beter slapen tijdens zwangerschap",  # medical
        "hoe samen sporten basic fit",  # competitor
        "wat kost meer energie",  # energy bills, not wellness
        "gezond ouder worden boek",  # product intent
        "hoe gezond eten in amerika",  # wrong audience
    ],
)
def test_off_brand_queries_are_filtered(query: str) -> None:
    assert not sd._keep(query, set())


@pytest.mark.parametrize(
    "query",
    ["hoeveel moet je elke dag bewegen", "fit blijven na je 50e", "hoe minder stress op werk"],
)
def test_on_brand_queries_survive(query: str) -> None:
    assert sd._keep(query, set())


def test_seed_echo_and_one_word_results_are_dropped() -> None:
    assert not sd._keep("altijd moe", {"altijd moe"})  # the seed itself
    assert not sd._keep("moe", set())  # single word is not a query worth targeting
    assert not sd._keep("x" * 200, set())  # rambling


@pytest.mark.asyncio
async def test_topics_are_interleaved_so_none_floods_the_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One noisy topic must not consume the whole list — that was the first bug."""

    async def fake_suggest(_client: Any, seed: str) -> list[str]:
        topic = next(t for t in sd._TOPICS if seed.endswith(t))
        return [f"hoe {topic} vraag {i}" for i in range(10)]

    monkeypatch.setattr(sd, "_suggest", fake_suggest)
    result = await sd.search_demand(limit=len(sd._TOPICS))

    topics = [q.topic for q in result.queries]
    assert len(set(topics)) == len(sd._TOPICS)  # every topic represented exactly once
    assert topics == list(sd._TOPICS)  # round-robin order


@pytest.mark.asyncio
async def test_questions_rank_above_plain_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_suggest(_client: Any, seed: str) -> list[str]:
        if seed != sd._TOPICS[0]:
            return []
        return [f"{sd._TOPICS[0]} in de winter", f"hoe {sd._TOPICS[0]} oplossen"]

    monkeypatch.setattr(sd, "_suggest", fake_suggest)
    result = await sd.search_demand(limit=5)
    assert result.queries[0].is_question


@pytest.mark.asyncio
async def test_a_failing_seed_is_skipped_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        async def get(self, *_a: Any, **_k: Any) -> Any:
            raise httpx.ConnectError("no network")

    assert await sd._suggest(_Boom(), "altijd moe") == []  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_pipeline_degrades_to_no_demand_when_mining_breaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead endpoint must never stop a weekly run."""

    async def boom() -> Any:
        raise RuntimeError("endpoint changed")

    monkeypatch.setattr(pipeline, "search_demand", boom)
    result = await pipeline._safe_demand()
    assert result.queries == []
    assert "use your own judgement" in result.as_lines()


def test_as_lines_groups_by_topic() -> None:
    result = sd.SearchDemandResult(
        queries=[
            sd.DemandQuery(text="hoe a", topic="altijd moe", seed_count=1, is_question=True),
            sd.DemandQuery(text="hoe b", topic="altijd moe", seed_count=1, is_question=True),
            sd.DemandQuery(text="hoe c", topic="slecht slapen", seed_count=1, is_question=True),
        ]
    )
    lines = result.as_lines()
    assert "**altijd moe**" in lines and "**slecht slapen**" in lines
    assert lines.index("hoe a") < lines.index("hoe c")
