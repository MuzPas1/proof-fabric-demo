"""FEA verification service.

VERIFICATION PROTOCOL:
1. Extract fea_payload (full payload including fea_hash, signature_version)
2. Integrity check: recompute fea_hash
3. Signature verification based on signature_version field
4. Backward compatibility: accept legacy v2: prefix signatures
"""
from typing import Dict, Any, Tuple, Optional

from crypto.canonicalize import canonicalize_to_json
from crypto.hashing import compute_sha256
from crypto.signing import (
    verify_signature,
    get_public_key,
    detect_signature_version,
    normalize_signature,
    SIGNATURE_VERSION_V1,
    SIGNATURE_VERSION_V2
)


def verify_fea(
    fea_payload: Dict[str, Any],
    signature: str,
    public_key_registry: Dict[str, bytes]
) -> Tuple[bool, Optional[str]]:
    """
    Verify an FEA payload and signature.

    VERIFICATION STEPS:
    1. Extract fea_hash from payload
    2. Recompute hash (canonicalize without fea_hash, SHA-256)
    3. Compare computed hash with fea_payload.fea_hash
    4. Detect signature version (from signature_version field or legacy prefix)
    5. Canonicalize FULL payload (including fea_hash)
    6. Verify signature based on version

    Returns (valid, reason) tuple.
    """
    # Step 1: Extract claimed hash
    claimed_hash = fea_payload.get('fea_hash')
    if not claimed_hash:
        return False, "Missing fea_hash in payload"

    # Step 2: Recompute hash (without fea_hash field)
    payload_without_hash = {k: v for k, v in fea_payload.items() if k != 'fea_hash'}
    canonical_without_hash = canonicalize_to_json(payload_without_hash)
    computed_hash = compute_sha256(canonical_without_hash)

    # Step 3: Verify hash integrity
    if computed_hash != claimed_hash:
        return False, "Hash mismatch: payload has been tampered with"

    # Step 4: Detect signature version
    sig_version = detect_signature_version(signature, fea_payload)

    # Step 5: Canonicalize FULL payload (including fea_hash)
    canonical_full = canonicalize_to_json(fea_payload)

    # Step 6: Get public key
    public_key_id = fea_payload.get('public_key_id')
    if not public_key_id:
        return False, "Missing public_key_id in payload"

    public_key_bytes = public_key_registry.get(public_key_id)
    if not public_key_bytes:
        try:
            from crypto.signing import get_public_key_id as get_current_key_id
            if public_key_id == get_current_key_id():
                public_key_bytes = get_public_key()
            else:
                return False, f"Unknown public_key_id: {public_key_id}"
        except Exception:
            return False, f"Unknown public_key_id: {public_key_id}"

    # Step 7: Verify signature based on version
    valid, reason = verify_signature(
        canonical_message=canonical_full,
        fea_hash=claimed_hash,
        signature=signature,
        public_key_bytes=public_key_bytes,
        signature_version=sig_version
    )

    if valid:
        version_desc = "message-signed" if sig_version == SIGNATURE_VERSION_V2 else "hash-signed, legacy"
        return True, f"Signature valid ({sig_version}: {version_desc})"

    return valid, reason


def verify_fea_public(
    fea_payload: Dict[str, Any],
    signature: str
) -> Tuple[bool, Optional[str]]:
    """
    Public verification using current key registry.
    """
    try:
        from crypto.signing import get_public_key_id, get_public_key
        registry = {
            get_public_key_id(): get_public_key()
        }
        return verify_fea(fea_payload, signature, registry)
    except Exception as e:
        return False, f"Verification error: {str(e)}"


def get_signature_version(fea_payload: Dict[str, Any], signature: str) -> str:
    """Get the signature version for a given FEA."""
    return detect_signature_version(signature, fea_payload)
