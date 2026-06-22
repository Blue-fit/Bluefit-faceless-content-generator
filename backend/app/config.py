"""Application configuration.

Single source of truth for credentials and per-deployment connection settings.
Everything loads from the environment (via ``backend/.env`` in development);
never hard-code keys elsewhere. See ``.env.example`` for the full list and
``CLAUDE.md`` for the "Google, R2, Resend" external-service boundary.
"""

from decimal import Decimal
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed deployment configuration loaded from the environment.

    Required fields have no defaults: a missing credential fails loudly at
    startup rather than surfacing as a confusing runtime error later.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Google Gemini (Developer API) ---
    google_api_key: SecretStr
    google_genai_use_vertexai: bool = False

    # --- Cloudflare R2 (S3-compatible) ---
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: SecretStr
    r2_bucket: str
    r2_endpoint_url: str
    r2_public_url: str

    # --- Resend (email) ---
    resend_api_key: SecretStr
    email_from: str
    client_email: str
    operator_email: str

    # --- Postgres (asyncpg DSN) ---
    database_url: str

    # --- App auth ---
    auth_bearer_token: SecretStr

    # --- Cost governance ---
    spend_cap_eur: Decimal = Decimal("100.00")


@lru_cache
def get_settings() -> Settings:
    """Return a process-cached ``Settings`` instance.

    Cached so the ``.env`` file and environment are parsed once per process.
    """
    return Settings()  # type: ignore[call-arg]  # fields populated from env
