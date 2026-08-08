"""Inbound Event Ingestion service.

Orchestrates: integration lifecycle (CRUD + credentials + monitoring) and the
inbound event flow (auth -> normalize -> validate -> map -> EXISTING proof
pipeline -> audit). It intentionally reuses the existing single-artifact
generator (``routes.fea_routes._generate_one``) so the core proof engine,
idempotency, replay protection and signing paths are unchanged.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time as _time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.ingestion import auth_providers
from core.ingestion.adapters import AdapterError, get_adapter
from models.fea import GenerateFEARequest
from models.ingestion import CommonEvent, IntegrationConfig

logger = logging.getLogger("pfp.ingestion.service")


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


def _is_connectivity_test(payload) -> bool:
    """Detect a provider connectivity/handshake ping (not a real business event).

    These carry NO domain identifier by design and are sent when an operator
    clicks "Test webhook" in a provider dashboard. Examples:
      - Cashfree: ``{"data": {"test_object": ...}, "type": "WEBHOOK"}``
      - Generic:  a top-level ``type`` of ``webhook`` / ``test`` / ``ping``.
    We acknowledge them (200) so onboarding succeeds, without minting a proof.
    """
    if not isinstance(payload, dict):
        return False
    data = payload.get("data")
    if isinstance(data, dict) and "test_object" in data:
        return True
    t = str(payload.get("type") or payload.get("event_type") or "").strip().lower()
    return t in ("webhook", "test", "ping", "test_webhook", "connectivity_test")


def _build_event_descriptor(event: CommonEvent, integration: dict, payload) -> dict:
    """Non-sensitive, privacy-preserving descriptor recorded ALONGSIDE the proof
    (NOT part of the signed payload, NOT a cryptographic commitment). Enables a
    provider-aware verification experience without storing any PII — document
    names, subjects, senders/recipients and account ids remain hash-only inside
    the signed ``metadata_hash``. Only workflow-level, non-personal fields are
    persisted here (provider, category, event type, event source, status,
    timestamp, external id) plus any explicitly display-safe attributes.

    Provider taxonomy (category + event source) is resolved from the generic
    ``core.ingestion.registry`` so it lives in exactly one place.
    """
    from core.ingestion import registry

    scheme = ((integration.get("auth_config") or {}).get("signature_scheme") or "").lower()
    name = integration.get("name") or integration.get("slug")
    prov = registry.resolve(scheme or (event.provider or ""), name)

    provider = event.provider or prov.label
    provider_category = event.provider_category or prov.category
    event_source = event.event_source or prov.default_event_source
    # Inbound authentication mechanism actually used to verify this event
    # (falls back to the provider's default policy). Presentation only.
    auth_provider = (integration.get("auth_provider") or prov.default_auth_method)
    auth_method = registry.auth_method_label(auth_provider)

    status = None
    event_type = None
    if isinstance(payload, dict):
        for k in ("status", "state", "event_status"):
            v = payload.get(k)
            if isinstance(v, (str, int)) and str(v).strip():
                status = str(v)[:64]
                break
        # Prefer the provider's descriptive event field (e.g. DocuSign
        # ``event``="envelope-completed") over the generic normalized type.
        for k in ("event", "event_type", "eventType", "type", "action"):
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                event_type = v[:128]
                break
    status = status or (str(event.status)[:64] if event.status else None)
    event_type = event_type or (str(event.event_type)[:128] if event.event_type else None)

    attributes = {
        str(k)[:64]: str(v)[:256]
        for k, v in (event.display_attributes or {}).items()
        if v not in (None, "")
    }
    return {
        "provider": str(provider)[:64],
        "provider_kind": scheme or prov.id,
        "provider_category": provider_category,
        "event_type": event_type,
        "event_source": event_source,
        "auth_method": auth_method,
        "status": status,
        "occurred_at": event.occurred_at,
        "external_id": event.external_id,
        "source": event.source,
        "attributes": attributes,
    }


async def _persist_event_descriptor(db, fea_id: str, event: CommonEvent, integration: dict, payload) -> None:
    """Additively attach the non-sensitive descriptor to the stored proof. Best
    effort — a failure here must never affect proof issuance."""
    try:
        await db.feas.update_one(
            {"fea_id": fea_id},
            {"$set": {"event_descriptor": _build_event_descriptor(event, integration, payload)}},
        )
    except Exception:
        logger.warning("failed to persist event_descriptor for fea_id=%s", fea_id)


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.integrations.create_index("integration_id", unique=True)
    await db.integrations.create_index("slug", unique=True)
    await db.integrations.create_index("tenant_id")
    await db.inbound_events.create_index("integration_id")
    await db.inbound_events.create_index("received_at")
    await db.inbound_nonces.create_index([("integration_id", 1), ("replay_key", 1)], unique=True)
    await db.inbound_nonces.create_index("expires_at", expireAfterSeconds=0)


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------
def _issue_credential(auth_provider: str) -> Tuple[Optional[str], dict]:
    """Return (raw_secret_shown_once, stored_fields). None raw for externally-configured providers."""
    if auth_provider in ("hmac", "hmac_sha256", "hmac_sha1"):
        secret = f"whsec_{secrets.token_hex(32)}"
        return secret, {"hmac_secret": secret, "token_hash": None, "basic_password_hash": None}
    if auth_provider in ("api_key", "bearer"):
        token = f"pfp_evt_{secrets.token_hex(24)}"
        return token, {"hmac_secret": None, "token_hash": _sha256_hex(token), "basic_password_hash": None}
    if auth_provider == "basic":
        password = f"pfp_{secrets.token_hex(18)}"
        return password, {"hmac_secret": None, "token_hash": None, "basic_password_hash": _sha256_hex(password)}
    # jwt / oauth2 / mtls / custom / none -> externally configured (no PFP-minted credential)
    return None, {"hmac_secret": None, "token_hash": None, "basic_password_hash": None}


# ---------------------------------------------------------------------------
# Integration lifecycle
# ---------------------------------------------------------------------------
async def create_integration(
    db: AsyncIOMotorDatabase, *, name: str, slug: str, tenant_id: str,
    adapter: str = "generic", auth_provider: str = "hmac",
    default_currency: str = "USD", field_map: Optional[Dict[str, str]] = None,
    description: Optional[str] = None, created_by: Optional[str] = None,
    auth_config: Optional[Dict] = None, require_timestamp: bool = False,
    timestamp_tolerance_seconds: int = 300, replay_protection: bool = False,
    secret: Optional[str] = None,
) -> Tuple[IntegrationConfig, Optional[str]]:
    if await db.integrations.find_one({"slug": slug}):
        raise IngestionError(f"integration slug already exists: {slug}", 409)
    raw, cred = _issue_credential(auth_provider)
    # External-webhook HMAC schemes (e.g. Cashfree/Stripe/Slack) sign with the
    # provider's OWN secret supplied via ``secret`` — do NOT mint a PFP secret.
    if secret and auth_provider in ("hmac", "hmac_sha256", "hmac_sha1"):
        raw, cred = None, {"hmac_secret": None, "token_hash": None, "basic_password_hash": None}
    cfg = IntegrationConfig(
        integration_id=str(uuid.uuid4()), slug=slug, name=name, description=description,
        tenant_id=tenant_id, adapter=adapter, auth_provider=auth_provider,
        auth_config=auth_config or {}, require_timestamp=require_timestamp,
        timestamp_tolerance_seconds=timestamp_tolerance_seconds, replay_protection=replay_protection,
        external_secret=secret, default_currency=default_currency.upper(),
        field_map=field_map or {}, created_by=created_by, updated_at=_now(), **cred,
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
    if "secret" in clean:  # externally-provided secret is stored redacted
        clean["external_secret"] = clean.pop("secret")
    clean["updated_at"] = _now()
    await db.integrations.update_one({"integration_id": integration_id}, {"$set": clean})
    result = await get_integration(db, integration_id, tenant_id)
    # Persistence visibility: print the EXACTLY-persisted auth_config immediately
    # after save so operators can confirm (e.g.) that signature_scheme=docusign
    # actually landed in the DB for this integration_id/slug.
    logger.info(
        "integration saved: id=%s slug=%s persisted auth_config=%s",
        integration_id, result.get("slug"), json.dumps(result.get("auth_config") or {}),
    )
    return result


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
    elif status == "test":
        pass  # connectivity/handshake ping — neither accepted nor rejected
    else:
        inc["total_rejected"] = 1
    set_fields = {"last_event_at": _now(), "last_error": error}
    await db.integrations.update_one({"integration_id": integration_id}, {"$inc": inc, "$set": set_fields})
    await db.inbound_events.insert_one({
        "event_log_id": str(uuid.uuid4()),
        "integration_id": integration_id,
        "event_type": event.event_type if event else ("connectivity.test" if status == "test" else None),
        "external_id": event.external_id if event else None,
        "status": status,
        "fea_id": fea_id,
        "error": error,
        "received_at": _now(),
    })


# ---------------------------------------------------------------------------
# Inbound processing (public entry point)
# ---------------------------------------------------------------------------
async def _validate_tenant_binding(db, slug: str, doc: dict) -> None:
    """Defense-in-depth: guarantee an inbound request resolves to exactly one
    active tenant and can never cross a tenant boundary.

    Slugs are globally unique (unique index), so this re-asserts that invariant
    at request time and refuses to serve a slug that is ambiguous or whose owning
    tenant is missing or explicitly deactivated.
    """
    tenant_id = doc.get("tenant_id")
    if not tenant_id:
        raise IngestionError("integration has no tenant binding", 403)

    # Re-assert the slug -> single-tenant invariant (never trust a stale read).
    matches = await db.integrations.count_documents({"slug": slug})
    if matches != 1:
        raise IngestionError("integration slug is ambiguous across tenants", 409)

    # Refuse ingestion for a tenant that has been explicitly deactivated.
    tdoc = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0, "status": 1})
    if tdoc and str(tdoc.get("status", "active")).lower() in ("disabled", "suspended", "revoked", "inactive"):
        raise IngestionError("owning tenant is not active", 403)


async def process_inbound(db, slug: str, raw_body: bytes, headers: Dict[str, str]) -> dict:
    """Authenticate, normalize, validate, and issue a Proof Artifact for one event."""
    import json

    doc = await db.integrations.find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise IngestionError("integration not found", 404)
    if not doc.get("enabled", False) or doc.get("status") != "active":
        raise IngestionError("integration is disabled", 403)

    await _validate_tenant_binding(db, slug, doc)

    # Read-path visibility: print the integration_id + auth_config the inbound
    # webhook actually loaded from the DB (fresh read; no cache). Compare this
    # id/auth_config against the "integration saved" log above — if they differ,
    # the webhook is hitting a DIFFERENT integration record than the one edited
    # (e.g. a duplicate slug or the DocuSign endpoint URL points elsewhere).
    logger.info(
        "inbound webhook loaded integration: slug=%s id=%s auth_provider=%s auth_config=%s",
        slug, doc.get("integration_id"), doc.get("auth_provider"),
        json.dumps(doc.get("auth_config") or {}),
    )

    lower_headers = {k.lower(): v for k, v in headers.items()}

    result = await asyncio.to_thread(auth_providers.authenticate, doc, lower_headers, raw_body)
    if not result.ok:
        await _record_event(db, doc["integration_id"], None, "rejected", None, f"auth: {result.reason}")
        raise IngestionError(f"authentication failed: {result.reason}", 401)

    # --- cross-cutting: timestamp validation ---
    tol = int(doc.get("timestamp_tolerance_seconds") or 300)
    if doc.get("require_timestamp") and result.timestamp is None:
        await _record_event(db, doc["integration_id"], None, "rejected", None, "timestamp: missing")
        raise IngestionError("authentication failed: missing timestamp", 401)
    if result.timestamp is not None and abs(_time.time() - result.timestamp) > tol:
        await _record_event(db, doc["integration_id"], None, "rejected", None, "timestamp: stale")
        raise IngestionError("authentication failed: stale request", 401)

    # --- cross-cutting: replay protection ---
    if doc.get("replay_protection"):
        from datetime import timedelta
        from pymongo.errors import DuplicateKeyError
        replay_key = result.replay_key or hashlib.sha256(raw_body).hexdigest()
        try:
            await db.inbound_nonces.insert_one({
                "integration_id": doc["integration_id"],
                "replay_key": replay_key,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=max(tol, 600)),
            })
        except DuplicateKeyError:
            await _record_event(db, doc["integration_id"], None, "rejected", None, "replay: duplicate")
            raise IngestionError("authentication failed: replay detected", 409)

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        await _record_event(db, doc["integration_id"], None, "rejected", None, "invalid JSON body")
        raise IngestionError("request body must be valid JSON", 400)

    # Provider connectivity/handshake ping (e.g. Cashfree "Test webhook"): the
    # signature already verified above, but there is no business event to prove.
    # Acknowledge it so onboarding succeeds; do NOT mint a Proof Artifact.
    if _is_connectivity_test(payload):
        await _record_event(db, doc["integration_id"], None, "test", None, None)
        return {"status": "test_acknowledged", "integration": slug,
                "detail": "connectivity test received; no proof issued"}

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
    await _persist_event_descriptor(db, response.fea_id, event, doc, payload)
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
        await _persist_event_descriptor(db, response.fea_id, event, doc, payload)
        await _record_event(db, integration_id, event, "accepted", response.fea_id, None)
        result["fea_id"] = response.fea_id
    return result


# ---------------------------------------------------------------------------
# Connection self-test / Test Webhook Simulator (generic, all providers)
# ---------------------------------------------------------------------------
def _sample_iso(offset_min: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=offset_min)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _sample_payload(doc: dict) -> dict:
    """Provider-specific sample event for a connection self-test.

    Shaped to normalize cleanly through the integration's configured adapter.
    Values are obviously synthetic and carry a random id so repeated tests never
    collide on idempotency/replay.
    """
    adapter = doc.get("adapter", "generic")
    uniq = secrets.token_hex(3)
    if adapter == "tarabut":
        return {
            "tarabutEventType": "payment_completed",
            "externalId": f"SIMPAY{uniq}",
            "occurredAt": _sample_iso(1),
            "status": "COMPLETED",
            "amount": "10.95",
            "currency": "BHD",
            "providerId": "BLUE",
            "eventSource": "Webhook",
            "attributes": {
                "Bank": "Blue Bank (Sandbox)",
                "Merchant Reference": f"ORD-{uniq}",
                "Customer Reference": f"CUST-{uniq}",
            },
            "sensitive": {
                "payerToken": f"payer-{uniq}",
                "destinationAccount": "BHD1",
            },
        }
    if adapter == "jira":
        return {
            "timestamp": int(_time.time() * 1000),
            "webhookEvent": "jira:issue_updated",
            "issue_event_type_name": "issue_generic",
            "user": {"accountId": f"sim-{uniq}", "displayName": "Sample User"},
            "issue": {
                "id": f"9000{uniq}",
                "key": f"KAN-{int(uniq, 16) % 90 + 1}",
                "fields": {
                    "summary": "Sample release-readiness issue",
                    "issuetype": {"name": "Task"},
                    "project": {"key": "KAN", "name": "My Kanban Space"},
                    "status": {"name": "In Progress"},
                    "priority": {"name": "High"},
                    "labels": ["sample", "connection-test"],
                    "duedate": "2026-12-31",
                    "created": _sample_iso(120),
                    "updated": _sample_iso(1),
                },
            },
            "changelog": {"id": uniq, "items": [{"field": "status", "fromString": "To Do", "toString": "In Progress"}]},
        }
    return {
        "type": "sample.event",
        "id": f"SIM-{uniq}",
        "timestamp": _sample_iso(1),
        "actor": "sim-system",
        "subject": "sim-subject",
        "amount": 25000,
        "currency": "USD",
    }


def _sign_sample(doc: dict, raw_body: bytes):
    """Produce request headers that satisfy the integration's configured inbound
    auth for a self-test, mirroring how each provider signs. Returns
    ``(headers, mode)`` where mode is ``signed`` (real auth will run), ``open``
    (no auth configured) or ``skip`` (credential not reproducible server-side,
    e.g. a hashed api_key/bearer/basic token). Never modifies the auth framework."""
    provider = (doc.get("auth_provider") or "hmac").lower()
    if provider == "none":
        return {}, "open"
    if not provider.startswith("hmac"):
        return {}, "skip"
    secret = doc.get("external_secret") or doc.get("hmac_secret")
    if not secret:
        return {}, "skip"
    cfg = doc.get("auth_config") or {}
    scheme = (cfg.get("signature_scheme") or "plain").lower()
    algo = hashlib.sha1 if provider == "hmac_sha1" else hashlib.sha256
    body = raw_body.decode("utf-8", "replace")
    enc = (cfg.get("signature_encoding") or ("base64" if scheme == "cashfree" else "hex")).lower()
    headers: Dict[str, str] = {}

    def _digest(signed_str: str, encoding: str = enc) -> str:
        d = hmac.new(secret.encode("utf-8"), signed_str.encode("utf-8"), algo)
        return base64.b64encode(d.digest()).decode("ascii") if encoding == "base64" else d.hexdigest()

    if scheme == "stripe":
        t = str(int(_time.time()))
        headers[cfg.get("signature_header", "stripe-signature")] = f"t={t},v1={_digest(f'{t}.{body}', 'hex')}"
    elif scheme == "slack":
        t = str(int(_time.time()))
        headers[cfg.get("timestamp_header", "x-slack-request-timestamp")] = t
        headers[cfg.get("signature_header", "x-slack-signature")] = "v0=" + _digest(f"v0:{t}:{body}", "hex")
    elif scheme == "cashfree":
        t = str(int(_time.time() * 1000))
        headers[cfg.get("timestamp_header", "x-webhook-timestamp")] = t
        headers[cfg.get("signature_header", "x-webhook-signature")] = _digest(f"{t}{body}", "base64")
    elif scheme == "docusign":
        d = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        headers[cfg.get("signature_header", "x-docusign-signature-1")] = base64.b64encode(d).decode("ascii")
    else:  # plain (Jira / GitHub / generic PFP-signed)
        header = cfg.get("signature_header") or doc.get("signature_header") or "x-pfp-signature"
        headers[header] = f"{cfg.get('signature_prefix', '')}{_digest(body)}"
    return headers, "signed"


async def simulate_connection(db, integration_id: str, tenant_id: Optional[str]) -> dict:
    """Generic connection self-test: build + sign a provider sample event, run it
    through the REAL auth + adapter + proof + verification path, and report each
    step. Issues a genuine (sample) Proof Artifact; recorded as a ``test`` event
    so accepted/rejected counters are unaffected."""
    from services.verification_service import verify_fea_with_registry

    doc = await _get_doc(db, integration_id, tenant_id)
    payload = _sample_payload(doc)
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers, mode = _sign_sample(doc, raw_body)
    lower_headers = {k.lower(): v for k, v in headers.items()}

    steps = [{"key": "connection", "label": "Connection", "status": "success",
              "detail": f"Reached inbound endpoint /api/ingest/{doc['slug']}"}]

    if mode == "skip":
        steps.append({"key": "authentication", "label": "Authentication", "status": "skipped",
                      "detail": "This auth method stores a non-reversible credential, so the "
                                "signature is simulated. Adapter, proof and verification are still validated."})
    else:
        result = await asyncio.to_thread(auth_providers.authenticate, doc, lower_headers, raw_body)
        if not result.ok:
            steps.append({"key": "authentication", "label": "Authentication", "status": "failed", "detail": result.reason})
            return {"ok": False, "steps": steps, "fea_id": None, "sample_event_type": None}
        steps.append({"key": "authentication", "label": "Authentication", "status": "success",
                      "detail": "Webhook signature verified"})

    try:
        event = get_adapter(doc.get("adapter", "generic")).normalize(payload, doc)
    except AdapterError as e:
        steps.append({"key": "proof", "label": "Proof generation", "status": "failed", "detail": f"normalize: {e}"})
        return {"ok": False, "steps": steps, "fea_id": None, "sample_event_type": None}

    request = map_to_request(event, doc)
    from routes.fea_routes import _generate_one
    try:
        response = await _generate_one(db, request, doc["tenant_id"])
    except Exception as e:
        detail = getattr(e, "detail", None) or str(e)
        steps.append({"key": "proof", "label": "Proof generation", "status": "failed", "detail": detail})
        return {"ok": False, "steps": steps, "fea_id": None, "sample_event_type": event.event_type}

    await _persist_event_descriptor(db, response.fea_id, event, doc, payload)
    await db.feas.update_one({"fea_id": response.fea_id}, {"$set": {"simulated": True}})
    await _record_event(db, integration_id, event, "test", response.fea_id, None)
    steps.append({"key": "proof", "label": "Proof generation", "status": "success", "detail": response.fea_id})

    fea_doc = await db.feas.find_one({"fea_id": response.fea_id}, {"_id": 0})
    valid = False
    if fea_doc:
        valid, _, _ = await verify_fea_with_registry(
            fea_doc["fea_payload"], fea_doc["signature"], fea_doc.get("signature_version", "v1"))
    steps.append({"key": "verification", "label": "Independent verification",
                  "status": "success" if valid else "failed",
                  "detail": "Signature verified against the key registry" if valid else "Verification failed"})

    return {"ok": all(s["status"] in ("success", "skipped") for s in steps),
            "fea_id": response.fea_id, "steps": steps, "sample_event_type": event.event_type,
            "tenant_id": doc.get("tenant_id")}
