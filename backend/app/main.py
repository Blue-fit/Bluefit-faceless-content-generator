from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db.connection import close_pool, create_pool
from app.routes.chat import router as chat_router
from app.routes.download import router as download_router
from app.routes.explain import router as explain_router
from app.routes.health import router as health_router
from app.routes.posts import router as posts_router
from app.routes.usage import router as usage_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    await create_pool()
    yield
    await close_pool()


app = FastAPI(title="Content Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_origin_regex=r"https://bluefit-faceless-content-generator.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(posts_router)
app.include_router(chat_router)
app.include_router(usage_router)
app.include_router(download_router)
app.include_router(explain_router)

_ASSETS = Path(__file__).resolve().parent.parent.parent / "scripts" / "out" / "pipeline"
_ASSETS.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=_ASSETS), name="assets")
