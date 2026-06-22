"""Cloudflare R2 asset uploader (S3-compatible via boto3).

Implements the AssetUploader Protocol from app/storage/__init__.py.
Upload a binary asset and return its public URL.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

import boto3
from botocore.config import Config

from app.config import get_settings


@lru_cache
def _client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.r2_endpoint_url,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key.get_secret_value(),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


class R2Uploader:
    """Uploads assets to Cloudflare R2 and returns their public URL."""

    async def upload(self, *, data: bytes, key: str, content_type: str) -> str:
        settings = get_settings()
        await asyncio.to_thread(
            _client().put_object,
            Bucket=settings.r2_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return f"{settings.r2_public_url}/{key}"
