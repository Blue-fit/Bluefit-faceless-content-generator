"""Cost metering — the @meter decorator and its request/result contracts.

Every paid tool MUST be wrapped with @meter (CLAUDE.md). The decorator:
1. checks the spend gate before the call (raises SpendCapExceeded on red),
2. runs the tool,
3. records the actual cost to the append-only `usage` table.

Tools take a `MeterRequest` subclass (carries `trigger` + `post_id`) and return
a `MeteredResult` subclass (carries `model` + `cost_eur`), so the decorator can
gate and record generically while staying type-safe.

(The ADK `before/after_tool_callback` glue in `callbacks.py` is the agent-invoked
path for the editor — Phase 2. The weekly pipeline dispatches tools directly and
uses this decorator.)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from typing import Literal, TypeVar
from uuid import UUID

import structlog
from pydantic import BaseModel

from app.db.connection import get_pool
from app.db.repositories.usage import get_monthly_spend, insert_usage
from app.meter import gate
from app.meter.gate import GateState

logger = structlog.get_logger(__name__)

# Mirror the CHECK constraints on the `usage` table (migration 001).
Trigger = Literal["cron", "edit", "explain", "ingest"]
CallType = Literal[
    "image", "video", "caption", "edit", "research", "explain", "embedding", "extraction"
]

# PRD D4 default. TODO: source the cap from brand/profile.yaml (hard_cap_eur).
DEFAULT_MONTHLY_CAP_EUR = Decimal("50")


class SpendCapExceeded(RuntimeError):
    """Raised when the monthly cap is already reached before a paid call."""

    def __init__(self, call_type: str, spend: Decimal, cap: Decimal) -> None:
        super().__init__(
            f"Spend cap reached ({spend}/{cap} EUR) before a '{call_type}' call"
        )
        self.call_type = call_type
        self.spend = spend
        self.cap = cap


class MeterRequest(BaseModel):
    """Base input for every paid tool — carries usage attribution."""

    trigger: Trigger
    post_id: UUID | None = None


class MeteredResult(BaseModel):
    """Base output for every paid tool — carries the realized cost."""

    model: str
    cost_eur: Decimal


ReqT = TypeVar("ReqT", bound=MeterRequest)
ResT = TypeVar("ResT", bound=MeteredResult)


def get_monthly_cap() -> Decimal:
    """Current monthly spend cap (EUR)."""
    # TODO: read from brand/profile.yaml once profile loading lands.
    return DEFAULT_MONTHLY_CAP_EUR


def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def meter(
    call_type: CallType,
) -> Callable[[Callable[[ReqT], Awaitable[ResT]]], Callable[[ReqT], Awaitable[ResT]]]:
    """Wrap a paid tool: gate on spend before, record usage after."""

    def decorator(
        fn: Callable[[ReqT], Awaitable[ResT]],
    ) -> Callable[[ReqT], Awaitable[ResT]]:
        @wraps(fn)
        async def wrapper(req: ReqT) -> ResT:
            cap = get_monthly_cap()
            pool = get_pool()
            async with pool.acquire() as conn:
                spend = await get_monthly_spend(conn, _month_start())

            state = gate.evaluate(spend, cap)
            if state is GateState.RED:
                raise SpendCapExceeded(call_type, spend, cap)
            if state is GateState.AMBER:
                logger.warning(
                    "meter.amber", call_type=call_type, spend=str(spend), cap=str(cap)
                )

            result = await fn(req)

            async with pool.acquire() as conn:
                await insert_usage(
                    conn,
                    model=result.model,
                    call_type=call_type,
                    cost_eur=result.cost_eur,
                    trigger=req.trigger,
                    post_id=req.post_id,
                )
            return result

        return wrapper

    return decorator
