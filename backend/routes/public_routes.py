"""Public routes (no authentication required)."""
from fastapi import APIRouter, HTTPException, status

from models.fea import PublicVerifyResponse
from services.verification_service import verify_fea_public
from services.key_service import get_all_public_keys
from models.key_registry import KeyRegistryResponse

router = APIRouter(prefix="/public", tags=["Public"])


@router.get("/verify/{fea_id}", response_model=PublicVerifyResponse)
async def public_verify_fea(fea_id: str):
    """
    Public verification of an FEA by ID.
    No authentication required.

    Returns clean structure:
    - fea_payload: the signed data
    - signature: pure base64 signature
    - signature_version: metadata
    - signature_valid: verification result
    """
    from server import db

    # Find FEA by ID
    fea_doc = await db.feas.find_one({"fea_id": fea_id}, {"_id": 0})

    if not fea_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FEA not found: {fea_id}"
        )

    # Get signature version (handle legacy documents)
    sig_version = fea_doc.get("signature_version", "v1")
    
    # For legacy documents, check if signature_version is in payload
    fea_payload = fea_doc["fea_payload"]
    if "signature_version" in fea_payload and sig_version == "v1":
        sig_version = fea_payload["signature_version"]

    # Verify the signature
    valid, reason, detected_version = verify_fea_public(
        fea_payload,
        fea_doc["signature"],
        sig_version
    )

    return PublicVerifyResponse(
        fea_id=fea_id,
        fea_payload=fea_payload,
        signature=fea_doc["signature"],
        signature_version=detected_version,
        signature_valid=valid,
        issuer_id=fea_payload.get("issuer_id", "unknown"),
        created_at=fea_doc["created_at"]
    )


@router.get("/keys", response_model=KeyRegistryResponse)
async def get_key_registry():
    """
    Get all public keys in the registry.
    No authentication required.
    """
    keys = get_all_public_keys()
    return KeyRegistryResponse(keys=keys)
