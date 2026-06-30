"""POST /auth/login — simple username/password login.

Credentials come from the environment (auth_username / auth_password), set by the
operator and never stored in code. On success the client receives the bearer
token used for every other endpoint — so the token is no longer baked into the
frontend bundle; you must log in to obtain it.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(body: LoginRequest) -> dict[str, str]:
    s = get_settings()
    expected_user = s.auth_username
    expected_pass = s.auth_password.get_secret_value()
    # Constant-time compares to avoid leaking length/content via timing.
    user_ok = hmac.compare_digest(body.username, expected_user)
    pass_ok = hmac.compare_digest(body.password, expected_pass)
    # Reject if login isn't configured (empty creds) or either check fails.
    if not (expected_user and expected_pass and user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return {"token": s.auth_bearer_token.get_secret_value()}