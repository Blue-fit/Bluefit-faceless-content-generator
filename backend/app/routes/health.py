from fastapi import APIRouter

from app.db.connection import get_pool

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    await get_pool().fetchval("SELECT 1")
    return {"status": "ok"}
