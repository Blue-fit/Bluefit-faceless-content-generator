"""Grounding-redirect resolution and generator metering in the weekly pipeline."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.agents import pipeline
from app.agents.schemas import TrendBrief, TrendTheme
from app.genai_client import MODEL_PRO
from app.meter import pricing

WEEK = date(2026, 9, 25)
REDIRECT = f"https://{pipeline._GROUNDING_HOST}/grounding-api-redirect/AbC123"
REAL = "https://www.brownhealth.org/be-well/winter"


def _brief(*urls: str) -> TrendBrief:
    return TrendBrief(
        week_start=WEEK,
        themes=[
            TrendTheme(title=f"T{i}", summary="s", why_relevant="w", source_url=u)
            for i, u in enumerate(urls)
        ],
    )


class _FakeResponse:
    def __init__(self, url: str) -> None:
        self.url = url


class _FakeClient:
    """Stands in for httpx.AsyncClient(follow_redirects=True)."""

    def __init__(self, final: str | Exception) -> None:
        self.final = final
        self.calls: list[str] = []

    async def get(self, url: str) -> _FakeResponse:
        self.calls.append(url)
        if isinstance(self.final, Exception):
            raise self.final
        return _FakeResponse(self.final)


# ---- single-URL resolution -------------------------------------------------------


@pytest.mark.asyncio
async def test_redirect_resolves_to_the_real_article() -> None:
    client = _FakeClient(REAL)
    assert await pipeline._resolve_source(client, REDIRECT) == REAL  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_network_failure_keeps_the_original_url() -> None:
    client = _FakeClient(httpx.ConnectError("boom"))
    assert await pipeline._resolve_source(client, REDIRECT) == REDIRECT  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_unresolved_redirect_is_not_stored_as_the_answer() -> None:
    """If we land back on the grounding host, keep the original rather than a dud."""
    client = _FakeClient(f"https://{pipeline._GROUNDING_HOST}/still-here")
    assert await pipeline._resolve_source(client, REDIRECT) == REDIRECT  # type: ignore[arg-type]


# ---- brief-level resolution ------------------------------------------------------


@pytest.mark.asyncio
async def test_only_grounding_urls_are_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def fake_resolve(_client: Any, url: str) -> str:
        seen.append(url)
        return REAL

    monkeypatch.setattr(pipeline, "_resolve_source", fake_resolve)
    out = await pipeline._resolve_sources(_brief(REDIRECT, "https://already.real/x"))

    assert seen == [REDIRECT]  # the already-real URL is left alone
    assert [t.source_url for t in out.themes] == [REAL, "https://already.real/x"]


@pytest.mark.asyncio
async def test_brief_without_redirects_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    async def explode(*_a: Any, **_k: Any) -> Any:  # pragma: no cover - must not run
        raise AssertionError("should not open a client")

    monkeypatch.setattr(pipeline.httpx, "AsyncClient", explode)
    brief = _brief("https://already.real/x")
    assert await pipeline._resolve_sources(brief) is brief


# ---- generator metering ----------------------------------------------------------


@pytest.fixture
def gen_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"run": pipeline._AgentRun("{}", 4000, 1500), "sessions": []}

    async def fake_run_agent(_agent: Any, _msg: str, session_id: str) -> pipeline._AgentRun:
        state["sessions"].append(session_id)
        return state["run"]

    monkeypatch.setattr(pipeline, "_run_agent", fake_run_agent)
    monkeypatch.setattr(pipeline, "build_generator", lambda: object())
    return state


@pytest.mark.asyncio
async def test_generate_is_priced_from_real_pro_tokens(gen_run: dict[str, Any]) -> None:
    req = pipeline._GenerateRequest(trigger="cron", message="m", session_id="wk-x-g")
    result = await pipeline._generate.__wrapped__(req)  # type: ignore[attr-defined]

    assert result.model == MODEL_PRO
    assert result.cost_eur == pricing.text_cost(MODEL_PRO, 4000, 1500) > Decimal(0)
    assert gen_run["sessions"] == ["wk-x-g"]


@pytest.mark.asyncio
async def test_guards_report_zero_cost_when_they_do_not_re_prompt(
    gen_run: dict[str, Any],
) -> None:
    """A clean week must not be billed for a correction that never happened."""
    from app.agents.schemas import GeneratorOutput, PostReferences, PostSpec

    def _post(pillar: str, value: str, type_: str = "image") -> PostSpec:
        return PostSpec(
            pillar=pillar,  # type: ignore[arg-type]
            type=type_,  # type: ignore[arg-type]
            scene_prompt="The Blue Fit mascot in a park",
            caption_template="question",
            caption="c",
            references_used=PostReferences(value=value),  # type: ignore[arg-type]
        )

    out = GeneratorOutput(
        posts=[
            _post("Community", "Belonging"),
            _post("Keep Moving", "Move naturally"),
            _post("Natural Eating", "The 80% rule", "video"),
        ]
    )
    _, value_cost = await pipeline._enforce_value_rules(out, frozenset(), "msg", WEEK)
    _, scene_cost = await pipeline._enforce_scene_variety(out, set(), "msg", WEEK)

    assert value_cost == Decimal(0) and scene_cost == Decimal(0)
    assert gen_run["sessions"] == []  # no generator call at all
