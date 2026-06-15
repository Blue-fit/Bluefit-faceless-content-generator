from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest

from app import meter as meter_mod
from app.meter import MeteredResult, MeterRequest, SpendCapExceeded, meter


class _Req(MeterRequest):
    pass


class _Res(MeteredResult):
    pass


class _FakePool:
    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[object]:
        yield object()  # conn is unused — the repo functions are mocked


@pytest.fixture
def recorded_usage(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch the DB boundary; capture what would be written to `usage`."""
    captured: dict[str, Any] = {}
    monkeypatch.setattr(meter_mod, "get_pool", lambda: _FakePool())

    async def fake_insert(conn: object, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(meter_mod, "insert_usage", fake_insert)
    return captured


def _set_spend(monkeypatch: pytest.MonkeyPatch, amount: str) -> None:
    async def fake_spend(conn: object, month_start: object) -> Decimal:
        return Decimal(amount)

    monkeypatch.setattr(meter_mod, "get_monthly_spend", fake_spend)


@pytest.mark.asyncio
async def test_records_usage_when_green(
    recorded_usage: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_spend(monkeypatch, "0")

    @meter("image")
    async def tool(req: _Req) -> _Res:
        return _Res(model="m", cost_eur=Decimal("0.039"))

    res = await tool(_Req(trigger="cron"))

    assert res.cost_eur == Decimal("0.039")
    assert recorded_usage["model"] == "m"
    assert recorded_usage["call_type"] == "image"
    assert recorded_usage["cost_eur"] == Decimal("0.039")
    assert recorded_usage["trigger"] == "cron"


@pytest.mark.asyncio
async def test_blocks_and_skips_usage_on_red(
    recorded_usage: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_spend(monkeypatch, "100")  # over the default 50 EUR cap

    @meter("image")
    async def tool(req: _Req) -> _Res:
        return _Res(model="m", cost_eur=Decimal("0.039"))

    with pytest.raises(SpendCapExceeded):
        await tool(_Req(trigger="cron"))

    assert recorded_usage == {}  # nothing written when blocked
