"""Webhook subscription routes (/api/webhooks). API-key (tenant) scoped."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from typing import List

from models.auth_models import ApiKeyRecord
from auth.dependencies import require_scope
from services import webhook_service, audit_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def _db():
    from server import db
    return db


class SubscribeRequest(BaseModel):
    url: HttpUrl
    events: List[str] = Field(default_factory=lambda: ["fea.generated"])


@router.post("/subscribe")
async def subscribe(
    body: SubscribeRequest,
    key: ApiKeyRecord = Depends(require_scope("webhooks:manage")),
):
    sub = await webhook_service.subscribe(_db(), key.tenant_id, str(body.url), body.events)
    await audit_service.record_audit(
        _db(), "webhook.subscribed", actor=key.key_id, tenant_id=key.tenant_id, target=sub.webhook_id,
    )
    return {
        "webhook_id": sub.webhook_id, "url": sub.url, "events": sub.events,
        "secret": sub.secret,  # shown once for HMAC verification setup
        "status": sub.status,
    }


@router.get("")
async def list_subscriptions(key: ApiKeyRecord = Depends(require_scope("webhooks:manage"))):
    subs = await webhook_service.list_subscriptions(_db(), key.tenant_id)
    for s in subs:
        s.pop("secret", None)
    return {"subscriptions": subs, "total": len(subs)}


@router.post("/test")
async def test_webhook(
    webhook_id: str = Query(...),
    key: ApiKeyRecord = Depends(require_scope("webhooks:manage")),
):
    result = await webhook_service.test_delivery(_db(), webhook_id, key.tenant_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    return result


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    key: ApiKeyRecord = Depends(require_scope("webhooks:manage")),
):
    ok = await webhook_service.delete_subscription(_db(), webhook_id, key.tenant_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    return {"status": "deleted", "webhook_id": webhook_id}
