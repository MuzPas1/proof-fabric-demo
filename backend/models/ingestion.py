"""Inbound Event Ingestion — data models (additive; independent module).

The ingestion framework accepts arbitrary external business events, normalizes
them into a single ``CommonEvent`` model, and feeds that into the EXISTING Proof
Artifact generation pipeline without modifying the core proof engine.

Security/privacy: credentials are never returned after creation. Sensitive
fields (``hmac_secret``/``token_hash``) are stripped by ``IntegrationConfig.public()``.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
AUTH_PROVIDERS = {
    "none", "hmac", "hmac_sha256", "hmac_sha1", "api_key", "bearer",
    "basic", "jwt", "oauth2", "mtls", "custom",
}
# Providers for which PFP mints a shared secret/token (others are externally configured)
CREDENTIAL_PROVIDERS = {"hmac", "hmac_sha256", "hmac_sha1", "api_key", "bearer", "basic"}
ADAPTERS = {"generic"}


# ---------------------------------------------------------------------------
# Common normalized event model (the single internal shape)
# ---------------------------------------------------------------------------
class CommonEvent(BaseModel):
    """Vendor-neutral normalized event. Any adapter must produce this shape."""
    event_type: str = Field(..., min_length=1, max_length=128)
    external_id: str = Field(..., min_length=1, max_length=256)
    occurred_at: str = Field(..., description="ISO-8601 UTC timestamp")
    source: Optional[str] = Field(None, max_length=128)
    actor: Optional[str] = Field(None, max_length=256, description="Originating subject/system (tokenized before signing)")
    subject: Optional[str] = Field(None, max_length=256, description="Affected subject (tokenized before signing)")
    amount: int = Field(0, ge=0, description="Optional quantity in smallest unit; 0 for non-financial events")
    currency: str = Field("USD", min_length=3, max_length=3)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(None, max_length=256)

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


# ---------------------------------------------------------------------------
# Integration configuration (persisted document)
# ---------------------------------------------------------------------------
class IntegrationConfig(BaseModel):
    """A configured inbound integration (adapter + auth provider + mapping)."""
    integration_id: str
    slug: str
    name: str
    description: Optional[str] = None
    tenant_id: str = "default"
    adapter: str = "generic"
    auth_provider: str = "hmac"
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    default_currency: str = "USD"
    field_map: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    status: str = "active"
    # --- cross-cutting inbound controls ---
    require_timestamp: bool = False
    timestamp_tolerance_seconds: int = 300
    replay_protection: bool = False
    # --- credentials (sensitive; never serialized to clients) ---
    hmac_secret: Optional[str] = None
    token_hash: Optional[str] = None
    basic_password_hash: Optional[str] = None
    external_secret: Optional[str] = None  # externally-provided (JWT HS / OAuth client secret)
    signature_header: str = "x-pfp-signature"
    token_header: str = "x-integration-key"
    # --- monitoring counters ---
    total_received: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    last_event_at: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: Optional[str] = None
    updated_at: Optional[str] = None

    def public(self) -> dict:
        """Redacted view safe for API responses (no secrets)."""
        d = self.model_dump()
        for secret in ("hmac_secret", "token_hash", "basic_password_hash", "external_secret"):
            d.pop(secret, None)
        # redact any sensitive keys that may have been placed in auth_config
        cfg = dict(d.get("auth_config") or {})
        for k in list(cfg.keys()):
            if any(s in k.lower() for s in ("secret", "password", "private", "key")) and k != "public_key":
                cfg[k] = "***redacted***"
        d["auth_config"] = cfg
        d["auth_configured"] = bool(
            self.hmac_secret or self.token_hash or self.basic_password_hash
            or self.external_secret or self.auth_config
        ) or self.auth_provider in ("none", "mtls")
        return d


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class CreateIntegrationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., min_length=2, max_length=63)
    description: Optional[str] = Field(None, max_length=512)
    adapter: str = "generic"
    auth_provider: str = "hmac"
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    default_currency: str = Field("USD", min_length=3, max_length=3)
    field_map: Dict[str, str] = Field(default_factory=dict)
    tenant_id: Optional[str] = None
    require_timestamp: bool = False
    timestamp_tolerance_seconds: int = Field(300, ge=1, le=86400)
    replay_protection: bool = False
    secret: Optional[str] = Field(None, description="Externally-provided secret for jwt(HS)/oauth2 introspection")

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not SLUG_RE.match(v):
            raise ValueError("slug must be 2-63 chars, lowercase alphanumeric and hyphens")
        return v

    @field_validator("adapter")
    @classmethod
    def _adapter(cls, v: str) -> str:
        if v not in ADAPTERS:
            raise ValueError(f"adapter must be one of {sorted(ADAPTERS)}")
        return v

    @field_validator("auth_provider")
    @classmethod
    def _auth(cls, v: str) -> str:
        if v not in AUTH_PROVIDERS:
            raise ValueError(f"auth_provider must be one of {sorted(AUTH_PROVIDERS)}")
        return v


class UpdateIntegrationRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=512)
    adapter: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    default_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    field_map: Optional[Dict[str, str]] = None
    require_timestamp: Optional[bool] = None
    timestamp_tolerance_seconds: Optional[int] = Field(None, ge=1, le=86400)
    replay_protection: Optional[bool] = None
    secret: Optional[str] = None

    @field_validator("adapter")
    @classmethod
    def _adapter(cls, v):
        if v is not None and v not in ADAPTERS:
            raise ValueError(f"adapter must be one of {sorted(ADAPTERS)}")
        return v


class TestIntegrationRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    issue: bool = Field(False, description="If true, actually issue a Proof Artifact; otherwise dry-run preview only")


class IngestResponse(BaseModel):
    status: str
    integration: str
    event_id: str
    fea_id: Optional[str] = None
    accepted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
