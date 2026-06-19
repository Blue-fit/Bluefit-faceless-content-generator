from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.config import get_settings
from app.db.connection import get_pool
from app.db.repositories.usage import get_monthly_spend

router = APIRouter()


@router.get("/usage/current-month")
async def current_month_spend(_: None = Depends(require_auth)) -> dict:
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    async with get_pool().acquire() as conn:
        spent = await get_monthly_spend(conn, month_start)
    cap = get_settings().spend_cap_eur
    return {"spent_eur": float(spent), "cap_eur": float(cap)}
