"""The weekly research step: brief validation, the repair retry, token metering,
and carrying each theme's source into the post's reasoning_blob."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.agents import pipeline
from app.agents.schemas import PostReferences, PostSpec, PostTakeaway

WEEK = date(2026, 9, 25)


def _theme(title: str = "Hara hachi bu") -> dict[str, str]:
    return {
        "title": title,
        "summary": "Stop eating at 80% full.",
        "why_relevant": "Natural Eating / The 80% rule",
        "action": "Leg je bestek neer bij tweederde van je bord",
        "dose": "elke warme maaltijd, 1 keer per dag",
        "payoff": "Je voelt je na het eten lichter en zakt 's middags minder weg",
        "evidence": "Okinawanen stoppen rond 80% verzadiging en eten daardoor minder.",
        "source_url": "https://example.nl/80",
    }


def _payload(*titles: str) -> str:
    return json.dumps({"themes": [_theme(t) for t in titles]})


# ---- parsing -------------------------------------------------------------------


def test_valid_brief_parses_and_week_start_is_injected() -> None:
    brief = pipeline._parse_brief(_payload("A", "B"), WEEK)
    assert brief is not None
    assert brief.week_start == WEEK
    assert [t.title for t in brief.themes] == ["A", "B"]


def test_brief_survives_markdown_fences() -> None:
    fenced = f"```json\n{_payload('A')}\n```"
    assert pipeline._parse_brief(fenced, WEEK) is not None


def test_bare_list_is_accepted_as_themes() -> None:
    brief = pipeline._parse_brief(json.dumps([_theme("A")]), WEEK)
    assert brief is not None and brief.themes[0].title == "A"


def test_prose_is_rejected() -> None:
    assert pipeline._parse_brief("Here are some ideas: ...", WEEK) is None


def test_theme_missing_a_required_field_is_rejected() -> None:
    bad = _theme()
    del bad["source_url"]  # every theme must cite a source
    assert pipeline._parse_brief(json.dumps({"themes": [bad]}), WEEK) is None


def test_non_object_json_is_rejected() -> None:
    assert pipeline._parse_brief("42", WEEK) is None


# ---- the metered research step ---------------------------------------------------


def _run(text: str, tokens: tuple[int, int]) -> pipeline._AgentRun:
    return pipeline._AgentRun(text, tokens[0], tokens[1])


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Queue agent runs; `_research` is called unmetered (no DB) via __wrapped__."""
    state: dict[str, Any] = {"queue": [], "sessions": []}

    async def fake_run_agent(_agent: Any, _message: str, session_id: str) -> pipeline._AgentRun:
        state["sessions"].append(session_id)
        return state["queue"].pop(0)

    monkeypatch.setattr(pipeline, "_run_agent", fake_run_agent)
    monkeypatch.setattr(pipeline, "build_researcher", lambda: object())
    return state


async def _research_unmetered(**kwargs: Any) -> pipeline._ResearchResult:
    req = pipeline._ResearchRequest(trigger="cron", week_start=WEEK, **kwargs)
    return await pipeline._research.__wrapped__(req)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_good_brief_costs_one_call_and_is_metered_from_real_tokens(
    runs: dict[str, Any],
) -> None:
    runs["queue"] = [_run(_payload("A"), (1000, 500))]
    result = await _research_unmetered()

    assert result.brief is not None and len(runs["queue"]) == 0
    assert len(runs["sessions"]) == 1
    from app.genai_client import MODEL_FLASH
    from app.meter import pricing

    assert result.cost_eur == pricing.text_cost(MODEL_FLASH, 1000, 500)
    assert result.cost_eur > Decimal(0)


@pytest.mark.asyncio
async def test_malformed_brief_is_repaired_once_and_both_calls_are_billed(
    runs: dict[str, Any],
) -> None:
    runs["queue"] = [_run("not json at all", (900, 100)), _run(_payload("Fixed"), (1100, 400))]
    result = await _research_unmetered()

    assert result.brief is not None and result.brief.themes[0].title == "Fixed"
    assert result.raw == _payload("Fixed")  # the repaired text is what flows on
    first, second = runs["sessions"]
    assert first.endswith("-r") and second.endswith("-r2")  # distinct ADK sessions
    from app.genai_client import MODEL_FLASH
    from app.meter import pricing

    assert result.cost_eur == pricing.text_cost(MODEL_FLASH, 2000, 500)  # summed


@pytest.mark.asyncio
async def test_still_invalid_after_repair_degrades_instead_of_failing_the_week(
    runs: dict[str, Any],
) -> None:
    runs["queue"] = [_run("nope", (10, 10)), _run("still nope", (10, 10))]
    result = await _research_unmetered()

    assert result.brief is None  # loudly logged, but...
    assert result.raw == "nope"  # ...the week still gets themes text to work from


# ---- the source survives into the post -------------------------------------------


def _spec(theme: str | None) -> PostSpec:
    return PostSpec(
        pillar="Natural Eating",
        type="image",
        scene_prompt="The Blue Fit mascot in a kitchen",
        takeaway=PostTakeaway(action="Neem de trap", dose="1 keer per dag",
                              payoff="Je benen worden sterker"),
        caption_template="question",
        caption="Neem vandaag de trap.",
        references_used=PostReferences(theme=theme, value="The 80% rule"),
    )


def test_reasoning_blob_records_the_theme_source_url() -> None:
    sources = {"Hara hachi bu": "https://example.nl/80"}
    blob = pipeline._reasoning_blob(
        _spec("Hara hachi bu"), [], [], "img", "https://r2/base.jpg", sources
    )
    assert blob["theme_source_url"] == "https://example.nl/80"


def test_reasoning_blob_source_is_none_for_an_unresearched_theme() -> None:
    blob = pipeline._reasoning_blob(
        _spec("Something the generator invented"), [], [], "img", "https://r2/b.jpg", {}
    )
    assert blob["theme_source_url"] is None
    # and a post with no theme at all must not blow up
    assert pipeline._reasoning_blob(_spec(None), [], [], "img", "u", None)["theme_source_url"] is None
