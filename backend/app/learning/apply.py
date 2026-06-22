"""Upsert extracted rule candidates into the `rules` table (learning loop).

Insert genuinely new rules; on a recurring preference (same normalised text), bump the
existing rule's confidence instead of duplicating. Exact-text dedup is the v1 approach
(semantic dedup is a future refinement). Free: no model calls here.
"""

from __future__ import annotations

import asyncpg

from app.db.repositories.rules import (
    get_active_rules,
    insert_rule,
    update_rule_confidence,
)
from app.learning.extract import RuleCandidate


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


async def apply_candidates(
    conn: asyncpg.Connection, candidates: list[RuleCandidate]
) -> dict[str, int]:
    """Insert new rules / bump confidence on recurring ones. Returns counts."""
    existing = {_norm(r.text): r for r in await get_active_rules(conn)}
    inserted = updated = 0
    for cand in candidates:
        match = existing.get(_norm(cand.text))
        if match is None:
            await insert_rule(
                conn, text=cand.text, confidence=_clamp(cand.confidence), source_week_id=None
            )
            inserted += 1
        else:
            # Recurrence raises confidence (capped at 1.0).
            await update_rule_confidence(
                conn, match.id, _clamp(max(match.confidence, cand.confidence) + 0.1)
            )
            updated += 1
    return {"inserted": inserted, "updated": updated}
