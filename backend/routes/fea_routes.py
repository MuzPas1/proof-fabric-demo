"""FEA generation and verification routes (authenticated)."""
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from models.fea import (
    GenerateFEARequest,
    FEAResponse,
    VerifyFEARequest,
    VerifyFEAResponse
)
from services.fea_service import generate_fea, get_canonical_payload_hash
from services.verification_service import verify_fea_public
from routes.auth import verify_api_key

router = APIRouter(prefix="/fea", tags=["FEA"])


@router.post("/generate", response_model=FEAResponse, dependencies=[Depends(verify_api_key)])
async def generate_fea_endpoint(request: GenerateFEARequest):
    """
    Generate a Financial Evidence Artifact.

    RESPONSE STRUCTURE (clean separation):
    - fea_payload: the signed data (ONLY this is signed)
    - signature: pure base64 Ed25519 signature
    - signature_version: metadata (NOT signed)
    - created_at: metadata (NOT signed)

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
                fea_payload=existing["fea_payload"],
                signature=existing["signature"],
                signature_version=existing.get("signature_version", "v1"),
                public_key_id=existing["public_key_id"],
                created_at=existing["created_at"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key already used with different payload"
            )

    # Generate new FEA
    try:
        response, document = generate_fea(request, skip_timestamp_validation=True)

        # Store in database
        await database.feas.insert_one(document.model_dump())

        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/verify", response_model=VerifyFEAResponse, dependencies=[Depends(verify_api_key)])
async def verify_fea_endpoint(request: VerifyFEARequest):
    """
    Verify an FEA payload and signature.

    ACCEPTS BOTH FORMATS:
    - New: fea_payload + signature + signature_version (external)
    - Legacy: fea_payload (with signature_version inside) + signature

    VERIFICATION PROTOCOL:
    1. Detect signature_version (external > payload field > prefix > v1)
    2. Clean payload (remove legacy signature_version if present)
    3. Recompute fea_hash for integrity check
    4. Canonicalize cleaned fea_payload
    5. Verify Ed25519 signature based on version
    """
    valid, reason, sig_version = verify_fea_public(
        request.fea_payload,
        request.signature,
        request.signature_version  # External version (new format)
    )

    return VerifyFEAResponse(
        valid=valid,
        reason=reason,
        signature_version=sig_version,
        verified_at=datetime.now(timezone.utc).isoformat()
    )
