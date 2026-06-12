"""Centralized configuration loaded from environment variables.

All secrets and environment-specific values come from the environment only.
Missing critical config fails fast (no silent defaults for secrets).
"""
import os
from functools import lru_cache


class Settings:
    """Application settings sourced from environment variables."""

    # --- Environment ---
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development").lower()

    # --- Database ---
    MONGO_URL: str = os.environ["MONGO_URL"]
    DB_NAME: str = os.environ["DB_NAME"]

    # --- Auth ---
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MIN: int = int(os.environ.get("ACCESS_TOKEN_TTL_MIN", "30"))
    REFRESH_TOKEN_TTL_DAYS: int = int(os.environ.get("REFRESH_TOKEN_TTL_DAYS", "7"))
    ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "admin@pfprotocol.com")
    ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "")

    # --- Multi-tenancy ---
    DEFAULT_TENANT_ID: str = os.environ.get("DEFAULT_TENANT_ID", "default")

    # --- KMS / signing ---
    KMS_PROVIDER: str = os.environ.get("KMS_PROVIDER", "local").lower()
    ISSUER_ID: str = os.environ.get("ISSUER_ID", "pfp-issuer-001")

    # --- Crypto policy ---
    ACCEPT_LEGACY_V1: bool = os.environ.get("ACCEPT_LEGACY_V1", "false").lower() == "true"
    ENFORCE_VERIFY_TIMESTAMP: bool = (
        os.environ.get("ENFORCE_VERIFY_TIMESTAMP", "false").lower() == "true"
    )

    # --- Security ---
    CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "*")
    MAX_REQUEST_BYTES: int = int(os.environ.get("MAX_REQUEST_BYTES", "1048576"))
    SANDBOX_API_KEY: str = os.environ.get("SANDBOX_API_KEY", "")

    # --- External evaluation (read-only) account ---
    EVAL_EMAIL: str = os.environ.get("EVAL_EMAIL", "")
    EVAL_PASSWORD: str = os.environ.get("EVAL_PASSWORD", "")
    EVAL_READONLY_API_KEY: str = os.environ.get("EVAL_READONLY_API_KEY", "")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT in ("production", "prod")

    @property
    def expose_sandbox_key(self) -> bool:
        """Sandbox API key is only exposed via /api/config outside production."""
        return not self.is_production and bool(self.SANDBOX_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
