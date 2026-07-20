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

    # --- Crypto agility / federation / BYOS feature flags (default OFF) ---
    # When OFF, only Ed25519 + FEA v1.1 issuance is active (existing behaviour).
    ENABLE_CRYPTO_SUITES: bool = os.environ.get("ENABLE_CRYPTO_SUITES", "false").lower() == "true"
    ENABLE_FEDERATED_KEYS: bool = os.environ.get("ENABLE_FEDERATED_KEYS", "false").lower() == "true"
    ENABLE_BYOS: bool = os.environ.get("ENABLE_BYOS", "false").lower() == "true"
    DEFAULT_SIGNATURE_SUITE: str = os.environ.get("DEFAULT_SIGNATURE_SUITE", "Ed25519")

    # --- Trust Layer 2: Independent Time Attestation (default OFF; additive) ---
    ENABLE_TIME_ANCHOR: bool = os.environ.get("ENABLE_TIME_ANCHOR", "false").lower() == "true"
    TIME_ANCHOR_PROVIDER: str = os.environ.get("TIME_ANCHOR_PROVIDER", "local").lower()
    TSA_URL: str = os.environ.get("TSA_URL", "")
    # Pinned RFC-3161 TSA trust anchors (PEM: root [+ intermediates]) as an inline
    # PEM string or a file path. When set, the rfc3161 provider verifies the TST
    # signing certificate chains to these roots -> chain_verified=true.
    TSA_ROOT_BUNDLE: str = os.environ.get("TSA_ROOT_BUNDLE", "")
    TIME_ANCHOR_LOCAL_SEED: str = os.environ.get("TIME_ANCHOR_LOCAL_SEED", "")

    # --- Trust Layer 2: AI Provenance & Accountability (default OFF; additive) ---
    ENABLE_AI_PROVENANCE: bool = os.environ.get("ENABLE_AI_PROVENANCE", "false").lower() == "true"

    # --- Inbound Event Ingestion framework (default OFF; additive module) ---
    ENABLE_EVENT_INGESTION: bool = os.environ.get("ENABLE_EVENT_INGESTION", "false").lower() == "true"

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
