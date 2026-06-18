"""FEA verification service.

VERIFICATION PROTOCOL:
1. Validate fea_version (must be supported)
2. Determine signature_version
3. Recompute fea_hash for integrity (constant-time comparison)
4. Canonicalize fea_payload
5. Verify signature with domain prefix (v2)
"""
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone, timedelta

from crypto.canonicalize import canonicalize_to_json
from crypto.hashing import compute_sha256
from crypto.signing import (
    verify_signature,
    get_public_key,
    normalize_signature,
    constant_time_compare,
    SIGNATURE_VERSION_V1,
    SIGNATURE_VERSION_V2,
    LEGACY_V2_PREFIX
)


# Supported FEA versions
SUPPORTED_FEA_VERSIONS = {"1.0", "1.1"}

# Timestamp validation bounds
MAX_FUTURE_SECONDS = 300  # 5 minutes
MAX_PAST_DAYS = 365  # 1 year


def validate_fea_version(fea_payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate fea_version is supported."""
    version = fea_payload.get('fea_version')
    if not version:
        return False, "Missing fea_version in payload"
    if version not in SUPPORTED_FEA_VERSIONS:
        return False, f"Unsupported fea_version: {version}. Supported: {SUPPORTED_FEA_VERSIONS}"
    return True, None


def validate_timestamp(timestamp_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validate timestamp is within acceptable bounds.
    - Not too far in the future (max 5 minutes)
    - Not too far in the past (max 1 year)
    """
    try:
        # Parse the normalized timestamp
        ts = timestamp_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(ts)
        now = datetime.now(timezone.utc)
        
        # Check future bound
        max_future = now + timedelta(seconds=MAX_FUTURE_SECONDS)
        if dt > max_future:
            return False, f"Timestamp too far in future: {timestamp_str}"
        
        # Check past bound
        min_past = now - timedelta(days=MAX_PAST_DAYS)
        if dt < min_past:
            return False, f"Timestamp too far in past: {timestamp_str}"
        
        return True, None
    except Exception as e:
        return False, f"Invalid timestamp format: {timestamp_str}"


def detect_signature_version(
    signature: str,
    fea_payload: Dict[str, Any],
    external_version: Optional[str] = None
) -> str:
    """Detect signature version with priority."""
    if external_version:
        return external_version
    if 'signature_version' in fea_payload:
        return fea_payload['signature_version']
    if signature.startswith(LEGACY_V2_PREFIX):
        return SIGNATURE_VERSION_V2
    return SIGNATURE_VERSION_V1


def clean_payload_for_verification(fea_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare payload for verification."""
    return fea_payload


def verify_fea(
    fea_payload: Dict[str, Any],
    signature: str,
    public_key_registry: Dict[str, bytes],
    external_signature_version: Optional[str] = None,
    skip_timestamp_validation: bool = False,
    key_algorithm: str = "Ed25519"
) -> Tuple[bool, Optional[str], str]:
    """
    Verify an FEA payload and signature.

    VERIFICATION STEPS:
    1. Validate fea_version
    2. Validate timestamp bounds (optional)
    3. Detect signature version
    4. Recompute fea_hash (constant-time comparison)
    5. Canonicalize fea_payload
    6. Algorithm-binding check (payload.algorithm == trusted key.algorithm)
    7. Verify signature with domain prefix under the resolved suite

    ``key_algorithm`` is the algorithm of the TRUSTED registry key. Defeats
    algorithm-confusion / downgrade attacks.

    Returns (valid, reason, signature_version) tuple.
    """
    from crypto import suites

    # Step 1: Validate fea_version
    valid, reason = validate_fea_version(fea_payload)
    if not valid:
        return False, reason, "unknown"

    # Step 2: Validate timestamp bounds
    if not skip_timestamp_validation:
        ts = fea_payload.get('transaction_summary', {}).get('timestamp')
        if ts:
            valid, reason = validate_timestamp(ts)
            if not valid:
                from core.config import settings
                if settings.ENFORCE_VERIFY_TIMESTAMP:
                    return False, reason, "unknown"
                # else advisory only (backward compatibility)

    # Step 3: Detect signature version
    sig_version = detect_signature_version(signature, fea_payload, external_signature_version)

    # Policy: reject legacy v1 signatures unless explicitly allowed
    if sig_version == SIGNATURE_VERSION_V1:
        from core.config import settings
        if not settings.ACCEPT_LEGACY_V1:
            return False, "Legacy v1 signatures are not accepted (set ACCEPT_LEGACY_V1=true to allow)", sig_version

    # Step 4: Clean payload
    clean_payload = clean_payload_for_verification(fea_payload)

    # Step 5: Extract and verify fea_hash with constant-time comparison
    claimed_hash = clean_payload.get('fea_hash')
    if not claimed_hash:
        return False, "Missing fea_hash in payload", sig_version

    payload_without_hash = {k: v for k, v in clean_payload.items() if k != 'fea_hash'}
    canonical_without_hash = canonicalize_to_json(payload_without_hash)
    computed_hash = compute_sha256(canonical_without_hash)

    # Use constant-time comparison to prevent timing attacks
    if not constant_time_compare(computed_hash, claimed_hash):
        return False, "Hash mismatch: payload has been tampered with", sig_version

    # Step 6: Canonicalize full payload
    canonical_full = canonicalize_to_json(clean_payload)

    # Step 7: Get public key
    public_key_id = clean_payload.get('public_key_id')
    if not public_key_id:
        return False, "Missing public_key_id in payload", sig_version

    public_key_bytes = public_key_registry.get(public_key_id)
    if not public_key_bytes:
        try:
            from crypto.signing import get_public_key_id as get_current_key_id
            if public_key_id == get_current_key_id():
                public_key_bytes = get_public_key()
            else:
                return False, f"Unknown public_key_id: {public_key_id}", sig_version
        except Exception:
            return False, f"Unknown public_key_id: {public_key_id}", sig_version

    # Step 7b: Algorithm-binding (anti-confusion / anti-downgrade).
    # The signed payload's algorithm (if present) MUST match the algorithm of
    # the trusted registry key; otherwise an attacker could claim a different
    # suite than the key actually uses.
    trusted_alg = suites.normalize_algorithm(key_algorithm)
    claimed_alg = suites.normalize_algorithm(fea_payload.get("algorithm", "Ed25519"))
    if sig_version == SIGNATURE_VERSION_V2 and claimed_alg != trusted_alg:
        return False, (
            f"Algorithm mismatch: payload claims {claimed_alg} but key is {trusted_alg} "
            "(algorithm-confusion defense)"
        ), sig_version

    # Step 8: Verify signature (with domain prefix for v2) under the suite.
    valid, reason = verify_signature(
        canonical_message=canonical_full,
        fea_hash=claimed_hash,
        signature=signature,
        public_key_bytes=public_key_bytes,
        signature_version=sig_version,
        algorithm=trusted_alg,
    )

    if valid:
        version_desc = "message-signed" if sig_version == SIGNATURE_VERSION_V2 else "hash-signed, legacy"
        return True, f"Signature valid ({sig_version}: {version_desc}, {trusted_alg})", sig_version

    return valid, reason, sig_version


async def verify_fea_with_registry(
    fea_payload: Dict[str, Any],
    signature: str,
    external_signature_version: Optional[str] = None
) -> Tuple[bool, Optional[str], str]:
    """
    Verify FEA using the persistent DB-backed key registry.
    Resolves public_key_id from the database, supporting retired keys.
    """
    public_key_id = fea_payload.get("public_key_id")
    if not public_key_id:
        return False, "Missing public_key_id in payload", "unknown"

    # Live revocation check — read status straight from DB (no stale cache).
    from services.key_service import get_key_by_id, get_key_status_live, get_public_key_bytes_by_id
    live_status = await get_key_status_live(public_key_id)
    if live_status == "revoked":
        return False, f"Key {public_key_id} has been revoked", "unknown"

    # Resolve key (+ algorithm + validity/tenant metadata) from the registry.
    key_info = await get_key_by_id(public_key_id)
    key_algorithm = "Ed25519"
    public_key_bytes = None
    if key_info is not None:
        key_algorithm = key_info.algorithm or "Ed25519"
        # Validity-window + ownership enforcement (federated keys). For legacy
        # platform keys these fields are absent → behaviour is unchanged.
        ok, reason = _check_key_constraints(key_info, fea_payload)
        if not ok:
            return False, reason, "unknown"
        public_key_bytes = await get_public_key_bytes_by_id(public_key_id)

    if not public_key_bytes:
        # Fallback: try current signing key (for backward compat)
        try:
            from crypto.signing import get_public_key_id as get_current_key_id, get_public_key
            if public_key_id == get_current_key_id():
                public_key_bytes = get_public_key()
        except Exception:
            pass

    if not public_key_bytes:
        return False, f"Unknown public_key_id: {public_key_id}", "unknown"

    registry = {public_key_id: public_key_bytes}
    return verify_fea(
        fea_payload, signature, registry, external_signature_version,
        skip_timestamp_validation=True, key_algorithm=key_algorithm,
    )


def _check_key_constraints(key_info, fea_payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Enforce federated-key constraints: validity window + tenant ownership.

    Backward compatible: legacy platform keys without these fields impose no
    constraint. Tenant isolation + validity windows are enforced WHENEVER the
    relevant fields are present on the key (independent of feature flags) — a
    federated key only carries them if it was registered through the federated
    flow, so this is a pure safety check.
    """
    # Tenant isolation: a tenant-owned (non-platform) key may only verify proofs
    # of that tenant.
    key_tenant = getattr(key_info, "tenant_id", None)
    owner = getattr(key_info, "owner", "platform")
    if owner not in (None, "platform") and key_tenant:
        payload_tenant = fea_payload.get("tenant_id")
        if payload_tenant and payload_tenant != key_tenant:
            return False, (
                f"Tenant isolation: key belongs to '{key_tenant}' "
                f"but proof is for tenant '{payload_tenant}'"
            )

    # Validity window enforced at the proof's issuance time (iat) when present.
    not_before = getattr(key_info, "not_before", None)
    not_after = getattr(key_info, "not_after", None)
    if not_before or not_after:
        iat = fea_payload.get("iat") or fea_payload.get("transaction_summary", {}).get("timestamp")
        if iat:
            try:
                t = datetime.fromisoformat(str(iat).replace("Z", "+00:00"))
                if not_before:
                    nb = datetime.fromisoformat(str(not_before).replace("Z", "+00:00"))
                    if t < nb:
                        return False, f"Key not yet valid (not_before {not_before})"
                if not_after:
                    na = datetime.fromisoformat(str(not_after).replace("Z", "+00:00"))
                    if t > na:
                        return False, f"Key expired (not_after {not_after})"
            except Exception:
                pass
    return True, None


def verify_fea_public(
    fea_payload: Dict[str, Any],
    signature: str,
    external_signature_version: Optional[str] = None
) -> Tuple[bool, Optional[str], str]:
    """
    Synchronous public verification — uses current key only.
    Prefer verify_fea_with_registry for DB-backed resolution.
    """
    try:
        from crypto.signing import get_public_key_id, get_public_key
        registry = {
            get_public_key_id(): get_public_key()
        }
        return verify_fea(fea_payload, signature, registry, external_signature_version, skip_timestamp_validation=True)
    except Exception as e:
        return False, f"Verification error: {str(e)}", "unknown"
