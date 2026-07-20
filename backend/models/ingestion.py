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
AUTH_PROVIDERS = {"hmac", "api_key", "bearer", "none"}
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
    default_currency: str = "USD"
    field_map: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    status: str = "active"
    # --- credentials (sensitive; never serialized to clients) ---
    hmac_secret: Optional[str] = None
    token_hash: Optional[str] = None
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
        d.pop("hmac_secret", None)
        d.pop("token_hash", None)
        d["auth_configured"] = bool(self.hmac_secret or self.token_hash) or self.auth_provider == "none"
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
    default_currency: str = Field("USD", min_length=3, max_length=3)
    field_map: Dict[str, str] = Field(default_factory=dict)
    tenant_id: Optional[str] = None

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
    default_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    field_map: Optional[Dict[str, str]] = None

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
