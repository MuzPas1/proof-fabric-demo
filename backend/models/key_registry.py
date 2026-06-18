"""Key registry models.

Federated trust (Phase 2) adds OPTIONAL fields to ``PublicKeyInfo`` so the
registry can hold customer/partner-owned keys (raw / JWK / PEM), with validity
windows and proof-of-possession — WITHOUT breaking legacy platform keys, which
simply omit the new fields and behave exactly as before.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal, Dict, Any


class PublicKeyInfo(BaseModel):
    """Public key information for verification."""
    model_config = ConfigDict(extra="ignore")

    public_key_id: str
    public_key: str  # Base64-encoded raw public key (Ed25519: 32B; EC: 0x04||X||Y 65B)
    algorithm: str = "Ed25519"  # Ed25519 | ES256 | ES256K
    created_at: str
    status: Literal["active", "retired", "revoked", "pending"] = "active"

    # -- Federated trust (all optional; legacy keys omit these) --------------
    key_format: Optional[str] = None          # "raw" | "jwk" | "spki-pem"
    jwk: Optional[Dict[str, Any]] = None       # original JWK (when key_format=jwk)
    tenant_id: Optional[str] = None            # owning tenant (federated keys)
    owner: Optional[str] = None                # "platform" | "customer" | "partner"
    not_before: Optional[str] = None           # ISO-8601 validity window start
    not_after: Optional[str] = None            # ISO-8601 validity window end
    pop_verified: Optional[bool] = None        # proof-of-possession confirmed
    label: Optional[str] = None                # human label for partner keys


class KeyRegistryResponse(BaseModel):
    """Response from key registry endpoint."""
    keys: list[PublicKeyInfo]
    total: int = 0
    active_count: int = 0
    retired_count: int = 0


class FederatedKeyRegisterRequest(BaseModel):
    """Register a customer/partner-owned public key (starts in `pending`)."""
    algorithm: str = Field(..., description="Ed25519 | ES256 | ES256K")
    key_format: str = Field("raw", description="raw | jwk | spki-pem")
    public_key: Optional[str] = Field(None, description="Base64 raw key OR base64 SPKI PEM, per key_format")
    jwk: Optional[Dict[str, Any]] = Field(None, description="JWK object (when key_format=jwk)")
    owner: str = Field("partner", description="customer | partner")
    label: Optional[str] = Field(None, max_length=200)
    not_before: Optional[str] = None
    not_after: Optional[str] = None


class FederatedKeyRegisterResponse(BaseModel):
    public_key_id: str
    tenant_id: str
    algorithm: str
    status: str
    pop_challenge: str = Field(..., description="Sign this (with domain prefix PFP_POP_V1::) using the private key, then call /confirm")
    pop_domain_prefix: str = "PFP_POP_V1::"
    expires_at: str


class FederatedKeyConfirmRequest(BaseModel):
    public_key_id: str
    pop_signature: str = Field(..., description="Base64 signature over (PFP_POP_V1:: + challenge)")
