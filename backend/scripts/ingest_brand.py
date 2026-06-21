"""Ingest the Blue Fit brand requirements doc into `brand_chunks` (RAG phase A).

Usage (from the backend/ directory):

    uv run python scripts/ingest_brand.py --dry-run   # chunk + print only, no DB/API
    uv run python scripts/ingest_brand.py             # embed + store (paid, needs DB)

Reads the requirements doc, splits it into heading-aware chunks, embeds them in
one batch (metered), and replaces the contents of `brand_chunks`. Idempotent:
re-run it whenever the brand doc changes. Run once per deployment / doc edit.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.db.connection import close_pool, create_pool, get_pool
from app.db.repositories.brand_chunks import (
    count_chunks,
    delete_all_chunks,
    insert_chunk,
)
from app.genai_client import MODEL_EMBED, embed_texts
from app.meter import MeteredResult, MeterRequest, meter
from app.meter import pricing

DOC = (
    Path(__file__).resolve().parents[2]
    / "context"
    / "Faceless content Blue fit- Requirements.md"
)
SOURCE = "requirements.md"
_MAX_CHARS = 1500  # target upper bound per chunk; small sections pack together

_HEADING = re.compile(r"^#{1,6}\s")


# ---- ② chunking: pure, no DB/API, unit-testable -----------------------------


def _split_sections(text: str) -> list[str]:
    """Split markdown into sections, each starting at a heading line."""
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if _HEADING.match(line) and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return [s for s in sections if s]


def _split_large(section: str, max_chars: int) -> list[str]:
    """Split one oversized section into paragraph-packed pieces."""
    out: list[str] = []
    buf = ""
    for para in (p for p in section.split("\n\n") if p.strip()):
        if buf and len(buf) + 2 + len(para) > max_chars:
            out.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}".strip()
    if buf:
        out.append(buf)
    return out


def chunk_markdown(text: str, max_chars: int = _MAX_CHARS) -> list[str]:
    """Heading-aware chunks: pack small sections together, split big ones.

    Each chunk stays a coherent unit (a pillar, a post example) so retrieval
    lands on the right brand rule rather than a random slice.
    """
    chunks: list[str] = []
    buf = ""
    for section in _split_sections(text):
        if len(section) > max_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_large(section, max_chars))
        elif buf and len(buf) + 2 + len(section) > max_chars:
            chunks.append(buf)
            buf = section
        else:
            buf = f"{buf}\n\n{section}".strip()
    if buf:
        chunks.append(buf)
    return chunks


# ---- ③ metered embedding ----------------------------------------------------


class _EmbedBatchRequest(MeterRequest):
    texts: list[str]


class _EmbedBatchResult(MeteredResult):
    vectors: list[list[float]]


@meter("embedding")
async def _embed_batch(req: _EmbedBatchRequest) -> _EmbedBatchResult:
    """Embed all chunks in one batch and report the cost to `usage`."""
    vectors = await embed_texts(req.texts)
    # Pricing is per input token; estimate ~4 chars/token (prices are placeholders
    # in pricing.py anyway, and verify_pricing.py catches real drift).
    tokens = sum(len(t) for t in req.texts) // 4
    return _EmbedBatchResult(
        model=MODEL_EMBED,
        cost_eur=pricing.embedding_cost(MODEL_EMBED, tokens),
        vectors=vectors,
    )


# ---- main -------------------------------------------------------------------


async def main() -> None:
    dry_run = "--dry-run" in sys.argv
    if not DOC.exists():
        raise SystemExit(f"Brand doc not found: {DOC}")

    chunks = chunk_markdown(DOC.read_text(encoding="utf-8"))
    print(f"Chunked {DOC.name} -> {len(chunks)} chunks "
          f"(sizes: {[len(c) for c in chunks]})")

    if dry_run:
        for i, c in enumerate(chunks, 1):
            head = c.splitlines()[0][:70]
            print(f"  [{i:2}] {len(c):4} chars | {head}")
        print("\nDry run: nothing embedded or written.")
        return

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY not found — create backend/.env first.")

    await create_pool()
    try:
        print(f"Embedding {len(chunks)} chunks (one batch) ...")
        result = await _embed_batch(_EmbedBatchRequest(texts=chunks, trigger="ingest"))
        async with get_pool().acquire() as conn, conn.transaction():
            await delete_all_chunks(conn)
            for content, vector in zip(chunks, result.vectors, strict=True):
                await insert_chunk(conn, content=content, embedding=vector, source=SOURCE)
            total = await count_chunks(conn)
        print(f"Stored {total} chunks in brand_chunks. Cost: EUR {result.cost_eur}")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
