"""FEA generation and verification routes (authenticated)."""
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from typing import Optional

from models.fea import (
    GenerateFEARequest,
    FEAResponse,
    VerifyFEARequest,
    VerifyFEAResponse
)
from services.fea_service import generate_fea, get_canonical_payload_hash
from services.verification_service import verify_fea_public, get_signature_version
from routes.auth import verify_api_key

router = APIRouter(prefix="/fea", tags=["FEA"])


@router.post("/generate", response_model=FEAResponse, dependencies=[Depends(verify_api_key)])
async def generate_fea_endpoint(request: GenerateFEARequest, db=None):
    """
    Generate a Financial Evidence Artifact.

    SIGNING MODEL (v2):
    - Builds FEA structure → computes SHA-256 → adds fea_hash
    - Canonicalizes FULL structure (including fea_hash)
    - Signs the canonical JSON directly using Ed25519

    Idempotency:
    - Same idempotency_key + same payload = same FEA returned
    - Same idempotency_key + different payload = 409 CONFLICT
    """
    from server import db as database

    # Check idempotency
    existing = await database.feas.find_one(
        {"idempotency_key": request.idempotency_key},
        {"_id": 0}
    )

    if existing:
        # Compute current payload hash
        current_hash = get_canonical_payload_hash(request)

        if existing["canonical_payload_hash"] == current_hash:
            # Same payload, return existing FEA
            return FEAResponse(
                fea_id=existing["fea_id"],
                fea_hash=existing["fea_hash"],
                signature=existing["signature"],
                public_key_id=existing["public_key_id"],
                fea_payload=existing["fea_payload"],
                created_at=existing["created_at"]
            )
        else:
            # Different payload with same idempotency key - reject
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key already used with different payload"
            )

    # Generate new FEA
    try:
        response, document = generate_fea(request)

        # Store in database
        await database.feas.insert_one(document.model_dump())

        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/verify", response_model=VerifyFEAResponse, dependencies=[Depends(verify_api_key)])
async def verify_fea_endpoint(request: VerifyFEARequest):
    """
    Verify an FEA payload and signature.

    VERIFICATION PROTOCOL:
    1. Extract fea_payload (full payload including fea_hash)
    2. Recompute fea_hash:
       - Remove fea_hash field from payload
       - Canonicalize (sort keys, remove nulls)
       - Compute SHA-256
    3. Compare computed hash with fea_payload.fea_hash
    4. Canonicalize FULL fea_payload (including fea_hash)
    5. Verify Ed25519 signature:
       - v2: verify against canonical message (correct)
       - v1: verify against fea_hash (legacy, backward compatible)
    """
    valid, reason = verify_fea_public(request.fea_payload, request.signature)

    return VerifyFEAResponse(
        valid=valid,
        reason=reason,
        verified_at=datetime.now(timezone.utc).isoformat()
    )
