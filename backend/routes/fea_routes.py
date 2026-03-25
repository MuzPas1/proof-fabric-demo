"""FEA generation and verification routes (authenticated)."""
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from models.fea import (
    GenerateFEARequest,
    FEAResponse,
    VerifyFEARequest,
    VerifyFEAResponse
)
from services.fea_service import generate_fea, get_canonical_payload_hash, get_transaction_payload_hash
from services.verification_service import verify_fea_with_registry
from routes.auth import verify_api_key

router = APIRouter(prefix="/fea", tags=["FEA"])


async def check_replay_protection(db, transaction_id: str, timestamp: str, request: GenerateFEARequest) -> FEAResponse | None:
    """
    Check for transaction replay based on (transaction_id + timestamp).
    
    Returns:
    - None: No existing transaction, proceed with generation
    - FEAResponse: Existing FEA with same payload (return it)
    
    Raises:
    - HTTPException 409: Replay attack detected (same transaction, different payload)
    """
    from crypto.canonicalize import normalize_timestamp
    
    normalized_ts = normalize_timestamp(timestamp)
    
    # Check for existing transaction with same (transaction_id, timestamp)
    existing = await db.feas.find_one(
        {
            "fea_payload.transaction_summary.transaction_id": transaction_id,
            "fea_payload.transaction_summary.timestamp": normalized_ts
        },
        {"_id": 0}
    )
    
    if existing:
        # Transaction exists - check if transaction payload matches (excluding idempotency_key)
        current_txn_hash = get_transaction_payload_hash(request)
        stored_txn_hash = existing.get("transaction_payload_hash", "")
        
        # Backward compat: old docs may not have transaction_payload_hash
        if not stored_txn_hash:
            # Fall back to canonical_payload_hash comparison (includes idem key)
            current_hash = get_canonical_payload_hash(request)
            stored_txn_hash = existing["canonical_payload_hash"]
            current_txn_hash = current_hash
        
        if stored_txn_hash == current_txn_hash:
            # Same transaction payload - return existing FEA
            return FEAResponse(
                fea_id=existing["fea_id"],
                fea_payload=existing["fea_payload"],
                signature=existing["signature"],
                signature_version=existing.get("signature_version", "v1"),
                public_key_id=existing["public_key_id"],
                created_at=existing["created_at"]
            )
        else:
            # Different payload - replay attack detected
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction replay detected with conflicting data"
            )
    
    return None


@router.post("/generate", response_model=FEAResponse, dependencies=[Depends(verify_api_key)])
async def generate_fea_endpoint(request: GenerateFEARequest):
    """
    Generate a Financial Evidence Artifact.

    REPLAY PROTECTION (dual layer):
    1. Idempotency key: Same key + same payload = same FEA
    2. Transaction uniqueness: (transaction_id + timestamp) must be globally unique

    If duplicate transaction detected:
    - Same payload → return existing FEA
    - Different payload → 409 CONFLICT (replay attack)
    """
    from server import db as database

    # Layer 1: Check idempotency key
    existing_by_idem = await database.feas.find_one(
        {"idempotency_key": request.idempotency_key},
        {"_id": 0}
    )

    if existing_by_idem:
        current_hash = get_canonical_payload_hash(request)
        
        if existing_by_idem["canonical_payload_hash"] == current_hash:
            return FEAResponse(
                fea_id=existing_by_idem["fea_id"],
                fea_payload=existing_by_idem["fea_payload"],
                signature=existing_by_idem["signature"],
                signature_version=existing_by_idem.get("signature_version", "v1"),
                public_key_id=existing_by_idem["public_key_id"],
                created_at=existing_by_idem["created_at"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key already used with different payload"
            )

    # Layer 2: Check transaction replay (transaction_id + timestamp)
    existing_by_txn = await check_replay_protection(
        database,
        request.transaction_id,
        request.timestamp,
        request
    )
    
    if existing_by_txn:
        return existing_by_txn

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
    """
    valid, reason, sig_version = await verify_fea_with_registry(
        request.fea_payload,
        request.signature,
        request.signature_version
    )

    return VerifyFEAResponse(
        valid=valid,
        reason=reason,
        signature_version=sig_version,
        verified_at=datetime.now(timezone.utc).isoformat()
    )
