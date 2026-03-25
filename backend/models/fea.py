"""FEA (Financial Evidence Artifact) data models."""
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


class FEAStructure(BaseModel):
    """The canonical FEA structure - Section 3 of spec."""
    fea_version: str = "1.0"
    issuer_id: str
    public_key_id: str
    transaction_summary: TransactionSummary
    parties: Parties
    metadata_hash: Optional[str] = None
    fea_hash: str = ""


class GenerateFEARequest(BaseModel):
    """Input for FEA generation - POST /generate-fea."""
    idempotency_key: str = Field(..., min_length=1)
    transaction_id: str = Field(..., min_length=1)
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    amount: int = Field(..., ge=0, description="Amount in smallest unit (e.g., paise)")
    currency: str = Field(..., min_length=3, max_length=3)
    payer_id: str = Field(..., description="Hashed/tokenized payer identifier")
    payee_id: str = Field(..., description="Hashed/tokenized payee identifier")
    metadata: Optional[Dict[str, Any]] = None


class FEAResponse(BaseModel):
    """Response from FEA generation."""
    model_config = ConfigDict(extra="ignore")
    
    fea_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fea_hash: str
    signature: str
    public_key_id: str
    fea_payload: Dict[str, Any]
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VerifyFEARequest(BaseModel):
    """Input for FEA verification - POST /verify-fea."""
    fea_payload: Dict[str, Any]
    signature: str


class VerifyFEAResponse(BaseModel):
    """Response from FEA verification."""
    valid: bool
    reason: Optional[str] = None
    verified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PublicVerifyResponse(BaseModel):
    """Response from public verification - GET /public/verify/{fea_id}."""
    fea_hash: str
    signature_valid: bool
    timestamp: str
    issuer_id: str


class FEADocument(BaseModel):
    """MongoDB document for FEA storage."""
    model_config = ConfigDict(extra="ignore")
    
    fea_id: str
    idempotency_key: str
    canonical_payload_hash: str
    fea_hash: str
    signature: str
    public_key_id: str
    created_at: str
    fea_payload: Dict[str, Any]
