"""Pluggable inbound authentication / signature verification.

Each provider validates that an inbound request genuinely originates from an
authorized external system, using ONLY the integration's stored credential and
the request headers/body. Providers are pure functions of their inputs — no I/O.

Supported providers:
    hmac     -> HMAC-SHA256 over the raw request body with a shared secret
                (header value may be bare hex or ``sha256=<hex>``).
    api_key  -> opaque token in a configurable header, compared by SHA-256 hash.
    bearer   -> opaque token in ``Authorization: Bearer <token>``, hash-compared.
    none     -> no verification (explicit opt-in; discouraged for production).

All comparisons are constant-time. Adding a new scheme is a matter of adding a
branch here plus (optionally) a stored credential — no core change required.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Dict, Tuple


def _sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ct_eq(a: str, b: str) -> bool:
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


def verify(integration: dict, headers: Dict[str, str], raw_body: bytes) -> Tuple[bool, str]:
    """Return (ok, reason). ``headers`` keys MUST be lowercased by the caller."""
    provider = (integration.get("auth_provider") or "hmac").lower()

    if provider == "none":
        return True, "ok"

    if provider == "hmac":
        secret = integration.get("hmac_secret")
        if not secret:
            return False, "integration missing HMAC secret"
        header_name = (integration.get("signature_header") or "x-pfp-signature").lower()
        provided = headers.get(header_name, "")
        if provided.startswith("sha256="):
            provided = provided[len("sha256="):]
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if provided and _ct_eq(provided.strip(), expected):
            return True, "ok"
        return False, "invalid HMAC signature"

    if provider == "api_key":
        header_name = (integration.get("token_header") or "x-integration-key").lower()
        provided = headers.get(header_name, "")
        if provided and _ct_eq(_sha256_hex(provided.strip()), integration.get("token_hash", "")):
            return True, "ok"
        return False, "invalid or missing API key"

    if provider == "bearer":
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            if token and _ct_eq(_sha256_hex(token), integration.get("token_hash", "")):
                return True, "ok"
        return False, "invalid or missing bearer token"

    return False, f"unknown auth provider: {provider}"
