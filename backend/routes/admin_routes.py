"""Admin control-plane routes (/api/admin). JWT + RBAC protected."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional

from auth.dependencies import require_permission, resolve_tenant_scope, get_current_user
from auth.rbac import Permission, Role
from models.auth_models import (
    User, CreateApiKeyRequest, CreateApiKeyResponse, CreateTenantRequest,
)
from models.key_registry import (
    FederatedKeyRegisterRequest, FederatedKeyRegisterResponse, FederatedKeyConfirmRequest,
)
from services import api_key_service, tenant_service, audit_service, key_service, federated_key_service
from core.config import settings

router = APIRouter(prefix="/admin", tags=["Admin"])


def _db():
    from server import db
    return db


# --------------------------------------------------------------------------
# API key management
# --------------------------------------------------------------------------
@router.post("/api-keys/create", response_model=CreateApiKeyResponse)
async def create_api_key(
    body: CreateApiKeyRequest,
    user: User = Depends(require_permission(Permission.APIKEYS_MANAGE)),
):
    tenant_id = resolve_tenant_scope(user, body.tenant_id)
    record, raw = await api_key_service.create_api_key(
        _db(), name=body.name, tenant_id=tenant_id, customer_id=body.customer_id,
        scopes=body.scopes, expires_in_days=body.expires_in_days, created_by=user.email,
    )
    await audit_service.record_audit(
        _db(), "apikey.created", actor=user.email, tenant_id=tenant_id,
        target=record.key_id, metadata={"name": body.name},
    )
    return CreateApiKeyResponse(
        key_id=record.key_id, api_key=raw, name=record.name,
        tenant_id=record.tenant_id, scopes=record.scopes, expires_at=record.expires_at,
    )


@router.get("/api-keys")
async def list_api_keys(
    user: User = Depends(require_permission(Permission.APIKEYS_READ)),
    tenant_id: Optional[str] = Query(None),
):
    scope = resolve_tenant_scope(user, tenant_id)
    keys = await api_key_service.list_api_keys(_db(), tenant_id=None if user.role == Role.SUPER_ADMIN.value and not tenant_id else scope)
    return {"keys": keys, "total": len(keys)}


@router.post("/api-keys/revoke")
async def revoke_api_key(
    key_id: str = Query(...),
    user: User = Depends(require_permission(Permission.APIKEYS_MANAGE)),
):
    ok = await api_key_service.revoke_api_key(_db(), key_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    await audit_service.record_audit(
        _db(), "apikey.revoked", actor=user.email, tenant_id=user.tenant_id, target=key_id,
    )
    return {"status": "revoked", "key_id": key_id}


# --------------------------------------------------------------------------
# Signing key lifecycle
# --------------------------------------------------------------------------
class CreateKeyRequest(BaseModel):
    public_key_b64: str = Field(..., min_length=10)
    public_key_id: Optional[str] = None


@router.post("/keys/create")
async def create_signing_key(
    body: CreateKeyRequest,
    user: User = Depends(require_permission(Permission.KEYS_MANAGE)),
):
    """Register an externally-generated public key in the registry."""
    import hashlib, base64
    kid = body.public_key_id or ("key_" + hashlib.sha256(base64.b64decode(body.public_key_b64)).hexdigest()[:16])
    info = await key_service.register_key(kid, body.public_key_b64, status="active")
    await audit_service.record_audit(
        _db(), "key.created", actor=user.email, tenant_id=user.tenant_id, target=kid,
    )
    return {"status": "created", "key": info.model_dump()}


@router.post("/keys/rotate")
async def rotate_signing_key(user: User = Depends(require_permission(Permission.KEYS_MANAGE))):
    """Generate a new keypair, register its public key as active, retire the
    previous active key(s). Returns the new private seed ONCE — the operator
    must deploy it to the KMS/secret store and restart for new issuance to use it."""
    kp = key_service.generate_new_keypair()
    await key_service.rotate_key(kp["public_key_id"], kp["public_key_b64"])
    await audit_service.record_audit(
        _db(), "key.rotated", actor=user.email, tenant_id=user.tenant_id,
        target=kp["public_key_id"],
    )
    return {
        "status": "rotated",
        "new_public_key_id": kp["public_key_id"],
        "new_public_key_b64": kp["public_key_b64"],
        "new_private_seed_b64": kp["seed_b64"],
        "action_required": "Set PRIVATE_KEY to new_private_seed_b64 in your KMS/secret store and restart the service to sign with the new key.",
    }


@router.post("/keys/revoke")
async def revoke_signing_key(
    public_key_id: str = Query(...),
    user: User = Depends(require_permission(Permission.KEYS_MANAGE)),
):
    ok = await key_service.revoke_key(public_key_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found")
    await audit_service.record_audit(
        _db(), "key.revoked", actor=user.email, tenant_id=user.tenant_id, target=public_key_id,
    )
    return {"status": "revoked", "public_key_id": public_key_id}


@router.post("/keys/retire")
async def retire_signing_key(
    public_key_id: str = Query(...),
    user: User = Depends(require_permission(Permission.KEYS_MANAGE)),
):
    ok = await key_service.retire_key(public_key_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found")
    await audit_service.record_audit(
        _db(), "key.retired", actor=user.email, tenant_id=user.tenant_id, target=public_key_id,
    )
    return {"status": "retired", "public_key_id": public_key_id}


# --------------------------------------------------------------------------
# Federated key registry (customer / partner-owned keys, proof-of-possession)
# --------------------------------------------------------------------------
@router.post("/keys/federated/register", response_model=FederatedKeyRegisterResponse)
async def register_federated_key(
    body: FederatedKeyRegisterRequest,
    tenant_id: Optional[str] = Query(None),
    user: User = Depends(require_permission(Permission.KEYS_MANAGE)),
):
    """Register a customer/partner-owned public key (raw / JWK / SPKI PEM).

    Returns a single-use proof-of-possession challenge; the key stays `pending`
    until /keys/federated/confirm proves control of the private key.
    """
    if not settings.ENABLE_FEDERATED_KEYS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Federated key registry is not enabled on this deployment")
    scope = resolve_tenant_scope(user, tenant_id)
    try:
        info, challenge, expires_at = await federated_key_service.register_federated_key(
            _db(), scope,
            algorithm=body.algorithm, key_format=body.key_format,
            public_key=body.public_key, jwk=body.jwk, owner=body.owner,
            label=body.label, not_before=body.not_before, not_after=body.not_after,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await audit_service.record_audit(
        _db(), "key.federated_registered", actor=user.email, tenant_id=scope, target=info.public_key_id,
        metadata={"algorithm": info.algorithm, "owner": info.owner},
    )
    return FederatedKeyRegisterResponse(
        public_key_id=info.public_key_id, tenant_id=scope, algorithm=info.algorithm,
        status=info.status, pop_challenge=challenge, expires_at=expires_at,
    )


@router.post("/keys/federated/confirm")
async def confirm_federated_key(
    body: FederatedKeyConfirmRequest,
    tenant_id: Optional[str] = Query(None),
    user: User = Depends(require_permission(Permission.KEYS_MANAGE)),
):
    """Confirm proof-of-possession and activate a pending federated key."""
    if not settings.ENABLE_FEDERATED_KEYS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Federated key registry is not enabled on this deployment")
    scope = resolve_tenant_scope(user, tenant_id)
    try:
        info = await federated_key_service.confirm_federated_key(
            _db(), scope, body.public_key_id, body.pop_signature,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await audit_service.record_audit(
        _db(), "key.federated_confirmed", actor=user.email, tenant_id=scope, target=info.public_key_id,
    )
    return {"status": info.status, "public_key_id": info.public_key_id, "pop_verified": info.pop_verified}


# --------------------------------------------------------------------------
# Bring-Your-Own-Signing (BYOS) — per-tenant signer configuration
# --------------------------------------------------------------------------
class SignerConfigRequest(BaseModel):
    type: str = Field(..., description="local | remote | cloud-kms")
    algorithm: str = Field("Ed25519", description="Ed25519 | ES256 | ES256K")
    # remote
    endpoint: Optional[str] = None
    auth_header: Optional[str] = None
    timeout: Optional[float] = None
    # cloud-kms
    provider: Optional[str] = None
    key_ref: Optional[str] = None
    # remote / cloud-kms expected public key (base64 raw)
    public_key: Optional[str] = None
    logical: Optional[str] = None


@router.post("/signers")
async def configure_signer(
    body: SignerConfigRequest,
    tenant_id: Optional[str] = Query(None),
    user: User = Depends(require_permission(Permission.KEYS_MANAGE)),
):
    """Configure the signer for a tenant (BYOS). Registers the signer's public key."""
    if not settings.ENABLE_BYOS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bring-Your-Own-Signing is not enabled on this deployment")
    from services import signer_service
    scope = resolve_tenant_scope(user, tenant_id)
    try:
        cfg = await signer_service.configure_signer(_db(), scope, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await audit_service.record_audit(
        _db(), "signer.configured", actor=user.email, tenant_id=scope,
        target=cfg.get("public_key_id"), metadata={"type": cfg.get("type"), "algorithm": cfg.get("algorithm")},
    )
    return {"status": "configured", "signer": cfg}


@router.get("/signers")
async def list_signers(
    tenant_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
):
    from services import signer_service
    scope = None if user.role == Role.SUPER_ADMIN.value and not tenant_id else resolve_tenant_scope(user, tenant_id)
    signers = await signer_service.list_signers(_db(), tenant_id=scope)
    return {"signers": signers, "total": len(signers)}


@router.get("/signers/health")
async def signers_health(user: User = Depends(get_current_user)):
    from services import signer_service
    return await signer_service.signers_health(_db())


@router.delete("/signers")
async def delete_signer(
    tenant_id: Optional[str] = Query(None),
    user: User = Depends(require_permission(Permission.KEYS_MANAGE)),
):
    if not settings.ENABLE_BYOS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bring-Your-Own-Signing is not enabled on this deployment")
    from services import signer_service
    scope = resolve_tenant_scope(user, tenant_id)
    ok = await signer_service.delete_signer(_db(), scope)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No signer configured for tenant")
    await audit_service.record_audit(_db(), "signer.deleted", actor=user.email, tenant_id=scope)
    return {"status": "deleted", "tenant_id": scope}


# --------------------------------------------------------------------------
# Tenants
# --------------------------------------------------------------------------
@router.post("/tenants")
async def create_tenant(
    body: CreateTenantRequest,
    user: User = Depends(require_permission(Permission.TENANTS_MANAGE)),
):
    if user.role != Role.SUPER_ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super_admin can create tenants")
    tenant = await tenant_service.create_tenant(_db(), body.name, body.tenant_id)
    await audit_service.record_audit(
        _db(), "tenant.created", actor=user.email, tenant_id=tenant.tenant_id, target=tenant.tenant_id,
    )
    return tenant.model_dump()


@router.get("/tenants")
async def list_tenants(user: User = Depends(require_permission(Permission.TENANTS_READ))):
    if user.role == Role.SUPER_ADMIN.value:
        tenants = await tenant_service.list_tenants(_db())
    else:
        t = await tenant_service.get_tenant(_db(), user.tenant_id)
        tenants = [t.model_dump()] if t else []
        return {"tenants": tenants, "total": len(tenants)}
    return {"tenants": tenants, "total": len(tenants)}


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------
@router.get("/audit")
async def get_audit(
    user: User = Depends(require_permission(Permission.AUDIT_READ)),
    tenant_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    if user.role == Role.SUPER_ADMIN.value:
        scope = tenant_id
    else:
        scope = user.tenant_id
    entries = await audit_service.list_audit(_db(), tenant_id=scope, action=action, limit=limit, skip=skip)
    return {"entries": entries, "count": len(entries)}


@router.get("/audit/verify")
async def verify_audit(user: User = Depends(require_permission(Permission.AUDIT_READ))):
    """Verify the integrity of the audit hash chain."""
    return await audit_service.verify_audit_chain(_db())
