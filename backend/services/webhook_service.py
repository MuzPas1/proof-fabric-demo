"""Webhook subscriptions + signed delivery for FEA lifecycle events."""
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.auth_models import WebhookSubscription

SUPPORTED_EVENTS = {"fea.generated", "fea.verified", "key.rotated", "test.event"}


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.webhooks.create_index("webhook_id", unique=True)
    await db.webhooks.create_index("tenant_id")


async def subscribe(
    db: AsyncIOMotorDatabase, tenant_id: str, url: str, events: List[str]
) -> WebhookSubscription:
    sub = WebhookSubscription(
        webhook_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        url=url,
        events=[e for e in events if e in SUPPORTED_EVENTS] or ["fea.generated"],
        secret=secrets.token_hex(24),
    )
    await db.webhooks.insert_one(sub.model_dump())
    return sub


async def list_subscriptions(db: AsyncIOMotorDatabase, tenant_id: str) -> List[dict]:
    cursor = db.webhooks.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def delete_subscription(db: AsyncIOMotorDatabase, webhook_id: str, tenant_id: str) -> bool:
    result = await db.webhooks.delete_one({"webhook_id": webhook_id, "tenant_id": tenant_id})
    return result.deleted_count > 0


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _deliver(url: str, secret: str, payload: dict) -> dict:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    signature = _sign(secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-PFP-Signature": f"sha256={signature}",
        "X-PFP-Event": payload.get("event", ""),
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, content=body, headers=headers)
            return {"url": url, "status": resp.status_code, "ok": resp.is_success}
    except Exception as e:
        return {"url": url, "status": 0, "ok": False, "error": str(e)}


async def dispatch_event(
    db: AsyncIOMotorDatabase, tenant_id: str, event: str, data: dict
) -> List[dict]:
    """Best-effort fan-out to all active subscriptions for the tenant+event."""
    payload = {
        "event": event,
        "tenant_id": tenant_id,
        "data": data,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
    }
    results = []
    cursor = db.webhooks.find(
        {"tenant_id": tenant_id, "status": "active", "events": event}, {"_id": 0}
    )
    async for sub in cursor:
        results.append(await _deliver(sub["url"], sub["secret"], payload))
    return results


async def test_delivery(db: AsyncIOMotorDatabase, webhook_id: str, tenant_id: str) -> Optional[dict]:
    doc = await db.webhooks.find_one(
        {"webhook_id": webhook_id, "tenant_id": tenant_id}, {"_id": 0}
    )
    if not doc:
        return None
    payload = {
        "event": "test.event",
        "tenant_id": tenant_id,
        "data": {"message": "PFP webhook test delivery"},
        "delivered_at": datetime.now(timezone.utc).isoformat(),
    }
    return await _deliver(doc["url"], doc["secret"], payload)
