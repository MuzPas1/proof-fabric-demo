"""FEA generation, verification, batch, and listing routes (authenticated)."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from models.fea import (
    GenerateFEARequest,
    FEAResponse,
    VerifyFEARequest,
    VerifyFEAResponse,
)
from models.ai_provenance import AttachProvenanceRequest
from models.auth_models import ApiKeyRecord
from services.fea_service import (
    generate_fea,
    get_canonical_payload_hash,
    get_transaction_payload_hash,
)
from services.verification_service import verify_fea_with_registry
from services import audit_service, webhook_service
from auth.dependencies import require_scope
from core.ratelimit import limiter
from core.observability import FEA_GENERATED, FEA_VERIFIED

router = APIRouter(prefix="/fea", tags=["FEA"])


async def check_replay_protection(db, tenant_id: str, transaction_id: str, timestamp: str, request: GenerateFEARequest) -> FEAResponse | None:
    """Check for transaction replay based on (tenant_id, transaction_id, timestamp)."""
    from crypto.canonicalize import normalize_timestamp

    normalized_ts = normalize_timestamp(timestamp)

    existing = await db.feas.find_one(
        {
            "tenant_id": tenant_id,
            "fea_payload.transaction_summary.transaction_id": transaction_id,
            "fea_payload.transaction_summary.timestamp": normalized_ts,
        },
        {"_id": 0},
    )

    if existing:
        current_txn_hash = get_transaction_payload_hash(request)
        stored_txn_hash = existing.get("transaction_payload_hash", "")

        if not stored_txn_hash:
            current_hash = get_canonical_payload_hash(request)
            stored_txn_hash = existing["canonical_payload_hash"]
            current_txn_hash = current_hash

        if stored_txn_hash == current_txn_hash:
            return FEAResponse(
                fea_id=existing["fea_id"],
                fea_payload=existing["fea_payload"],
                signature=existing["signature"],
                signature_version=existing.get("signature_version", "v1"),
                public_key_id=existing["public_key_id"],
                created_at=existing["created_at"],
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction replay detected with conflicting data",
        )

    return None


async def _generate_one(database, request: GenerateFEARequest, tenant_id: str) -> FEAResponse:
    """Core single-FEA generation with dual-layer replay protection (tenant scoped)."""
    # Resolve signature suite (crypto agility). Default Ed25519. When the
    # feature flag is OFF, only Ed25519 is permitted (no downgrade/confusion).
    from crypto import suites
    from core.config import settings

    suite_alg = "Ed25519"
    requested = getattr(request, "signature_suite", None)
    if requested:
        norm = suites.normalize_algorithm(requested)
        if norm != "Ed25519":
            if not settings.ENABLE_CRYPTO_SUITES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Crypto-agility (non-Ed25519 suites) is not enabled on this deployment",
                )
            if not suites.is_supported(norm):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported signature suite: {requested}",
                )
            from core.kms import get_kms
            if not get_kms().supports_algorithm("production", norm):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No signing key configured for suite {norm}",
                )
        suite_alg = norm

    # BYOS: resolve the tenant's configured signer (if any). When BYOS is OFF
    # or no config exists, this is the platform LocalSigner with ``suite_alg``
    # (byte-identical to the existing Ed25519 path).
    from services import signer_service
    signer = await signer_service.resolve_signer(database, tenant_id, default_suite=suite_alg)
    if signer.name != "local" and requested:
        # A BYOS signer dictates the algorithm; an explicit conflicting suite is
        # rejected to avoid ambiguity.
        if suites.normalize_algorithm(requested) != suites.normalize_algorithm(signer.algorithm):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tenant signer uses {signer.algorithm}; cannot override with {requested}",
            )

    # Layer 1: idempotency key (scoped to tenant)
    existing_by_idem = await database.feas.find_one(
        {"tenant_id": tenant_id, "idempotency_key": request.idempotency_key},
        {"_id": 0},
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
                created_at=existing_by_idem["created_at"],
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already used with different payload",
        )

    # Layer 2: transaction replay
    existing_by_txn = await check_replay_protection(
        database, tenant_id, request.transaction_id, request.timestamp, request
    )
    if existing_by_txn:
        return existing_by_txn

    try:
        response, document = generate_fea(request, skip_timestamp_validation=True, tenant_id=tenant_id, suite_alg=suite_alg, signer=signer)
        await database.feas.insert_one(document.model_dump())
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/generate", response_model=FEAResponse)
@limiter.limit("120/minute")
async def generate_fea_endpoint(
    request: Request,
    body: GenerateFEARequest,
    key: ApiKeyRecord = Depends(require_scope("fea:write")),
):
    """Generate a Proof Artifact (tenant-bound, dual-layer replay protection)."""
    from server import db as database

    response = await _generate_one(database, body, key.tenant_id)
    try:
        FEA_GENERATED.labels(key.tenant_id).inc()
        await audit_service.record_audit(
            database, "fea.generated", actor=key.key_id, tenant_id=key.tenant_id,
            target=response.fea_id, metadata={"transaction_id": body.transaction_id},
        )
        await webhook_service.dispatch_event(
            database, key.tenant_id, "fea.generated",
            {"fea_id": response.fea_id, "transaction_id": body.transaction_id},
        )
    except Exception:
        pass
    return response


class BatchGenerateRequest(BaseModel):
    items: List[GenerateFEARequest] = Field(..., min_length=1, max_length=500)


class BatchItemResult(BaseModel):
    index: int
    success: bool
    fea_id: Optional[str] = None
    error: Optional[str] = None


class BatchGenerateResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[BatchItemResult]


@router.post("/batch", response_model=BatchGenerateResponse)
@limiter.limit("30/minute")
async def batch_generate_fea(
    request: Request,
    body: BatchGenerateRequest,
    key: ApiKeyRecord = Depends(require_scope("fea:write")),
):
    """Generate up to 500 Proof Artifacts in a single call. Each item is processed
    independently; partial failures are reported per-item."""
    from server import db as database

    results: List[BatchItemResult] = []
    succeeded = 0
    for idx, item in enumerate(body.items):
        try:
            resp = await _generate_one(database, item, key.tenant_id)
            results.append(BatchItemResult(index=idx, success=True, fea_id=resp.fea_id))
            succeeded += 1
            FEA_GENERATED.labels(key.tenant_id).inc()
        except HTTPException as e:
            results.append(BatchItemResult(index=idx, success=False, error=str(e.detail)))
        except Exception as e:
            results.append(BatchItemResult(index=idx, success=False, error=str(e)))

    await audit_service.record_audit(
        database, "fea.batch_generated", actor=key.key_id, tenant_id=key.tenant_id,
        metadata={"total": len(body.items), "succeeded": succeeded},
    )
    return BatchGenerateResponse(
        total=len(body.items), succeeded=succeeded,
        failed=len(body.items) - succeeded, results=results,
    )


@router.post("/verify", response_model=VerifyFEAResponse)
@limiter.limit("240/minute")
async def verify_fea_endpoint(
    request: Request,
    body: VerifyFEARequest,
    key: ApiKeyRecord = Depends(require_scope("fea:verify")),
):
    """Verify a Proof Artifact payload and signature."""
    valid, reason, sig_version = await verify_fea_with_registry(
        body.fea_payload, body.signature, body.signature_version
    )
    try:
        FEA_VERIFIED.labels("valid" if valid else "invalid").inc()
    except Exception:
        pass
    return VerifyFEAResponse(
        valid=valid, reason=reason, signature_version=sig_version,
        verified_at=datetime.now(timezone.utc).isoformat(),
    )


class FEAListItem(BaseModel):
    fea_id: str
    transaction_id: Optional[str] = None
    created_at: str
    public_key_id: str


class FEAListResponse(BaseModel):
    items: List[FEAListItem]
    total: int
    limit: int
    skip: int


@router.get("", response_model=FEAListResponse)
async def list_feas(
    key: ApiKeyRecord = Depends(require_scope("fea:read")),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """List the authenticated tenant's Proof Artifacts (paginated)."""
    from server import db as database
    query = {"tenant_id": key.tenant_id}
    total = await database.feas.count_documents(query)
    cursor = database.feas.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        items.append(FEAListItem(
            fea_id=doc["fea_id"],
            transaction_id=doc.get("fea_payload", {}).get("transaction_summary", {}).get("transaction_id"),
            created_at=doc["created_at"],
            public_key_id=doc["public_key_id"],
        ))
    return FEAListResponse(items=items, total=total, limit=limit, skip=skip)


@router.get("/{fea_id}", response_model=FEAResponse)
async def get_fea(fea_id: str, key: ApiKeyRecord = Depends(require_scope("fea:read"))):
    """Authenticated single Proof Artifact fetch (tenant scoped)."""
    from server import db as database
    doc = await database.feas.find_one(
        {"fea_id": fea_id, "tenant_id": key.tenant_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"FEA not found: {fea_id}")
    return FEAResponse(
        fea_id=doc["fea_id"], fea_payload=doc["fea_payload"], signature=doc["signature"],
        signature_version=doc.get("signature_version", "v2"),
        public_key_id=doc["public_key_id"], created_at=doc["created_at"],
    )


class PublicFEAVerifyResponse(BaseModel):
    found: bool
    fea_id: str
    valid: Optional[bool] = None
    reason: Optional[str] = None
    signature_version: Optional[str] = None
    public_key_id: Optional[str] = None
    created_at: Optional[str] = None
    transaction_id: Optional[str] = None
    artifact: Optional[Dict[str, Any]] = None


@router.get("/public/{fea_id}", response_model=PublicFEAVerifyResponse)
@limiter.limit("120/minute")
async def public_verify_fea_by_id(request: Request, fea_id: str):
    """Public, cross-tenant lookup + independent verification of a Proof Artifact
    by its (unguessable) FEA ID. Returns the signature verdict and the full signed
    artifact JSON so an auditor can verify and/or download it. The payload is
    privacy-preserving (hashes/tokenized ids only)."""
    from server import db as database
    doc = await database.feas.find_one({"fea_id": fea_id}, {"_id": 0})
    if not doc:
        return PublicFEAVerifyResponse(found=False, fea_id=fea_id, reason="Proof not found")
    valid, reason, sig_version = await verify_fea_with_registry(
        doc["fea_payload"], doc["signature"], doc.get("signature_version")
    )
    txid = (doc.get("fea_payload", {}) or {}).get("transaction_summary", {}).get("transaction_id")
    artifact = {
        "fea_id": doc["fea_id"],
        "fea_payload": doc["fea_payload"],
        "signature": doc["signature"],
        "signature_version": doc.get("signature_version", "v2"),
        "public_key_id": doc["public_key_id"],
        "created_at": doc["created_at"],
        "event_descriptor": doc.get("event_descriptor"),
        "ai_provenance": doc.get("ai_provenance"),
        "time_anchor": doc.get("time_anchor"),
    }
    return PublicFEAVerifyResponse(
        found=True, fea_id=fea_id, valid=valid, reason=reason,
        signature_version=sig_version, public_key_id=doc["public_key_id"],
        created_at=doc["created_at"], transaction_id=txid, artifact=artifact,
    )


@router.post("/{fea_id}/anchor")
@limiter.limit("60/minute")
async def anchor_fea_endpoint(
    request: Request,
    fea_id: str,
    key: ApiKeyRecord = Depends(require_scope("fea:write")),
):
    """Attach a detached Independent Time Attestation to an existing proof.

    Additive & opt-in (gated by ENABLE_TIME_ANCHOR). Does NOT modify the signed
    payload, signature, or fea_id — the anchor commits to the existing fea_hash.
    Idempotent: re-anchoring returns the existing envelope.
    """
    from core.config import settings as _settings
    if not _settings.ENABLE_TIME_ANCHOR:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time attestation not enabled")
    from server import db as database
    from services.time_anchor_service import anchor_fea
    try:
        envelope = await anchor_fea(database, fea_id, tenant_id=key.tenant_id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proof not found: {fea_id}")
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    try:
        await audit_service.record_audit(
            database, "fea.time_anchored", actor=key.key_id, tenant_id=key.tenant_id, target=fea_id,
        )
    except Exception:
        pass
    return {"fea_id": fea_id, "time_anchor": envelope}


@router.post("/{fea_id}/provenance")
@limiter.limit("60/minute")
async def attach_provenance_endpoint(
    request: Request,
    fea_id: str,
    body: AttachProvenanceRequest,
    key: ApiKeyRecord = Depends(require_scope("fea:write")),
):
    """Attach a detached AI Provenance & Accountability envelope to an existing proof.

    Additive & opt-in (gated by ENABLE_AI_PROVENANCE). Does NOT modify the signed
    payload, signature, or fea_id — the envelope binds to the existing fea_hash and
    is itself signed (Ed25519) for independent, tamper-evident verification.
    Privacy-preserving: hashes & identity metadata only — no raw content stored.
    Write-once / idempotent: re-attaching returns the existing envelope.
    """
    from core.config import settings as _settings
    if not _settings.ENABLE_AI_PROVENANCE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provenance not enabled")
    from server import db as database
    from services.ai_provenance_service import attach_provenance
    try:
        envelope = await attach_provenance(database, fea_id, body, tenant_id=key.tenant_id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proof not found: {fea_id}")
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    try:
        await audit_service.record_audit(
            database, "fea.provenance_attached", actor=key.key_id, tenant_id=key.tenant_id, target=fea_id,
        )
    except Exception:
        pass
    return {"fea_id": fea_id, "ai_provenance": envelope}
