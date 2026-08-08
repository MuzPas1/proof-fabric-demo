"""Admin control-plane routes for the Tarabut Gateway (Open Banking) provider.

Additive & isolated. JWT + RBAC protected, feature-gated by
ENABLE_EVENT_INGESTION. Inbound Tarabut payment webhooks use the existing public
ingestion endpoint (/api/ingest/{slug}) with adapter=tarabut + auth=rsa_sha256;
these admin routes cover status, the API/proof catalog, event->proof issuance
(usable for validation with real Tarabut-shaped payloads before live keys), a
convenience to configure the RS256 webhook verification key, and outbound
OAuth2 API triggers (active once sandbox credentials are configured).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth.dependencies import require_permission, resolve_tenant_scope
from auth.rbac import Permission
from core.config import settings
from models.auth_models import User
from services import audit_service, ingestion_service, tarabut_service
from core.ingestion.tarabut_client import TarabutError

router = APIRouter(prefix="/admin/tarabut", tags=["Admin — Tarabut Open Banking"])


def _db():
    from server import db
    return db


def _guard():
    if not settings.ENABLE_EVENT_INGESTION:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event ingestion is not enabled on this deployment")


class ProveEventRequest(BaseModel):
    event: Dict[str, Any] = Field(..., description="A Tarabut event (service envelope, payment webhook, or consent/account/transaction object)")
    tenant_id: Optional[str] = None


class WebhookKeyRequest(BaseModel):
    integration_id: str
    public_key: Optional[str] = Field(None, description="RS256 public key (PEM)")
    jwks_url: Optional[str] = None
    key_id: Optional[str] = Field(None, description="Key id (kid) to map the PEM under; optional")
    accept_unverified: Optional[bool] = None


class OAuthConfigRequest(BaseModel):
    integration_id: str
    client_id: Optional[str] = Field(None, description="Tarabut OAuth Client ID (non-secret)")
    client_secret: Optional[str] = Field(None, description="Tarabut OAuth Client Secret (stored redacted)")
    redirect_uri: Optional[str] = None
    region: Optional[str] = None
    payment_client_id: Optional[str] = None


class IntentRequest(BaseModel):
    user: Dict[str, Any]
    provider_id: str = "BLUE"
    redirect_url: Optional[str] = None
    language: Optional[str] = None
    purpose_statement: Optional[str] = None
    permissions_list: Optional[List[str]] = None
    tenant_id: Optional[str] = None


class AccountsRequest(BaseModel):
    customer_user_id: str
    tenant_id: Optional[str] = None


class RevokeConsentRequest(BaseModel):
    consent_id: str
    customer_user_id: str
    tenant_id: Optional[str] = None


class PaymentStatusRequest(BaseModel):
    payment_id: str
    tenant_id: Optional[str] = None


@router.get("/status")
async def tarabut_status(user: User = Depends(require_permission(Permission.INTEGRATIONS_READ))):
    _guard()
    return await tarabut_service.get_status(_db())


@router.get("/catalog")
async def tarabut_catalog(user: User = Depends(require_permission(Permission.INTEGRATIONS_READ))):
    _guard()
    return {
        "supported_apis": tarabut_service.SUPPORTED_APIS,
        "supported_proof_events": tarabut_service.SUPPORTED_PROOF_EVENTS,
        "region": settings.TARABUT_REGION,
    }


@router.post("/prove-event")
async def prove_event(
    body: ProveEventRequest,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
):
    """Normalize a Tarabut event and issue a Proof Artifact through the existing
    pipeline. Works without live sandbox credentials, so operators can validate
    the full event->proof->verification path with real Tarabut-shaped payloads."""
    _guard()
    tenant_id = resolve_tenant_scope(user, body.tenant_id)
    try:
        result = await tarabut_service.record_event_proof(_db(), body.event, tenant_id=tenant_id)
    except TarabutError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    await audit_service.record_audit(
        _db(), "tarabut.event_proved", actor=user.email, tenant_id=tenant_id,
        target=result.get("fea_id"), metadata={"event_type": result.get("event_type")},
    )
    return result


@router.post("/webhook-key")
async def configure_webhook_key(
    body: WebhookKeyRequest,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
    tenant_id: str = Query(None),
):
    """Configure the RS256 webhook verification material on a Tarabut integration
    without a code change (PEM public key, JWKS URL, and/or accept-unverified)."""
    _guard()
    scope = resolve_tenant_scope(user, tenant_id)
    try:
        current = await ingestion_service.get_integration(_db(), body.integration_id, scope)
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    if current.get("adapter") != "tarabut":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "integration is not a Tarabut provider")

    auth_config = dict(current.get("auth_config") or {})
    if body.public_key:
        if body.key_id:
            keys = auth_config.get("rsa_public_keys")
            keys = dict(keys) if isinstance(keys, dict) else {}
            keys[body.key_id] = body.public_key
            auth_config["rsa_public_keys"] = keys
        else:
            auth_config["public_key"] = body.public_key
    if body.jwks_url is not None:
        auth_config["jwks_url"] = body.jwks_url
    if body.accept_unverified is not None:
        auth_config["accept_unverified"] = "true" if body.accept_unverified else "false"

    try:
        updated = await ingestion_service.update_integration(
            _db(), body.integration_id, scope, {"auth_config": auth_config})
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    await audit_service.record_audit(
        _db(), "tarabut.webhook_key_configured", actor=user.email,
        tenant_id=updated["tenant_id"], target=body.integration_id,
    )
    return {"integration_id": body.integration_id, "auth_config": updated.get("auth_config")}


@router.post("/oauth-config")
async def configure_oauth(
    body: OAuthConfigRequest,
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
    tenant_id: str = Query(None),
):
    """Securely configure Tarabut OAuth credentials on the Tarabut integration
    (Client ID + Redirect URI in non-secret auth_config; Client Secret stored in
    the integration's redacted secret slot — never returned). Follows the
    existing provider-configuration pattern; no hardcoding."""
    _guard()
    scope = resolve_tenant_scope(user, tenant_id)
    try:
        current = await ingestion_service.get_integration(_db(), body.integration_id, scope)
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    if current.get("adapter") != "tarabut":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "integration is not a Tarabut provider")

    auth_config = dict(current.get("auth_config") or {})
    if body.client_id is not None:
        auth_config["oauth_client_id"] = body.client_id
    if body.redirect_uri is not None:
        auth_config["redirect_uri"] = body.redirect_uri
    if body.region is not None:
        auth_config["tarabut_region"] = body.region
    if body.payment_client_id is not None:
        auth_config["payment_client_id"] = body.payment_client_id

    updates: dict = {"auth_config": auth_config}
    if body.client_secret:  # maps to external_secret (stored redacted, never returned)
        updates["secret"] = body.client_secret
    try:
        updated = await ingestion_service.update_integration(_db(), body.integration_id, scope, updates)
    except ingestion_service.IngestionError as e:
        raise HTTPException(e.status_code, str(e))
    await audit_service.record_audit(
        _db(), "tarabut.oauth_configured", actor=user.email,
        tenant_id=updated["tenant_id"], target=body.integration_id,
    )
    return {
        "integration_id": body.integration_id,
        "oauth_client_id": (updated.get("auth_config") or {}).get("oauth_client_id"),
        "redirect_uri": (updated.get("auth_config") or {}).get("redirect_uri"),
        "region": (updated.get("auth_config") or {}).get("tarabut_region"),
        "client_secret_stored": bool(updated.get("has_external_secret")),
    }


@router.post("/connectivity")
async def connectivity(
    tenant_id: str = Query(None),
    user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
):
    """Live sandbox connectivity check — acquires an access token (never returned)."""
    _guard()
    scope = resolve_tenant_scope(user, tenant_id)
    try:
        return await tarabut_service.check_connectivity(_db(), tenant_id=scope)
    except TarabutError as e:
        raise HTTPException(getattr(e, "status_code", None) or status.HTTP_400_BAD_REQUEST, str(e))


# --- Outbound API triggers (active once sandbox credentials are configured) ---
def _outbound(fn_result):
    return fn_result


@router.post("/connect/intent")
async def create_intent(body: IntentRequest, user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE))):
    _guard()
    tenant_id = resolve_tenant_scope(user, body.tenant_id)
    try:
        return await tarabut_service.prove_create_intent(
            _db(), user=body.user, provider_id=body.provider_id, tenant_id=tenant_id,
            redirect_url=body.redirect_url, language=body.language,
            purpose_statement=body.purpose_statement, permissions_list=body.permissions_list)
    except TarabutError as e:
        raise HTTPException(getattr(e, "status_code", None) or status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/accounts")
async def get_accounts(body: AccountsRequest, user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE))):
    _guard()
    tenant_id = resolve_tenant_scope(user, body.tenant_id)
    try:
        return await tarabut_service.prove_get_accounts(_db(), customer_user_id=body.customer_user_id, tenant_id=tenant_id)
    except TarabutError as e:
        raise HTTPException(getattr(e, "status_code", None) or status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/consent/revoke")
async def revoke_consent(body: RevokeConsentRequest, user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE))):
    _guard()
    tenant_id = resolve_tenant_scope(user, body.tenant_id)
    try:
        return await tarabut_service.prove_revoke_consent(
            _db(), consent_id=body.consent_id, customer_user_id=body.customer_user_id, tenant_id=tenant_id)
    except TarabutError as e:
        raise HTTPException(getattr(e, "status_code", None) or status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/payments/status")
async def payment_status(body: PaymentStatusRequest, user: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE))):
    _guard()
    tenant_id = resolve_tenant_scope(user, body.tenant_id)
    try:
        return await tarabut_service.prove_payment_status(_db(), payment_id=body.payment_id, tenant_id=tenant_id)
    except TarabutError as e:
        raise HTTPException(getattr(e, "status_code", None) or status.HTTP_400_BAD_REQUEST, str(e))
