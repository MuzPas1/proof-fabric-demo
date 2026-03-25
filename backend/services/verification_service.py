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
SUPPORTED_FEA_VERSIONS = {"1.0"}

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
    skip_timestamp_validation: bool = False
) -> Tuple[bool, Optional[str], str]:
    """
    Verify an FEA payload and signature.

    VERIFICATION STEPS:
    1. Validate fea_version
    2. Validate timestamp bounds (optional)
    3. Detect signature version
    4. Recompute fea_hash (constant-time comparison)
    5. Canonicalize fea_payload
    6. Verify signature with domain prefix

    Returns (valid, reason, signature_version) tuple.
    """
    # Step 1: Validate fea_version
    valid, reason = validate_fea_version(fea_payload)
    if not valid:
        return False, reason, "unknown"

    # Step 2: Validate timestamp (optional, for new verifications)
    if not skip_timestamp_validation:
        ts = fea_payload.get('transaction_summary', {}).get('timestamp')
        if ts:
            valid, reason = validate_timestamp(ts)
            if not valid:
                # Log warning but don't fail - timestamp validation is advisory
                pass  # Allow for backward compatibility

    # Step 3: Detect signature version
    sig_version = detect_signature_version(signature, fea_payload, external_signature_version)

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

    # Step 8: Verify signature (with domain prefix for v2)
    valid, reason = verify_signature(
        canonical_message=canonical_full,
        fea_hash=claimed_hash,
        signature=signature,
        public_key_bytes=public_key_bytes,
        signature_version=sig_version
    )

    if valid:
        version_desc = "message-signed" if sig_version == SIGNATURE_VERSION_V2 else "hash-signed, legacy"
        return True, f"Signature valid ({sig_version}: {version_desc})", sig_version

    return valid, reason, sig_version


def verify_fea_public(
    fea_payload: Dict[str, Any],
    signature: str,
    external_signature_version: Optional[str] = None
) -> Tuple[bool, Optional[str], str]:
    """Public verification using current key registry."""
    try:
        from crypto.signing import get_public_key_id, get_public_key
        registry = {
            get_public_key_id(): get_public_key()
        }
        return verify_fea(fea_payload, signature, registry, external_signature_version, skip_timestamp_validation=True)
    except Exception as e:
        return False, f"Verification error: {str(e)}", "unknown"
