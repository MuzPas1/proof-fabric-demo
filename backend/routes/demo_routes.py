"""
Demo routes — Transaction Proof Flow.

Public, unauthenticated demo endpoints:
  • POST /demo/proof              — stateless normalize + canonical SHA-256 hash
  • POST /demo/issue              — issue a proof that embeds compliance state and persist it
  • GET  /demo/verify/{proof_id}  — retrieve a stored proof and re-verify its integrity
  • POST /demo/artifact           — build + sign a downloadable standalone proof artifact
  • POST /demo/artifact/verify    — independently verify an uploaded proof artifact

Crypto logic (canonicalization + hashing) is untouched; issue/verify only add
persistence + lookup on top of the existing primitives.
"""
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from typing import Union, Optional, Any, Dict
from datetime import datetime, timezone
import json

from crypto.canonicalize import canonicalize_to_json, normalize_timestamp
from crypto.hashing import compute_sha256


router = APIRouter(prefix="/demo", tags=["Demo"])


class PartyRecord(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=200)
    user_id: str = Field(..., min_length=1, max_length=200)
    amount: Union[str, float, int]
    created_at: str = Field(..., min_length=1)


class ProofMetadata(BaseModel):
    algorithm: str
    canonicalization: str
    generated_at: str


class ProofResponse(BaseModel):
    proof_hash: str
    normalized_payload: dict
    metadata: ProofMetadata


def _normalize_amount(amount: Union[str, float, int]) -> str:
    """Normalize amount to a canonical string with 2 decimal places."""
    try:
        if isinstance(amount, str):
            amount = amount.strip().replace(",", "")
            if amount == "":
                raise ValueError("empty amount")
        value = float(amount)
        return f"{value:.2f}"
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid amount: {amount!r}",
        )


def _normalize_timestamp_safe(ts: str) -> str:
    """Normalize timestamp; raise 400 on invalid input."""
    raw = ts.strip()
    normalized = normalize_timestamp(raw)
    # normalize_timestamp returns raw value on parse failure — detect that.
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid timestamp: {ts!r}",
        )
    return normalized


def normalize_party_record(record: PartyRecord) -> dict:
    """
    Normalize a party record so logically identical inputs produce
    identical canonical representations.

    Rules:
      - trim surrounding whitespace
      - lowercase user_id (casing consistency across systems)
      - preserve transaction_id casing (treated as opaque identifier)
      - amount → string with 2 decimals
      - created_at → ISO 8601 UTC (`...Z`)
      - deterministic field ordering is applied later by canonicalization
    """
    return {
        "transaction_id": record.transaction_id.strip(),
        "user_id": record.user_id.strip().lower(),
        "amount": _normalize_amount(record.amount),
        "created_at": _normalize_timestamp_safe(record.created_at),
    }


@router.post("/proof", response_model=ProofResponse)
async def generate_party_proof(record: PartyRecord):
    """
    Generate a deterministic proof for a party record.

    Steps:
      1. Normalize fields (trim, casing, amount format, timestamp format)
      2. Canonicalize to a deterministic JSON string (sorted keys)
      3. SHA-256 hash the canonical JSON

    Two parties applying these same steps to logically-identical records
    will produce identical `proof_hash` values — enabling proof-based
    consistency comparison without exposing raw data.
    """
    normalized = normalize_party_record(record)
    canonical_json = canonicalize_to_json(normalized)
    proof_hash = compute_sha256(canonical_json)

    return ProofResponse(
        proof_hash=proof_hash,
        normalized_payload=normalized,
        metadata=ProofMetadata(
            algorithm="SHA-256",
            canonicalization="sorted-keys/utf-8/no-whitespace",
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        ),
    )


# ---------------------------------------------------------------------------
# Compliance-aware proof issuance & auditor verification
# ---------------------------------------------------------------------------

class ComplianceResult(BaseModel):
    kyc: str = Field(..., pattern="^(Pass|Fail)$")
    aml: str = Field(..., pattern="^(Pass|Fail)$")
    limits: str = Field(..., pattern="^(Within allowed range|Exceeded)$")
    status: str = Field(..., pattern="^(COMPLIANT|NON-COMPLIANT)$")


class IssueRequest(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=200)
    user_id: str = Field(..., min_length=1, max_length=200)
    amount: Union[str, float, int]
    created_at: str = Field(..., min_length=1)
    compliance: ComplianceResult


class IssueResponse(BaseModel):
    proof_id: str
    proof_hash: str
    transaction_id: str
    issued_at: str
    metadata: ProofMetadata


class VerifyByIdResponse(BaseModel):
    valid: bool
    proof_id: str
    transaction_id: Optional[str] = None
    compliance: Optional[dict] = None
    issued_at: Optional[str] = None
    reason: Optional[str] = None


def _build_canonical_payload(record: PartyRecord, compliance: ComplianceResult) -> dict:
    """Normalize the transaction record and embed the compliance result."""
    normalized = normalize_party_record(record)
    return {
        **normalized,
        "compliance": {
            "kyc": compliance.kyc,
            "aml": compliance.aml,
            "limits": compliance.limits,
            "status": compliance.status,
        },
    }


@router.post("/issue", response_model=IssueResponse)
async def issue_proof(req: IssueRequest):
    """
    Issue a compliance-aware proof for a transaction and persist it so it can
    be verified later by an auditor using only the Proof ID.
    """
    from server import db as database

    record = PartyRecord(
        transaction_id=req.transaction_id,
        user_id=req.user_id,
        amount=req.amount,
        created_at=req.created_at,
    )
    full_payload = _build_canonical_payload(record, req.compliance)
    canonical_json = canonicalize_to_json(full_payload)
    proof_hash = compute_sha256(canonical_json)

    issued_at = (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    )

    await database.demo_proofs.replace_one(
        {"proof_id": proof_hash},
        {
            "proof_id": proof_hash,
            "transaction_id": full_payload["transaction_id"],
            "compliance": full_payload["compliance"],
            "normalized_payload": full_payload,
            "issued_at": issued_at,
        },
        upsert=True,
    )

    return IssueResponse(
        proof_id=proof_hash,
        proof_hash=proof_hash,
        transaction_id=full_payload["transaction_id"],
        issued_at=issued_at,
        metadata=ProofMetadata(
            algorithm="SHA-256",
            canonicalization="sorted-keys/utf-8/no-whitespace",
            generated_at=issued_at,
        ),
    )


@router.get("/verify/{proof_id}", response_model=VerifyByIdResponse)
async def verify_proof_by_id(proof_id: str):
    """
    Look up a stored proof and re-verify its integrity by re-canonicalizing
    and re-hashing the persisted payload. Returns the compliance state that
    was embedded when the proof was issued.
    """
    from server import db as database

    proof_id = proof_id.strip().lower()
    if len(proof_id) != 64 or not all(c in "0123456789abcdef" for c in proof_id):
        return VerifyByIdResponse(
            valid=False,
            proof_id=proof_id,
            reason="Malformed Proof ID",
        )

    doc = await database.demo_proofs.find_one({"proof_id": proof_id}, {"_id": 0})
    if not doc:
        return VerifyByIdResponse(
            valid=False,
            proof_id=proof_id,
            reason="Proof not found",
        )

    canonical = canonicalize_to_json(doc["normalized_payload"])
    recomputed = compute_sha256(canonical)
    if recomputed != proof_id:
        return VerifyByIdResponse(
            valid=False,
            proof_id=proof_id,
            transaction_id=doc.get("transaction_id"),
            compliance=doc.get("compliance"),
            issued_at=doc.get("issued_at"),
            reason="Hash mismatch — proof integrity failed",
        )

    return VerifyByIdResponse(
        valid=True,
        proof_id=proof_id,
        transaction_id=doc["transaction_id"],
        compliance=doc["compliance"],
        issued_at=doc["issued_at"],
    )


# ---------------------------------------------------------------------------
# Independent signed proof artifact (Ed25519, downloadable, externally verifiable)
# ---------------------------------------------------------------------------

class ArtifactRequest(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=200)
    user_id: str = Field(..., min_length=1, max_length=200)
    amount: Union[str, float, int]
    compliance: ComplianceResult
    timestamp: Optional[str] = None


class ArtifactVerifyResult(BaseModel):
    valid: bool
    status: str  # valid_compliant | valid_non_compliant | invalid
    reason: Optional[str] = None
    extracted: Optional[Dict[str, Any]] = None


@router.post("/artifact")
async def build_downloadable_artifact(req: ArtifactRequest):
    """
    Build and sign a standalone proof artifact that can be downloaded,
    shared, and independently verified anywhere.

    Response:
      - Body: canonical JSON of the signed artifact
      - Content-Type: application/pfp-proof+json;v=1
      - Content-Disposition: attachment (suggested filename with proof_id)
    """
    from server import db as database
    from services.artifact_service import build_signed_artifact

    try:
        artifact = await build_signed_artifact(
            database,
            transaction_id=req.transaction_id,
            user_id=req.user_id,
            amount=req.amount,
            compliance=req.compliance.model_dump(exclude={"status"}),
            timestamp=req.timestamp,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    # Canonical body so the download matches what was signed.
    body = canonicalize_to_json(artifact)
    filename = f"pfp-proof-{artifact['proof_id'][:16]}.json"
    return Response(
        content=body,
        media_type="application/pfp-proof+json;v=1",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/artifact/verify", response_model=ArtifactVerifyResult)
async def verify_downloadable_artifact(artifact: Dict[str, Any]):
    """
    Independently verify an uploaded/pasted signed proof artifact.

    Runs strict schema checks, canonical-ordering enforcement, normalization,
    timestamp skew, constant-time proof_id comparison, kid lookup (including
    revocation), and Ed25519 signature verification.
    """
    from server import db as database
    from services.artifact_service import verify_signed_artifact

    result = await verify_signed_artifact(database, artifact)
    return ArtifactVerifyResult(**result)

