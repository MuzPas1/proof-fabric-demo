"""Inbound Event Ingestion service.

Orchestrates: integration lifecycle (CRUD + credentials + monitoring) and the
inbound event flow (auth -> normalize -> validate -> map -> EXISTING proof
pipeline -> audit). It intentionally reuses the existing single-artifact
generator (``routes.fea_routes._generate_one``) so the core proof engine,
idempotency, replay protection and signing paths are unchanged.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.ingestion import auth_providers
from core.ingestion.adapters import AdapterError, get_adapter
from models.fea import GenerateFEARequest
from models.ingestion import CommonEvent, IntegrationConfig


class IngestionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokenize(value: Optional[str]) -> str:
    """Privacy-preserving tokenization — only a hash reaches the signed payload."""
    return hashlib.sha256((value if value else "n/a").encode("utf-8")).hexdigest()


def _sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.integrations.create_index("integration_id", unique=True)
    await db.integrations.create_index("slug", unique=True)
    await db.integrations.create_index("tenant_id")
    await db.inbound_events.create_index("integration_id")
    await db.inbound_events.create_index("received_at")


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------
def _issue_credential(auth_provider: str) -> Tuple[Optional[str], dict]:
    """Return (raw_secret_shown_once, stored_fields). None raw for 'none'."""
    if auth_provider == "hmac":
        secret = f"whsec_{secrets.token_hex(32)}"
        return secret, {"hmac_secret": secret, "token_hash": None}
    if auth_provider in ("api_key", "bearer"):
        token = f"pfp_evt_{secrets.token_hex(24)}"
        return token, {"hmac_secret": None, "token_hash": _sha256_hex(token)}
    return None, {"hmac_secret": None, "token_hash": None}


# ---------------------------------------------------------------------------
# Integration lifecycle
# ---------------------------------------------------------------------------
async def create_integration(
    db: AsyncIOMotorDatabase, *, name: str, slug: str, tenant_id: str,
    adapter: str = "generic", auth_provider: str = "hmac",
    default_currency: str = "USD", field_map: Optional[Dict[str, str]] = None,
    description: Optional[str] = None, created_by: Optional[str] = None,
) -> Tuple[IntegrationConfig, Optional[str]]:
    if await db.integrations.find_one({"slug": slug}):
        raise IngestionError(f"integration slug already exists: {slug}", 409)
    raw, cred = _issue_credential(auth_provider)
    cfg = IntegrationConfig(
        integration_id=str(uuid.uuid4()), slug=slug, name=name, description=description,
        tenant_id=tenant_id, adapter=adapter, auth_provider=auth_provider,
        default_currency=default_currency.upper(), field_map=field_map or {},
        created_by=created_by, updated_at=_now(), **cred,
    )
    await db.integrations.insert_one(cfg.model_dump())
    return cfg, raw


async def _get_doc(db, integration_id: str, tenant_id: Optional[str]) -> dict:
    query = {"integration_id": integration_id}
    if tenant_id:
        query["tenant_id"] = tenant_id
    doc = await db.integrations.find_one(query, {"_id": 0})
    if not doc:
        raise IngestionError("integration not found", 404)
    return doc


async def list_integrations(db, tenant_id: Optional[str]) -> List[dict]:
    query = {"tenant_id": tenant_id} if tenant_id else {}
    cursor = db.integrations.find(query, {"_id": 0}).sort("created_at", -1)
    return [IntegrationConfig(**doc).public() async for doc in cursor]


async def get_integration(db, integration_id: str, tenant_id: Optional[str]) -> dict:
    return IntegrationConfig(**await _get_doc(db, integration_id, tenant_id)).public()


async def update_integration(db, integration_id: str, tenant_id: Optional[str], updates: dict) -> dict:
    await _get_doc(db, integration_id, tenant_id)
    clean = {k: v for k, v in updates.items() if v is not None}
    if "default_currency" in clean:
        clean["default_currency"] = clean["default_currency"].upper()
    clean["updated_at"] = _now()
    await db.integrations.update_one({"integration_id": integration_id}, {"$set": clean})
    return await get_integration(db, integration_id, tenant_id)


async def set_enabled(db, integration_id: str, tenant_id: Optional[str], enabled: bool) -> dict:
    await _get_doc(db, integration_id, tenant_id)
    await db.integrations.update_one(
        {"integration_id": integration_id},
        {"$set": {"enabled": enabled, "status": "active" if enabled else "disabled", "updated_at": _now()}},
    )
    return await get_integration(db, integration_id, tenant_id)


async def rotate_secret(db, integration_id: str, tenant_id: Optional[str]) -> Tuple[dict, Optional[str]]:
    doc = await _get_doc(db, integration_id, tenant_id)
    raw, cred = _issue_credential(doc.get("auth_provider", "hmac"))
    cred["updated_at"] = _now()
    await db.integrations.update_one({"integration_id": integration_id}, {"$set": cred})
    return await get_integration(db, integration_id, tenant_id), raw


async def delete_integration(db, integration_id: str, tenant_id: Optional[str]) -> None:
    await _get_doc(db, integration_id, tenant_id)
    await db.integrations.delete_one({"integration_id": integration_id})


async def get_stats(db, integration_id: str, tenant_id: Optional[str]) -> dict:
    doc = await _get_doc(db, integration_id, tenant_id)
    return {
        "integration_id": doc["integration_id"], "slug": doc["slug"],
        "enabled": doc.get("enabled", False), "status": doc.get("status"),
        "health": "healthy" if doc.get("enabled") else "disabled",
        "total_received": doc.get("total_received", 0),
        "total_accepted": doc.get("total_accepted", 0),
        "total_rejected": doc.get("total_rejected", 0),
        "last_event_at": doc.get("last_event_at"),
        "last_error": doc.get("last_error"),
    }


async def list_events(db, integration_id: str, tenant_id: Optional[str], limit: int = 50) -> List[dict]:
    await _get_doc(db, integration_id, tenant_id)
    cursor = (db.inbound_events.find({"integration_id": integration_id}, {"_id": 0})
              .sort("received_at", -1).limit(min(limit, 200)))
    return [doc async for doc in cursor]


# ---------------------------------------------------------------------------
# Normalization + mapping
# ---------------------------------------------------------------------------
def map_to_request(event: CommonEvent, integration: dict) -> GenerateFEARequest:
    """Map a normalized CommonEvent onto the existing proof-generation contract.

    Non-financial events use amount=0 and a default currency. Actor/subject are
    tokenized (hashed) so raw identifiers never enter the signed payload.
    """
    slug = integration.get("slug", "event")
    idem = event.idempotency_key or f"{slug}:{event.external_id}:{event.occurred_at}"
    metadata = dict(event.attributes or {})
    metadata.update({
        "event_type": event.event_type,
        "source": event.source or slug,
        "integration": slug,
    })
    return GenerateFEARequest(
        idempotency_key=idem[:256],
        transaction_id=event.external_id,
        timestamp=event.occurred_at,
        amount=event.amount,
        currency=event.currency,
        payer_id=_tokenize(event.actor or event.source or slug),
        payee_id=_tokenize(event.subject or event.event_type),
        metadata=metadata,
    )


async def _record_event(db, integration_id: str, event: Optional[CommonEvent],
                        status: str, fea_id: Optional[str], error: Optional[str]) -> None:
    inc = {"total_received": 1}
    if status == "accepted":
        inc["total_accepted"] = 1
    else:
        inc["total_rejected"] = 1
    set_fields = {"last_event_at": _now(), "last_error": error}
    await db.integrations.update_one({"integration_id": integration_id}, {"$inc": inc, "$set": set_fields})
    await db.inbound_events.insert_one({
        "event_log_id": str(uuid.uuid4()),
        "integration_id": integration_id,
        "event_type": event.event_type if event else None,
        "external_id": event.external_id if event else None,
        "status": status,
        "fea_id": fea_id,
        "error": error,
        "received_at": _now(),
    })


# ---------------------------------------------------------------------------
# Inbound processing (public entry point)
# ---------------------------------------------------------------------------
async def process_inbound(db, slug: str, raw_body: bytes, headers: Dict[str, str]) -> dict:
    """Authenticate, normalize, validate, and issue a Proof Artifact for one event."""
    import json

    doc = await db.integrations.find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise IngestionError("integration not found", 404)
    if not doc.get("enabled", False) or doc.get("status") != "active":
        raise IngestionError("integration is disabled", 403)

    lower_headers = {k.lower(): v for k, v in headers.items()}

    ok, reason = auth_providers.verify(doc, lower_headers, raw_body)
    if not ok:
        await _record_event(db, doc["integration_id"], None, "rejected", None, f"auth: {reason}")
        raise IngestionError(f"authentication failed: {reason}", 401)

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        await _record_event(db, doc["integration_id"], None, "rejected", None, "invalid JSON body")
        raise IngestionError("request body must be valid JSON", 400)

    try:
        event = get_adapter(doc.get("adapter", "generic")).normalize(payload, doc)
    except AdapterError as e:
        await _record_event(db, doc["integration_id"], None, "rejected", None, f"normalize: {e}")
        raise IngestionError(f"event validation failed: {e}", 422)

    request = map_to_request(event, doc)
    from routes.fea_routes import _generate_one  # reuse existing pipeline (no core change)
    try:
        response = await _generate_one(db, request, doc["tenant_id"])
    except Exception as e:
        detail = getattr(e, "detail", None) or str(e)
        await _record_event(db, doc["integration_id"], event, "rejected", None, f"proof: {detail}")
        raise
    await _record_event(db, doc["integration_id"], event, "accepted", response.fea_id, None)
    return {"status": "accepted", "integration": slug, "event_id": event.external_id, "fea_id": response.fea_id}


async def dry_run(db, integration_id: str, tenant_id: Optional[str], payload: dict, issue: bool) -> dict:
    """Admin test hook: normalize a sample payload; optionally issue a real proof."""
    doc = await _get_doc(db, integration_id, tenant_id)
    event = get_adapter(doc.get("adapter", "generic")).normalize(payload, doc)
    request = map_to_request(event, doc)
    preview = request.model_dump()
    result = {"normalized_event": event.model_dump(), "mapped_request": preview, "fea_id": None}
    if issue:
        from routes.fea_routes import _generate_one
        response = await _generate_one(db, request, doc["tenant_id"])
        await _record_event(db, integration_id, event, "accepted", response.fea_id, None)
        result["fea_id"] = response.fea_id
    return result
