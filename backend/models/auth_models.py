"""Auth & control-plane data models."""
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Tenant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tenant_id: str
    name: str
    status: str = "active"  # active | suspended
    created_at: str = Field(default_factory=_now_iso)


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    password_hash: str
    role: str = "read_only"
    tenant_id: str
    status: str = "active"
    created_at: str = Field(default_factory=_now_iso)


class ApiKeyRecord(BaseModel):
    """Persistent API key. The raw secret is shown once at creation; only the
    SHA-256 hash is stored."""
    model_config = ConfigDict(extra="ignore")
    key_id: str
    key_hash: str
    name: str
    tenant_id: str
    customer_id: Optional[str] = None
    scopes: List[str] = Field(default_factory=lambda: ["fea:write", "fea:read", "fea:verify", "webhooks:manage"])
    status: str = "active"  # active | revoked
    prefix: str = ""        # first chars of the raw key for display
    created_at: str = Field(default_factory=_now_iso)
    created_by: Optional[str] = None
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None


class WebhookSubscription(BaseModel):
    model_config = ConfigDict(extra="ignore")
    webhook_id: str
    tenant_id: str
    url: str
    events: List[str] = Field(default_factory=lambda: ["fea.generated"])
    secret: str = ""  # HMAC signing secret for delivery
    status: str = "active"
    created_at: str = Field(default_factory=_now_iso)


class AuditEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    audit_id: str
    action: str
    actor: str            # user email / api-key id / "system"
    tenant_id: str
    target: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    prev_hash: str = ""   # hash chain for tamper-evidence
    entry_hash: str = ""
    created_at: str = Field(default_factory=_now_iso)


# --- Request / response DTOs ---
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: str
    email: str


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    tenant_id: Optional[str] = None
    customer_id: Optional[str] = None
    scopes: Optional[List[str]] = None
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


class CreateApiKeyResponse(BaseModel):
    key_id: str
    api_key: str  # raw key, shown ONCE
    name: str
    tenant_id: str
    scopes: List[str]
    expires_at: Optional[str] = None


class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    tenant_id: Optional[str] = None
