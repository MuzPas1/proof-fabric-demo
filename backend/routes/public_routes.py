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
    
    Returns:
    - fea_hash
    - signature validity
    - timestamp
    - issuer_id
    """
    from server import db
    
    # Find FEA by ID
    fea_doc = await db.feas.find_one({"fea_id": fea_id}, {"_id": 0})
    
    if not fea_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FEA not found: {fea_id}"
        )
    
    # Verify the signature
    valid, reason = verify_fea_public(fea_doc["fea_payload"], fea_doc["signature"])
    
    return PublicVerifyResponse(
        fea_hash=fea_doc["fea_hash"],
        signature_valid=valid,
        timestamp=fea_doc["created_at"],
        issuer_id=fea_doc["fea_payload"].get("issuer_id", "unknown")
    )


@router.get("/keys", response_model=KeyRegistryResponse)
async def get_key_registry():
    """
    Get all public keys in the registry.
    No authentication required.
    """
    keys = get_all_public_keys()
    return KeyRegistryResponse(keys=keys)
