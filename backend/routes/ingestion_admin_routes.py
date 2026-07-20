"""Admin control-plane routes for the inbound event ingestion framework.

JWT + RBAC protected. Provides full lifecycle management: create, configure,
enable/disable, credential rotation, monitoring/health, audit, recent events,
and integration testing. All management is restricted to PFP administrators;
the external inbound endpoints (/api/ingest/*) are handled separately and use
per-integration provider auth instead.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth.dependencies import require_permission, resolve_tenant_scope, get_current_user
from auth.rbac import Permission, Role
from core.config import settings
from models.auth_models import User
from models.ingestion import (
    CreateIntegrationRequest, UpdateIntegrationRequest, TestIntegrationRequest,
)
from services import ingestion_service, audit_service

router = APIRouter(prefix="/admin/integrations", tags=["Admin — Integrations"])


def _db():
    from server import db
    return db


def _guard():
    if not settings.ENABLE_EVENT_INGESTION:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event ingestion is not enabled on this deployment")


def _scope_for_read(user: User, tenant_id):
    if user.role == Role.SUPER_ADMIN.value and not tenant_id:
        return None
    return resolve_tenant_scope(user, tenant_id)


@router.post("")
async def create_integration(
    body: CreateIntegrationRequest,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
):
    _guard()
    tenant_id = resolve_tenant_scope(user, body.tenant_id)
    try:
        cfg, raw = await ingestion_service.create_integration(
            _db(), name=body.name, slug=body.slug, tenant_id=tenant_id,
            adapter=body.adapter, auth_provider=body.auth_provider,
            default_currency=body.default_currency, field_map=body.field_map,
            description=body.description, created_by=user.email,
            auth_config=body.auth_config, require_timestamp=body.require_timestamp,
            timestamp_tolerance_seconds=body.timestamp_tolerance_seconds,
            replay_protection=body.replay_protection, secret=body.secret,
        )
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    await audit_service.record_audit(
        _db(), "integration.created", actor=user.email, tenant_id=tenant_id,
        target=cfg.integration_id, metadata={"slug": cfg.slug, "adapter": cfg.adapter, "auth": cfg.auth_provider},
    )
    result = cfg.public()
    if raw is not None:
        result["credential"] = raw  # shown ONCE — not retrievable later
        result["credential_notice"] = "Store this now; it cannot be retrieved again."
    result["inbound_url"] = f"/api/ingest/{cfg.slug}"
    return result


@router.get("")
async def list_integrations(
    user: User = Depends(require_permission(Permission.INTEGRATIONS_READ)),
    tenant_id: str = Query(None),
):
    _guard()
    items = await ingestion_service.list_integrations(_db(), _scope_for_read(user, tenant_id))
    return {"integrations": items, "total": len(items)}


@router.get("/{integration_id}")
async def get_integration(
    integration_id: str,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_READ)),
    tenant_id: str = Query(None),
):
    _guard()
    try:
        return await ingestion_service.get_integration(_db(), integration_id, _scope_for_read(user, tenant_id))
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))


@router.patch("/{integration_id}")
async def update_integration(
    integration_id: str,
    body: UpdateIntegrationRequest,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
    tenant_id: str = Query(None),
):
    _guard()
    scope = _scope_for_read(user, tenant_id)
    try:
        updated = await ingestion_service.update_integration(_db(), integration_id, scope, body.model_dump(exclude_none=True))
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    await audit_service.record_audit(
        _db(), "integration.updated", actor=user.email, tenant_id=updated["tenant_id"], target=integration_id,
    )
    return updated


@router.post("/{integration_id}/enable")
async def enable_integration(
    integration_id: str,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
    tenant_id: str = Query(None),
):
    _guard()
    try:
        cfg = await ingestion_service.set_enabled(_db(), integration_id, _scope_for_read(user, tenant_id), True)
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    await audit_service.record_audit(_db(), "integration.enabled", actor=user.email, tenant_id=cfg["tenant_id"], target=integration_id)
    return cfg


@router.post("/{integration_id}/disable")
async def disable_integration(
    integration_id: str,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
    tenant_id: str = Query(None),
):
    _guard()
    try:
        cfg = await ingestion_service.set_enabled(_db(), integration_id, _scope_for_read(user, tenant_id), False)
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    await audit_service.record_audit(_db(), "integration.disabled", actor=user.email, tenant_id=cfg["tenant_id"], target=integration_id)
    return cfg


@router.post("/{integration_id}/rotate-secret")
async def rotate_secret(
    integration_id: str,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
    tenant_id: str = Query(None),
):
    _guard()
    try:
        cfg, raw = await ingestion_service.rotate_secret(_db(), integration_id, _scope_for_read(user, tenant_id))
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    await audit_service.record_audit(_db(), "integration.secret_rotated", actor=user.email, tenant_id=cfg["tenant_id"], target=integration_id)
    if raw is not None:
        cfg["credential"] = raw
        cfg["credential_notice"] = "Store this now; it cannot be retrieved again."
    return cfg


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: str,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
    tenant_id: str = Query(None),
):
    _guard()
    scope = _scope_for_read(user, tenant_id)
    try:
        cfg = await ingestion_service.get_integration(_db(), integration_id, scope)
        await ingestion_service.delete_integration(_db(), integration_id, scope)
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    await audit_service.record_audit(_db(), "integration.deleted", actor=user.email, tenant_id=cfg["tenant_id"], target=integration_id)
    return {"status": "deleted", "integration_id": integration_id}


@router.get("/{integration_id}/stats")
async def integration_stats(
    integration_id: str,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_READ)),
    tenant_id: str = Query(None),
):
    _guard()
    try:
        return await ingestion_service.get_stats(_db(), integration_id, _scope_for_read(user, tenant_id))
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))


@router.get("/{integration_id}/events")
async def integration_events(
    integration_id: str,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_READ)),
    tenant_id: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    _guard()
    try:
        events = await ingestion_service.list_events(_db(), integration_id, _scope_for_read(user, tenant_id), limit=limit)
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    return {"events": events, "count": len(events)}


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: str,
    body: TestIntegrationRequest,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
    tenant_id: str = Query(None),
):
    _guard()
    from core.ingestion.adapters import AdapterError
    try:
        result = await ingestion_service.dry_run(
            _db(), integration_id, _scope_for_read(user, tenant_id), body.payload, body.issue,
        )
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    except AdapterError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"event validation failed: {e}")
    return result
