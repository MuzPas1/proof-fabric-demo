"""Auth0 Identity provider — turns an authenticated Auth0 session into a
privacy-preserving "Identity Authenticated" Proof Artifact.

Architectural note: this module contains NO proof/crypto logic. It normalizes the
Auth0 userinfo into the vendor-neutral ``CommonEvent`` and reuses the EXACT same
pipeline every other provider uses (``ingestion_service.map_to_request`` ->
``routes.fea_routes._generate_one`` -> ``_build_event_descriptor``). The Proof
Engine has no knowledge that this event originated from Auth0.

Privacy: PFP never stores passwords, tokens, id_tokens, JWT payloads or raw
claims. Sensitive identifiers (email, session id, provider user id) are stored
ONLY as one-way hashes (folded into the signed ``metadata_hash`` commitment).
Only opaque, non-personal metadata (provider, identity provider, issuer,
client id, opaque subject) is kept in the unsigned descriptor for display.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone

from core.config import settings
from models.ingestion import CommonEvent
from services import ingestion_service

logger = logging.getLogger("pfp.auth0.service")


def _hash(value) -> str:
    return hashlib.sha256((str(value) if value else "n/a").encode("utf-8")).hexdigest()


def _identity_provider(sub: str) -> str:
    """Auth0 ``sub`` is ``<connection>|<id>`` (e.g. ``google-oauth2|123``)."""
    if sub and "|" in sub:
        return sub.split("|", 1)[0]
    return "auth0"


def _mask_subject(sub: str) -> str:
    """Privacy-preserving display of the authenticated principal: keep the
    identity-provider connection intact but mask the raw account id so the
    externally-readable descriptor never exposes the provider's raw subject."""
    if not sub:
        return "unknown"
    conn, _, ident = sub.partition("|")
    if not ident:
        conn, ident = "", sub
    if len(ident) <= 4:
        masked = "•" * len(ident)
    else:
        masked = ident[:2] + "•" * (len(ident) - 4) + ident[-2:]
    return f"{conn}|{masked}" if conn else masked


async def generate_identity_proof(db, userinfo: dict, token: dict | None = None) -> str:
    """Normalize the Auth0 identity event and issue a Proof Artifact via the
    shared pipeline. Returns the fea_id."""
    sub = userinfo.get("sub") or "unknown"
    email = userinfo.get("email")
    idp = _identity_provider(sub)
    issuer = f"https://{settings.AUTH0_DOMAIN}/"
    client_id = settings.AUTH0_CLIENT_ID
    sid = userinfo.get("sid")
    now = datetime.now(timezone.utc).isoformat()
    # Unique, unguessable per-authentication event id (no PII).
    nonce = secrets.token_hex(8)
    external_id = "auth0-" + hashlib.sha256(
        f"{sub}|{sid or ''}|{now}|{nonce}".encode("utf-8")
    ).hexdigest()[:24]

    # Display-safe metadata for the verification UI (unsigned descriptor).
    display_attributes = {
        "Authenticated User": _mask_subject(str(sub)),
        "Identity Provider": idp,
        "Application": settings.AUTH0_APP_NAME,
        "Issuer": issuer,
        "Client ID": client_id,
    }

    event = CommonEvent(
        event_type="Identity Authenticated",
        external_id=external_id,
        occurred_at=now,
        source="auth0",
        actor=str(sub),
        subject=client_id,
        amount=0,
        currency="USD",
        provider="Auth0",
        provider_category="Identity",
        event_source="OAuth",
        status="Authenticated",
        display_attributes=display_attributes,
        # These enter the signed payload as a single one-way metadata_hash
        # commitment — raw values are never stored.
        attributes={
            "event_type": "Identity Authenticated",
            "identity_provider": idp,
            "issuer": issuer,
            "client_id": client_id,
            "email_hash": _hash(email),
            "session_hash": _hash(sid or external_id),
            "provider_user_id_hash": _hash(sub),
        },
    )

    integration = {
        "slug": "auth0",
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "name": "Auth0",
        "auth_config": {},
    }
    request = ingestion_service.map_to_request(event, integration)
    from routes.fea_routes import _generate_one  # reuse existing pipeline (no core change)
    response = await _generate_one(db, request, settings.DEFAULT_TENANT_ID)
    await ingestion_service._persist_event_descriptor(db, response.fea_id, event, integration, {})
    logger.info("auth0 identity proof issued: fea_id=%s idp=%s", response.fea_id, idp)
    return response.fea_id
