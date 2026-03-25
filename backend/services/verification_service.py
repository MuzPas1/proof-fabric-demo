"""FEA verification service.

VERIFICATION PROTOCOL:
1. Determine signature_version:
   - From external parameter (new format)
   - From fea_payload.signature_version (legacy)
   - From signature prefix (legacy v2:)
   - Default to v1
2. Clean fea_payload (remove signature_version if present)
3. Recompute fea_hash for integrity
4. Canonicalize fea_payload
5. Verify signature based on version
"""
from typing import Dict, Any, Tuple, Optional

from crypto.canonicalize import canonicalize_to_json
from crypto.hashing import compute_sha256
from crypto.signing import (
    verify_signature,
    get_public_key,
    normalize_signature,
    SIGNATURE_VERSION_V1,
    SIGNATURE_VERSION_V2,
    LEGACY_V2_PREFIX
)


def detect_signature_version(
    signature: str,
    fea_payload: Dict[str, Any],
    external_version: Optional[str] = None
) -> str:
    """
    Detect signature version with priority:
    1. External signature_version parameter (new format)
    2. signature_version field in payload (legacy format)
    3. Legacy v2: prefix in signature
    4. Default to v1 (hash-signed)
    """
    # Priority 1: External parameter
    if external_version:
        return external_version
    
    # Priority 2: Field in payload (legacy)
    if 'signature_version' in fea_payload:
        return fea_payload['signature_version']
    
    # Priority 3: Legacy prefix
    if signature.startswith(LEGACY_V2_PREFIX):
        return SIGNATURE_VERSION_V2
    
    # Default: v1
    return SIGNATURE_VERSION_V1


def clean_payload_for_verification(fea_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare payload for verification.
    
    For NEW format: payload doesn't have signature_version (nothing to remove)
    For LEGACY format: payload HAS signature_version (keep it, it was signed)
    
    We do NOT remove signature_version because:
    - New FEAs don't have it in payload
    - Legacy FEAs that have it, signed it as part of the payload
    """
    # Return payload as-is - don't remove anything
    # This maintains backward compatibility with legacy FEAs
    return fea_payload


def verify_fea(
    fea_payload: Dict[str, Any],
    signature: str,
    public_key_registry: Dict[str, bytes],
    external_signature_version: Optional[str] = None
) -> Tuple[bool, Optional[str], str]:
    """
    Verify an FEA payload and signature.

    VERIFICATION STEPS:
    1. Detect signature version
    2. Clean payload (remove legacy signature_version if present)
    3. Recompute fea_hash for integrity check
    4. Canonicalize cleaned fea_payload
    5. Verify signature based on version

    Returns (valid, reason, signature_version) tuple.
    """
    # Step 1: Detect signature version
    sig_version = detect_signature_version(signature, fea_payload, external_signature_version)

    # Step 2: Clean payload for verification
    clean_payload = clean_payload_for_verification(fea_payload)

    # Step 3: Extract and verify fea_hash
    claimed_hash = clean_payload.get('fea_hash')
    if not claimed_hash:
        return False, "Missing fea_hash in payload", sig_version

    # Recompute hash (without fea_hash field)
    payload_without_hash = {k: v for k, v in clean_payload.items() if k != 'fea_hash'}
    canonical_without_hash = canonicalize_to_json(payload_without_hash)
    computed_hash = compute_sha256(canonical_without_hash)

    if computed_hash != claimed_hash:
        return False, "Hash mismatch: payload has been tampered with", sig_version

    # Step 4: Canonicalize full cleaned payload
    canonical_full = canonicalize_to_json(clean_payload)

    # Step 5: Get public key
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

    # Step 6: Verify signature
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
    """
    Public verification using current key registry.
    """
    try:
        from crypto.signing import get_public_key_id, get_public_key
        registry = {
            get_public_key_id(): get_public_key()
        }
        return verify_fea(fea_payload, signature, registry, external_signature_version)
    except Exception as e:
        return False, f"Verification error: {str(e)}", "unknown"
