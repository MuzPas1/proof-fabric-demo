"""
Independent-verifiable signed proof artifact (Ed25519).

This service is ADDITIVE — it does not modify the existing proof generation /
verification logic used by `/api/demo/issue` and `/api/demo/verify/{proof_id}`.
It produces a standalone, downloadable JSON artifact that can be verified
anywhere without querying internal systems.

Artifact schema (v1):
    {
      "version": 1,
      "transaction_id": "...",
      "user_id": "...",
      "amount": "...",
      "compliance": { "kyc": "Pass|Fail", "aml": "Pass|Fail",
                      "limits": "Within allowed range|Exceeded" },
      "timestamp": "ISO-8601 UTC (…Z)",
      "proof_id": "<sha256 of canonical JSON excluding proof_id+signature>",
      "algorithm": "Ed25519",
      "kid": "<key id>",
      "signature": "<base64 Ed25519 over canonical JSON excluding signature>"
    }

Signing / verification rules:
  * Canonical JSON uses lexicographically sorted keys, UTF-8, no whitespace.
  * `proof_id`  = SHA-256 of canonical JSON of the base payload
                  (all fields EXCLUDING `proof_id` and `signature`).
  * `signature` = Ed25519( canonical JSON of base payload + {proof_id} ),
                  base64 encoded. A domain prefix `PFP_ARTIFACT_V1::` is
                  prepended to the signing bytes to prevent cross-protocol
                  signature reuse.
  * Timestamp must be ISO-8601 UTC and MUST NOT be in the future by more
    than `MAX_FUTURE_SKEW_SECONDS` (= 300s / 5 minutes).
  * Both `proof_id` comparison and signature verification use
    constant-time primitives.
  * `kid` must resolve to a key in the registry whose status is
    `active` or `retired`. `revoked` keys are rejected.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

from crypto.canonicalize import canonicalize_to_json, normalize_timestamp
from crypto.signing import (
    get_signing_key,
    get_public_key_id,
    get_public_key_b64,
)
from services.key_service import get_key_by_id, register_key


ARTIFACT_VERSION = 1
ARTIFACT_ALGORITHM = "Ed25519"
ARTIFACT_DOMAIN_PREFIX = b"PFP_ARTIFACT_V1::"
MAX_FUTURE_SKEW_SECONDS = 300  # 5 minutes

REQUIRED_TOP_FIELDS = {
    "version",
    "transaction_id",
    "user_id",
    "amount",
    "compliance",
    "timestamp",
    "proof_id",
    "algorithm",
    "kid",
    "signature",
}
REQUIRED_COMPLIANCE_FIELDS = {"kyc", "aml", "limits"}
COMPLIANCE_ALLOWED_VALUES = {
    "kyc": {"Pass", "Fail"},
    "aml": {"Pass", "Fail"},
    "limits": {"Within allowed range", "Exceeded"},
}


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _normalize_amount(amount: Any) -> str:
    if isinstance(amount, str):
        amount = amount.strip().replace(",", "")
        if amount == "":
            raise ValueError("amount is empty")
    try:
        return f"{float(amount):.2f}"
    except (TypeError, ValueError):
        raise ValueError(f"invalid amount: {amount!r}")


def _normalize_timestamp(ts: str) -> str:
    raw = ts.strip()
    normalized = normalize_timestamp(raw)
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except Exception as e:
        raise ValueError(f"invalid timestamp: {ts!r}") from e
    return normalized


def _normalize_compliance(c: Dict[str, Any]) -> Dict[str, str]:
    missing = REQUIRED_COMPLIANCE_FIELDS - set(c.keys())
    extra = set(c.keys()) - REQUIRED_COMPLIANCE_FIELDS
    if missing:
        raise ValueError(f"compliance missing fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"compliance has unexpected fields: {sorted(extra)}")
    out = {}
    for field in ("kyc", "aml", "limits"):
        value = c[field]
        if not isinstance(value, str):
            raise ValueError(f"compliance.{field} must be a string")
        value = value.strip()
        if value not in COMPLIANCE_ALLOWED_VALUES[field]:
            raise ValueError(
                f"compliance.{field} must be one of {sorted(COMPLIANCE_ALLOWED_VALUES[field])}"
            )
        out[field] = value
    return out


def _base_payload(
    transaction_id: str,
    user_id: str,
    amount: Any,
    compliance: Dict[str, Any],
    timestamp: str,
    kid: str,
) -> Dict[str, Any]:
    """Normalized base payload used for proof_id hashing (excludes proof_id + signature)."""
    return {
        "version": ARTIFACT_VERSION,
        "transaction_id": transaction_id.strip(),
        "user_id": user_id.strip().lower(),
        "amount": _normalize_amount(amount),
        "compliance": _normalize_compliance(compliance),
        "timestamp": _normalize_timestamp(timestamp),
        "algorithm": ARTIFACT_ALGORITHM,
        "kid": kid,
    }


# ---------------------------------------------------------------------------
# Key management (reuses existing key_registry collection)
# ---------------------------------------------------------------------------

async def ensure_demo_signing_key(db: AsyncIOMotorDatabase) -> str:
    """
    Ensure an active Ed25519 signing key is registered for the demo artifact.
    Reuses the existing server private key (from PRIVATE_KEY env) and registers
    its public key in the key registry. Returns the active kid.
    """
    kid = get_public_key_id()
    existing = await get_key_by_id(kid)
    if existing is None:
        await register_key(kid, get_public_key_b64(), status="active")
    return kid


async def _get_public_key_and_status(
    db: AsyncIOMotorDatabase, kid: str
) -> Tuple[Optional[bytes], Optional[str]]:
    key_info = await get_key_by_id(kid)
    if key_info is None:
        return None, None
    return base64.b64decode(key_info.public_key), key_info.status


# ---------------------------------------------------------------------------
# Sign
# ---------------------------------------------------------------------------

def _sign_bytes(canonical_json: str) -> str:
    signing_key: SigningKey = get_signing_key()
    message = ARTIFACT_DOMAIN_PREFIX + canonical_json.encode("utf-8")
    signed = signing_key.sign(message)
    return base64.b64encode(signed.signature).decode("ascii")


def _verify_bytes(canonical_json: str, signature_b64: str, public_key: bytes) -> bool:
    try:
        vk = VerifyKey(public_key)
        message = ARTIFACT_DOMAIN_PREFIX + canonical_json.encode("utf-8")
        signature = base64.b64decode(signature_b64)
        vk.verify(message, signature)
        return True
    except (BadSignatureError, Exception):
        return False


async def build_signed_artifact(
    db: AsyncIOMotorDatabase,
    transaction_id: str,
    user_id: str,
    amount: Any,
    compliance: Dict[str, Any],
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and sign a new proof artifact. Raises ValueError on invalid input."""
    kid = await ensure_demo_signing_key(db)
    if timestamp is None:
        timestamp = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        )

    base = _base_payload(transaction_id, user_id, amount, compliance, timestamp, kid)

    # proof_id = sha256 of canonical(base)
    base_canonical = canonicalize_to_json(base)
    proof_id = hashlib.sha256(base_canonical.encode("utf-8")).hexdigest()

    # signature = sign( canonical(base + proof_id) )
    signing_payload = {**base, "proof_id": proof_id}
    signing_canonical = canonicalize_to_json(signing_payload)
    signature = _sign_bytes(signing_canonical)

    return {**signing_payload, "signature": signature}


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


async def verify_signed_artifact(
    db: AsyncIOMotorDatabase, artifact: Any
) -> Dict[str, Any]:
    """
    Verify a signed artifact independently (no lookup of the original record).

    Returns: {
      valid: bool,
      reason: str | None,
      status: "valid_compliant" | "valid_non_compliant" | "invalid",
      extracted: {transaction_id, compliance, timestamp} | None
    }
    """
    # ---- Structural & schema validation ----
    if not isinstance(artifact, dict):
        return _invalid("Artifact must be a JSON object")

    keys = set(artifact.keys())
    missing = REQUIRED_TOP_FIELDS - keys
    if missing:
        return _invalid(f"Missing required fields: {sorted(missing)}")
    extra = keys - REQUIRED_TOP_FIELDS
    if extra:
        return _invalid(f"Unexpected fields: {sorted(extra)}")

    if artifact["version"] != ARTIFACT_VERSION:
        return _invalid(f"Unsupported version: {artifact['version']!r}")
    if artifact["algorithm"] != ARTIFACT_ALGORITHM:
        return _invalid(f"Unsupported algorithm: {artifact['algorithm']!r}")

    # ---- Normalize & re-derive base payload ----
    try:
        compliance = _normalize_compliance(artifact["compliance"])
        base = {
            "version": ARTIFACT_VERSION,
            "transaction_id": str(artifact["transaction_id"]).strip(),
            "user_id": str(artifact["user_id"]).strip().lower(),
            "amount": _normalize_amount(artifact["amount"]),
            "compliance": compliance,
            "timestamp": _normalize_timestamp(str(artifact["timestamp"])),
            "algorithm": ARTIFACT_ALGORITHM,
            "kid": str(artifact["kid"]),
        }
    except ValueError as e:
        return _invalid(f"Normalization failed: {e}")

    # ---- Timestamp skew ----
    try:
        ts_dt = _parse_iso(base["timestamp"])
    except Exception:
        return _invalid("Invalid timestamp format")
    skew = (ts_dt - datetime.now(timezone.utc)).total_seconds()
    if skew > MAX_FUTURE_SKEW_SECONDS:
        return _invalid(
            f"Timestamp is in the future by {int(skew)}s (max skew {MAX_FUTURE_SKEW_SECONDS}s)"
        )

    # ---- Recompute proof_id & constant-time compare ----
    base_canonical = canonicalize_to_json(base)
    expected_proof_id = hashlib.sha256(base_canonical.encode("utf-8")).hexdigest()
    provided_proof_id = str(artifact["proof_id"]).strip().lower()

    if not hmac.compare_digest(expected_proof_id, provided_proof_id):
        return _invalid("proof_id does not match canonical payload hash")

    # ---- Resolve key via kid ----
    public_key, status = await _get_public_key_and_status(db, base["kid"])
    if public_key is None:
        return _invalid(f"Unknown kid: {base['kid']!r}")
    if status == "revoked":
        return _invalid(f"Key {base['kid']!r} has been revoked")
    if status not in ("active", "retired"):
        return _invalid(f"Key {base['kid']!r} has unsupported status: {status!r}")

    # ---- Verify signature ----
    signing_payload = {**base, "proof_id": expected_proof_id}
    signing_canonical = canonicalize_to_json(signing_payload)
    sig_ok = _verify_bytes(signing_canonical, str(artifact["signature"]), public_key)
    if not sig_ok:
        return _invalid("Signature verification failed")

    # ---- Success ----
    is_compliant = (
        compliance["kyc"] == "Pass"
        and compliance["aml"] == "Pass"
        and compliance["limits"] == "Within allowed range"
    )
    return {
        "valid": True,
        "reason": None,
        "status": "valid_compliant" if is_compliant else "valid_non_compliant",
        "extracted": {
            "transaction_id": base["transaction_id"],
            "compliance": compliance,
            "timestamp": base["timestamp"],
            "kid": base["kid"],
            "key_status": status,
        },
    }


def _invalid(reason: str) -> Dict[str, Any]:
    return {"valid": False, "reason": reason, "status": "invalid", "extracted": None}
