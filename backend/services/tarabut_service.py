"""Tarabut Gateway (Open Banking) service — additive, isolated orchestration.

Turns authenticated Tarabut provider events (inbound payment webhooks AND
outbound OAuth2 API responses) into PFP Proof Artifacts using the EXISTING proof
pipeline (``routes.fea_routes._generate_one``) via the shared ingestion mapping
and the ``tarabut`` event adapter. No core proof-engine code is modified and no
Tarabut-specific proof engine is introduced.

Credentials are read from environment configuration (never hardcoded). Outbound
API methods raise ``TarabutError`` with a clear message until the operator
supplies sandbox credentials, so the module is safe to load with empty config.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.config import settings
from core.ingestion.adapters import AdapterError, get_adapter
from core.ingestion.tarabut_client import TarabutClient, TarabutError

logger = logging.getLogger("pfp.tarabut")

# Every authenticated Tarabut event PFP can produce a Proof Artifact for.
SUPPORTED_PROOF_EVENTS: List[str] = [
    "intent_created", "connect_journey_started", "account_linked",
    "consent_granted", "consent_updated", "consent_revoked", "consent_expired",
    "consent_retrieved", "redirect_completed", "callback_received",
    "account_retrieved", "account_updated", "balance_retrieved", "balance_refreshed",
    "transaction_retrieved", "transaction_refreshed", "enriched_transaction_retrieved",
    "beneficiaries_retrieved", "direct_debits_retrieved", "scheduled_payments_retrieved",
    "standing_orders_retrieved",
    "payment_created", "payment_processing", "payment_completed", "payment_settled",
    "payment_received", "payment_failed", "payment_expired", "payment_refunded",
    "income_verification_requested", "income_verification_completed",
    "salary_verification_requested", "salary_verification_completed",
    "categorisation_requested", "categorisation_completed",
]

# Documented Tarabut APIs wired into the outbound client.
SUPPORTED_APIS: List[Dict[str, str]] = [
    {"area": "Auth", "name": "OAuth2 Access Token (client credentials)"},
    {"area": "Auth", "name": "Payments OAuth Token (client credentials)"},
    {"area": "Connect", "name": "Create Intent"},
    {"area": "Connect", "name": "Providers"},
    {"area": "Consent", "name": "Get All Consents"},
    {"area": "Consent", "name": "Get Consent Details"},
    {"area": "Consent", "name": "Revoke Consent"},
    {"area": "Consent", "name": "Create Consent Dashboard"},
    {"area": "Account Information", "name": "Get Accounts"},
    {"area": "Account Information", "name": "Get Account Balances"},
    {"area": "Account Information", "name": "Refresh Account Balances"},
    {"area": "Account Information", "name": "Get Account Transactions (enriched)"},
    {"area": "Account Information", "name": "Get Account Raw Transactions"},
    {"area": "Account Information", "name": "Refresh Account Transactions"},
    {"area": "Regular Payments", "name": "Beneficiaries"},
    {"area": "Regular Payments", "name": "Direct Debits"},
    {"area": "Regular Payments", "name": "Scheduled Payments"},
    {"area": "Regular Payments", "name": "Standing Orders"},
    {"area": "Payments", "name": "Create Payment (PIR)"},
    {"area": "Payments", "name": "Get Payment Status"},
    {"area": "Payments", "name": "Create Partner Payment"},
    {"area": "Payments", "name": "Get Partner Payment Status"},
]


class TarabutNotConfigured(TarabutError):
    pass


# ---------------------------------------------------------------------------
# Configuration / status (never returns secrets)
# ---------------------------------------------------------------------------
def is_oauth_configured() -> bool:
    return bool(settings.TARABUT_CLIENT_ID and settings.TARABUT_CLIENT_SECRET)


def is_payments_configured() -> bool:
    return bool(settings.TARABUT_PAYMENT_CLIENT_ID and settings.TARABUT_PAYMENT_CLIENT_SECRET)


def build_client() -> TarabutClient:
    if not is_oauth_configured():
        raise TarabutNotConfigured(
            "Tarabut sandbox credentials are not configured. Set TARABUT_CLIENT_ID and "
            "TARABUT_CLIENT_SECRET (and, for payments, TARABUT_PAYMENT_CLIENT_ID/SECRET)."
        )
    return TarabutClient(
        client_id=settings.TARABUT_CLIENT_ID,
        client_secret=settings.TARABUT_CLIENT_SECRET,
        redirect_uri=settings.TARABUT_REDIRECT_URI,
        region=settings.TARABUT_REGION,
        payment_client_id=settings.TARABUT_PAYMENT_CLIENT_ID,
        payment_client_secret=settings.TARABUT_PAYMENT_CLIENT_SECRET,
    )


async def get_status(db) -> dict:
    """Non-secret status for the admin console."""
    integrations = []
    try:
        cursor = db.integrations.find({"adapter": "tarabut"}, {"_id": 0})
        async for doc in cursor:
            cfg = doc.get("auth_config") or {}
            webhook_key = bool(cfg.get("public_key") or cfg.get("rsa_public_keys") or cfg.get("jwks_url"))
            integrations.append({
                "integration_id": doc.get("integration_id"),
                "slug": doc.get("slug"),
                "enabled": doc.get("enabled", False),
                "inbound_url": f"/api/ingest/{doc.get('slug')}",
                "webhook_key_configured": webhook_key,
                "accept_unverified": str(cfg.get("accept_unverified", "")).lower() in ("1", "true", "yes"),
                "total_accepted": doc.get("total_accepted", 0),
            })
    except Exception:
        logger.warning("failed to list tarabut integrations for status")
    return {
        "region": settings.TARABUT_REGION,
        "oauth_configured": is_oauth_configured(),
        "payments_configured": is_payments_configured(),
        "integrations": integrations,
        "supported_apis": SUPPORTED_APIS,
        "supported_proof_events": SUPPORTED_PROOF_EVENTS,
    }


# ---------------------------------------------------------------------------
# Event -> Proof Artifact (reuses the existing pipeline)
# ---------------------------------------------------------------------------
def _synthetic_integration(tenant_id: str) -> dict:
    """A minimal in-memory integration used when no stored Tarabut integration
    exists yet (e.g. outbound-only proofs). Carries no credentials."""
    return {
        "integration_id": None,
        "slug": "tarabut",
        "name": "Tarabut",
        "adapter": "tarabut",
        "tenant_id": tenant_id,
        "auth_provider": "rsa_sha256",
        "auth_config": {"tarabut_region": settings.TARABUT_REGION},
        "default_currency": "BHD",
    }


async def _find_integration(db, tenant_id: Optional[str]) -> Optional[dict]:
    query: Dict[str, Any] = {"adapter": "tarabut"}
    if tenant_id:
        query["tenant_id"] = tenant_id
    return await db.integrations.find_one(query, {"_id": 0})


async def record_event_proof(db, event: dict, *, integration: Optional[dict] = None,
                             tenant_id: Optional[str] = None) -> dict:
    """Normalize a Tarabut event and issue a Proof Artifact via the EXISTING
    pipeline. Works with a stored integration (updates its counters) or, when
    none exists, a synthetic integration (proof only, no counter update)."""
    from services.ingestion_service import map_to_request, _persist_event_descriptor, _record_event
    from routes.fea_routes import _generate_one

    resolved_tenant = tenant_id or settings.DEFAULT_TENANT_ID
    doc = integration or await _find_integration(db, resolved_tenant) or _synthetic_integration(resolved_tenant)
    doc_tenant = doc.get("tenant_id") or resolved_tenant

    try:
        normalized = get_adapter("tarabut").normalize(event, doc)
    except AdapterError as e:
        raise TarabutError(f"event validation failed: {e}")

    request = map_to_request(normalized, doc)
    response = await _generate_one(db, request, doc_tenant)
    await _persist_event_descriptor(db, response.fea_id, normalized, doc, event)
    if doc.get("integration_id"):
        await _record_event(db, doc["integration_id"], normalized, "accepted", response.fea_id, None)
    return {
        "fea_id": response.fea_id,
        "event_type": normalized.event_type,
        "external_id": normalized.external_id,
        "status": normalized.status,
    }


# ---------------------------------------------------------------------------
# Outbound API -> event envelope -> Proof Artifact (requires live credentials)
# ---------------------------------------------------------------------------
def _envelope(event_type: str, external_id: str, *, status: Optional[str] = None,
              amount: Any = None, currency: Optional[str] = None, provider_id: Optional[str] = None,
              event_source: str = "API", attributes: Optional[dict] = None,
              sensitive: Optional[dict] = None) -> dict:
    env: Dict[str, Any] = {
        "tarabutEventType": event_type, "externalId": str(external_id),
        "eventSource": event_source, "attributes": attributes or {}, "sensitive": sensitive or {},
    }
    if status is not None:
        env["status"] = status
    if amount is not None:
        env["amount"] = amount
    if currency:
        env["currency"] = currency
    if provider_id:
        env["providerId"] = provider_id
    return env


async def prove_create_intent(db, *, user: dict, provider_id: str, tenant_id: Optional[str] = None,
                              redirect_url: Optional[str] = None, language: Optional[str] = None,
                              purpose_statement: Optional[str] = None,
                              permissions_list: Optional[List[str]] = None) -> dict:
    client = build_client()
    result = await client.create_intent(user=user, provider_id=provider_id, redirect_url=redirect_url,
                                         language=language, purpose_statement=purpose_statement,
                                         permissions_list=permissions_list)
    env = _envelope("intent_created", result.get("intentId", "intent"), provider_id=provider_id,
                    attributes={"Expiry": result.get("expiry")},
                    sensitive={"customerUserId": (user or {}).get("customerUserId")})
    proof = await record_event_proof(db, env, tenant_id=tenant_id)
    return {"tarabut": result, "proof": proof}


async def prove_get_accounts(db, *, customer_user_id: str, tenant_id: Optional[str] = None) -> dict:
    client = build_client()
    result = await client.get_accounts(customer_user_id)
    proofs = []
    for acct in (result.get("accounts") or []):
        env = _envelope("account_retrieved", acct.get("accountId", "account"),
                        status=(acct.get("consents") or [{}])[0].get("status"),
                        provider_id=acct.get("providerId"),
                        attributes={"Account Product Type": acct.get("accountProductType"),
                                    "Last Updated": acct.get("lastUpdatedDateTime")},
                        sensitive={"account": acct.get("accountId"),
                                   "accountHolderName": acct.get("accountHolderName"),
                                   "identifiers": (acct.get("identifiers") or {}).get("value")})
        proofs.append(await record_event_proof(db, env, tenant_id=tenant_id))
    return {"tarabut": result, "proofs": proofs}


async def prove_revoke_consent(db, *, consent_id: str, customer_user_id: str,
                               tenant_id: Optional[str] = None) -> dict:
    client = build_client()
    result = await client.revoke_consent(consent_id, customer_user_id)
    env = _envelope("consent_revoked", result.get("id", consent_id),
                    status=result.get("status", "REVOKED"), event_source="API",
                    sensitive={"customerUserId": customer_user_id})
    proof = await record_event_proof(db, env, tenant_id=tenant_id)
    return {"tarabut": result, "proof": proof}


async def prove_payment_status(db, *, payment_id: str, tenant_id: Optional[str] = None) -> dict:
    client = build_client()
    result = await client.get_payment(payment_id)
    env = _envelope(f"payment_{str(result.get('status', 'status')).lower()}",
                    result.get("id", payment_id), status=result.get("status"),
                    amount=result.get("amount"), currency=result.get("currency"),
                    event_source="API",
                    attributes={"Bank": result.get("bank"),
                                "Merchant Reference": result.get("merchantReference"),
                                "Customer Reference": result.get("customerReference")},
                    sensitive={"destinationAccount": result.get("destinationAccount")})
    proof = await record_event_proof(db, env, tenant_id=tenant_id)
    return {"tarabut": result, "proof": proof}
