"""Bearer token authentication dependency."""

from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

_bearer = HTTPBearer()


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> None:
    if credentials.credentials != get_settings().auth_bearer_token.get_secret_value():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
