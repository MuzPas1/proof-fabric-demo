"""Federated key registry — customer/partner-owned public keys with PoP.

Onboarding flow (proof-of-possession):
  1. register: caller submits a public key (raw b64 / JWK / SPKI PEM) + algorithm
     + optional validity window. The key is stored with status="pending" and a
     single-use challenge nonce is returned.
  2. confirm: caller signs ``PFP_POP_V1:: + challenge`` with the matching private
     key and submits the signature. The server verifies it against the submitted
     public key (proving control of the private key) and flips the key to
     status="active", pop_verified=True.

Tenant isolation: a federated key is OWNED by the registering tenant; at FEA
verification time a non-platform key may only verify proofs of its own tenant
(enforced in verification_service._check_key_constraints).

All cryptographic primitives reuse the suite layer — no new crypto here.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from crypto import suites
from models.key_registry import PublicKeyInfo
from services import key_service

POP_DOMAIN_PREFIX = "PFP_POP_V1::"
POP_TTL_SECONDS = 900  # 15 minutes


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.key_registry.create_index([("tenant_id", 1), ("status", 1)])
    # Auto-expire stale PoP challenges.
    await db.pop_challenges.create_index("expires_at", expireAfterSeconds=0)
    await db.pop_challenges.create_index("public_key_id", unique=True)


def _kid_from_raw(raw: bytes) -> str:
    return "fed_key_" + hashlib.sha256(raw).hexdigest()[:16]


def _normalize_to_raw(algorithm: str, key_format: str, public_key: Optional[str], jwk: Optional[dict]) -> Tuple[str, bytes, Optional[dict]]:
    """Return (algorithm, raw_public_key_bytes, jwk_or_None). Raises ValueError."""
    key_format = (key_format or "raw").lower()
    if key_format == "jwk":
        if not jwk:
            raise ValueError("jwk is required when key_format=jwk")
        alg, raw = suites.jwk_to_public_key_bytes(jwk)
        return alg, raw, jwk
    if key_format in ("spki-pem", "pem", "spki"):
        if not public_key:
            raise ValueError("public_key (base64 PEM/DER) is required for spki-pem")
        alg, raw = suites.spki_pem_to_public_key_bytes(base64.b64decode(public_key))
        return alg, raw, None
    # raw
    if not public_key:
        raise ValueError("public_key (base64 raw) is required for key_format=raw")
    alg = suites.normalize_algorithm(algorithm)
    raw = base64.b64decode(public_key)
    if not suites.validate_public_key_bytes(alg, raw):
        raise ValueError(f"Invalid {alg} public key bytes")
    return alg, raw, None


async def register_federated_key(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    *,
    algorithm: str,
    key_format: str,
    public_key: Optional[str],
    jwk: Optional[dict],
    owner: str,
    label: Optional[str],
    not_before: Optional[str],
    not_after: Optional[str],
) -> Tuple[PublicKeyInfo, str, str]:
    """Register a pending federated key + issue a PoP challenge.

    Returns (key_info, challenge, expires_at_iso).
    """
    alg, raw, original_jwk = _normalize_to_raw(algorithm, key_format, public_key, jwk)
    if not suites.is_supported(alg):
        raise ValueError(f"Unsupported algorithm: {alg}")
    if owner not in ("customer", "partner"):
        raise ValueError("owner must be 'customer' or 'partner'")

    kid = _kid_from_raw(raw)
    raw_b64 = base64.b64encode(raw).decode("ascii")

    existing = await db.key_registry.find_one({"public_key_id": kid}, {"_id": 0})
    if existing and existing.get("status") == "active":
        raise ValueError("Key already registered and active")

    key_info = PublicKeyInfo(
        public_key_id=kid,
        public_key=raw_b64,
        algorithm=alg,
        created_at=datetime.now(timezone.utc).isoformat(),
        status="pending",
        key_format=(key_format or "raw").lower(),
        jwk=original_jwk,
        tenant_id=tenant_id,
        owner=owner,
        not_before=not_before,
        not_after=not_after,
        pop_verified=False,
        label=label,
    )
    await db.key_registry.update_one(
        {"public_key_id": kid}, {"$set": key_info.model_dump()}, upsert=True
    )
    # Refresh cache (so subsequent reads see the pending key metadata).
    key_service.add_key_to_registry(key_info)

    challenge = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=POP_TTL_SECONDS)
    await db.pop_challenges.update_one(
        {"public_key_id": kid},
        {"$set": {
            "public_key_id": kid,
            "tenant_id": tenant_id,
            "challenge": challenge,
            "algorithm": alg,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return key_info, challenge, expires_at.isoformat()


async def confirm_federated_key(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    public_key_id: str,
    pop_signature_b64: str,
) -> PublicKeyInfo:
    """Verify proof-of-possession and activate the key. Raises ValueError."""
    key_doc = await db.key_registry.find_one({"public_key_id": public_key_id}, {"_id": 0})
    if not key_doc:
        raise ValueError("Unknown public_key_id")
    if key_doc.get("tenant_id") != tenant_id:
        raise ValueError("Key does not belong to this tenant")
    if key_doc.get("status") == "active":
        return PublicKeyInfo(**key_doc)
    if key_doc.get("status") != "pending":
        raise ValueError(f"Key is not pending (status={key_doc.get('status')})")

    challenge_doc = await db.pop_challenges.find_one({"public_key_id": public_key_id}, {"_id": 0})
    if not challenge_doc:
        raise ValueError("PoP challenge expired or not found — re-register the key")

    alg = key_doc["algorithm"]
    raw_pub = base64.b64decode(key_doc["public_key"])
    message = (POP_DOMAIN_PREFIX + challenge_doc["challenge"]).encode("utf-8")
    try:
        signature = base64.b64decode(pop_signature_b64)
    except Exception:
        raise ValueError("Malformed pop_signature encoding")

    ok, reason = suites.verify(alg, raw_pub, message, signature)
    if not ok:
        raise ValueError(f"Proof-of-possession failed: {reason}")

    await db.key_registry.update_one(
        {"public_key_id": public_key_id},
        {"$set": {"status": "active", "pop_verified": True}},
    )
    await db.pop_challenges.delete_one({"public_key_id": public_key_id})

    updated = await db.key_registry.find_one({"public_key_id": public_key_id}, {"_id": 0})
    info = PublicKeyInfo(**updated)
    key_service.add_key_to_registry(info)
    return info
