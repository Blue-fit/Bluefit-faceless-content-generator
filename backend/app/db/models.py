"""Pydantic models mirroring database rows.

These are read models: they represent data coming out of the DB.
Write operations use explicit keyword arguments in each repository function.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class Week(BaseModel):
    id: UUID
    week_start: date
    trend_brief: dict | None
    status: str
    created_at: datetime


class Post(BaseModel):
    id: UUID
    week_id: UUID
    type: str
    pillar: str
    current_version_id: UUID | None
    created_at: datetime


class PostVersion(BaseModel):
    id: UUID
    post_id: UUID
    parent_version_id: UUID | None
    version_number: int
    asset_url: str | None
    caption: str | None
    edit_instruction: str | None
    reasoning_blob: dict | None
    reasoning_embedding: list[float] | None
    created_at: datetime


class UsageRecord(BaseModel):
    id: UUID
    model: str
    call_type: str
    cost_eur: Decimal
    trigger: str
    post_id: UUID | None
    created_at: datetime


class Message(BaseModel):
    id: UUID
    post_id: UUID
    role: str
    content: str
    created_at: datetime


class Rule(BaseModel):
    id: UUID
    text: str
    confidence: float
    status: str
    source_week_id: UUID | None
    created_at: datetime
    updated_at: datetime


class BrandChunk(BaseModel):
    id: UUID
    content: str
    embedding: list[float] | None
    source: str
    created_at: datetime


class StrategicBrief(BaseModel):
    id: UUID
    month: date
    content: str
    created_at: datetime
