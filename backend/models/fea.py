"""Proof Artifact data models (stored under the `fea` / `fea_id` contract names)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid


class TransactionSummary(BaseModel):
    """Transaction summary within FEA structure."""
    transaction_id: str
    timestamp: str
    amount: int
    currency: str


class Parties(BaseModel):
    """Party information within FEA structure."""
    payer_hash: str
    payee_hash: str


class FEAPayload(BaseModel):
    """
    The canonical Proof Artifact payload - THIS IS WHAT GETS SIGNED.
    
    Contains ONLY the signed data, no signature metadata.
    """
    fea_version: str = "1.0"
    issuer_id: str
    public_key_id: str
    transaction_summary: TransactionSummary
    parties: Parties
    metadata_hash: Optional[str] = None
    fea_hash: str = ""


class GenerateFEARequest(BaseModel):
    """Input for Proof Artifact generation - POST /api/fea/generate."""
    idempotency_key: str = Field(..., min_length=1)
    transaction_id: str = Field(..., min_length=1)
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    amount: int = Field(..., ge=0, description="Amount/quantity in smallest unit (e.g., cents)")
    currency: str = Field(..., min_length=3, max_length=3)
    payer_id: str = Field(..., description="Hashed/tokenized payer identifier")
    payee_id: str = Field(..., description="Hashed/tokenized payee identifier")
    metadata: Optional[Dict[str, Any]] = None
    signature_suite: Optional[str] = Field(
        None,
        description="Signature suite: Ed25519 (default) | ES256 (secp256r1) | ES256K (secp256k1). "
                    "Requires the crypto-agility feature to be enabled.",
    )


class FEAResponse(BaseModel):
    """
    Response from Proof Artifact generation.
    
    Structure separates:
    - fea_payload: the signed data
    - signature: cryptographic signature
    - signature_version: signature metadata (NOT signed)
    - created_at: response metadata (NOT signed)
    """
    model_config = ConfigDict(extra="ignore")
    
    fea_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fea_payload: Dict[str, Any]  # The signed data
    signature: str  # Pure base64 Ed25519 signature
    signature_version: str = "v2"  # Signature metadata (NOT part of signed data)
    public_key_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VerifyFEARequest(BaseModel):
    """
    Input for Proof Artifact verification - POST /api/fea/verify.
    
    Supports both:
    - New format: fea_payload + signature + signature_version (external)
    - Legacy format: fea_payload with signature_version inside + signature
    """
    fea_payload: Dict[str, Any]
    signature: str
    signature_version: Optional[str] = None  # External version (new format)


class VerifyFEAResponse(BaseModel):
    """Response from Proof Artifact verification."""
    valid: bool
    reason: Optional[str] = None
    signature_version: str = "unknown"
    verified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PublicVerifyResponse(BaseModel):
    """Response from public verification - GET /public/verify/{fea_id}."""
    fea_id: str
    fea_payload: Dict[str, Any]
    signature: str
    signature_version: str
    signature_valid: bool
    issuer_id: str
    created_at: str
    time_attestation: Optional[Dict[str, Any]] = None  # present only when a time anchor exists
    ai_provenance: Optional[Dict[str, Any]] = None  # present only when an AI provenance envelope exists (Trust Layer 2)
    event_descriptor: Optional[Dict[str, Any]] = None  # non-sensitive provider-aware descriptor (generic ingestion / identity)


class FEADocument(BaseModel):
    """MongoDB document for Proof Artifact storage."""
    model_config = ConfigDict(extra="ignore")
    
    fea_id: str
    idempotency_key: str
    tenant_id: str = "default"
    canonical_payload_hash: str
    transaction_payload_hash: str = ""  # Hash of transaction data only (for replay protection)
    fea_payload: Dict[str, Any]  # Only the signed payload
    signature: str
    signature_version: str
    public_key_id: str
    created_at: str
    time_anchor: Optional[Dict[str, Any]] = None  # detached time-attestation envelope (Trust Layer 2)
    ai_provenance: Optional[Dict[str, Any]] = None  # detached AI provenance & accountability envelope (Trust Layer 2)
