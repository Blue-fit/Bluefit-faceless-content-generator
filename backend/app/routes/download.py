"""GET /download — proxies an R2 asset to the client as a file download."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

router = APIRouter()

_ALLOWED_HOST = "r2.dev"


@router.get("/download")
async def download(url: str = Query(...), pillar: str = Query(default="bluefit-post")) -> StreamingResponse:
    if _ALLOWED_HOST not in url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL.")

    ext = url.split(".")[-1].lower()
    content_type = "video/mp4" if ext == "mp4" else "image/jpeg"
    filename = f"{pillar}.{ext}"

    async def stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url) as r:
                async for chunk in r.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
