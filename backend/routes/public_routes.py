"""Public routes (no authentication required)."""
from fastapi import APIRouter, HTTPException, status

from core.config import settings
from models.fea import PublicVerifyResponse
from services.verification_service import verify_fea_with_registry
from services.key_service import get_all_keys
from models.key_registry import KeyRegistryResponse

router = APIRouter(prefix="/public", tags=["Public"])


@router.get("/verify/{fea_id}", response_model=PublicVerifyResponse)
async def public_verify_fea(fea_id: str):
    """
    Public verification of a Proof Artifact by ID.
    No authentication required.
    """
    from server import db

    fea_doc = await db.feas.find_one({"fea_id": fea_id}, {"_id": 0})

    if not fea_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FEA not found: {fea_id}"
        )

    sig_version = fea_doc.get("signature_version", "v1")
    fea_payload = fea_doc["fea_payload"]
    
    if "signature_version" in fea_payload and sig_version == "v1":
        sig_version = fea_payload["signature_version"]

    valid, reason, detected_version = await verify_fea_with_registry(
        fea_payload,
        fea_doc["signature"],
        sig_version
    )

    time_attestation = None
    if settings.ENABLE_TIME_ANCHOR and fea_doc.get("time_anchor"):
        try:
            from services.time_anchor_service import verify_time_attestation
            time_attestation = await verify_time_attestation(fea_doc)
        except Exception:
            time_attestation = None

    return PublicVerifyResponse(
        fea_id=fea_id,
        fea_payload=fea_payload,
        signature=fea_doc["signature"],
        signature_version=detected_version,
        signature_valid=valid,
        issuer_id=fea_payload.get("issuer_id", "unknown"),
        created_at=fea_doc["created_at"],
        time_attestation=time_attestation,
    )


@router.get("/keys", response_model=KeyRegistryResponse)
async def get_key_registry():
    """
    Get all public keys in the registry.
    No authentication required.
    
    Returns both active and retired keys to support
    verification of historical Proof Artifacts.
    """
    keys = await get_all_keys()
    
    active_count = sum(1 for k in keys if k.status == "active")
    retired_count = sum(1 for k in keys if k.status == "retired")
    
    return KeyRegistryResponse(
        keys=keys,
        total=len(keys),
        active_count=active_count,
        retired_count=retired_count
    )
