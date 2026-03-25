"""FEA verification service.

VERIFICATION PROTOCOL (v2):

1. Extract fea_payload (full payload including fea_hash)
2. Integrity check:
   - Remove fea_hash field
   - Canonicalize
   - Compute SHA-256
   - Compare with fea_payload.fea_hash
3. Signature verification:
   - Canonicalize FULL fea_payload (including fea_hash)
   - Verify Ed25519 signature on canonical JSON
4. Backward compatibility:
   - Detect signature version (v1 vs v2)
   - v1: verify against fea_hash (legacy)
   - v2: verify against canonical message (correct)
"""
from typing import Dict, Any, Tuple, Optional

from crypto.canonicalize import canonicalize_to_json
from crypto.hashing import compute_sha256
from crypto.signing import verify_signature, get_public_key, is_v2_signature


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
    4. Canonicalize FULL payload (including fea_hash)
    5. Verify signature (auto-detects v1 vs v2)

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

    # Step 4: Canonicalize FULL payload (including fea_hash)
    canonical_full = canonicalize_to_json(fea_payload)

    # Step 5: Get public key
    public_key_id = fea_payload.get('public_key_id')
    if not public_key_id:
        return False, "Missing public_key_id in payload"

    public_key_bytes = public_key_registry.get(public_key_id)
    if not public_key_bytes:
        # Try to use current key if ID matches
        try:
            from crypto.signing import get_public_key_id as get_current_key_id
            if public_key_id == get_current_key_id():
                public_key_bytes = get_public_key()
            else:
                return False, f"Unknown public_key_id: {public_key_id}"
        except Exception:
            return False, f"Unknown public_key_id: {public_key_id}"

    # Step 6: Verify signature (auto-detects v1 vs v2)
    # - v2: verifies against canonical_full (message-signed)
    # - v1: verifies against claimed_hash (hash-signed, legacy)
    valid, reason = verify_signature(
        canonical_message=canonical_full,
        fea_hash=claimed_hash,
        signature=signature,
        public_key_bytes=public_key_bytes
    )

    if valid:
        sig_version = "v2 (message-signed)" if is_v2_signature(signature) else "v1 (hash-signed, legacy)"
        return True, f"Signature valid ({sig_version})"

    return valid, reason


def verify_fea_public(
    fea_payload: Dict[str, Any],
    signature: str
) -> Tuple[bool, Optional[str]]:
    """
    Public verification using current key registry.
    """
    # Build registry with current key
    try:
        from crypto.signing import get_public_key_id, get_public_key
        registry = {
            get_public_key_id(): get_public_key()
        }
        return verify_fea(fea_payload, signature, registry)
    except Exception as e:
        return False, f"Verification error: {str(e)}"


def get_verification_details(
    fea_payload: Dict[str, Any],
    signature: str
) -> Dict[str, Any]:
    """
    Get detailed verification information for debugging/documentation.
    """
    result = {
        "signature_version": "v2" if is_v2_signature(signature) else "v1",
        "steps": []
    }

    # Step 1: Extract hash
    claimed_hash = fea_payload.get('fea_hash')
    result["steps"].append({
        "step": 1,
        "action": "Extract fea_hash from payload",
        "result": claimed_hash[:16] + "..." if claimed_hash else "MISSING"
    })

    if not claimed_hash:
        result["error"] = "Missing fea_hash"
        return result

    # Step 2: Recompute hash
    payload_without_hash = {k: v for k, v in fea_payload.items() if k != 'fea_hash'}
    canonical_without_hash = canonicalize_to_json(payload_without_hash)
    computed_hash = compute_sha256(canonical_without_hash)

    result["steps"].append({
        "step": 2,
        "action": "Recompute SHA-256 (canonicalize without fea_hash)",
        "canonical_json_preview": canonical_without_hash[:100] + "...",
        "computed_hash": computed_hash[:16] + "..."
    })

    # Step 3: Compare hashes
    hash_match = computed_hash == claimed_hash
    result["steps"].append({
        "step": 3,
        "action": "Compare computed hash with fea_hash",
        "result": "MATCH" if hash_match else "MISMATCH"
    })

    if not hash_match:
        result["error"] = "Hash mismatch"
        return result

    # Step 4: Canonicalize full payload
    canonical_full = canonicalize_to_json(fea_payload)
    result["steps"].append({
        "step": 4,
        "action": "Canonicalize FULL payload (including fea_hash)",
        "canonical_json_preview": canonical_full[:100] + "..."
    })

    # Step 5: Signature info
    result["steps"].append({
        "step": 5,
        "action": "Verify Ed25519 signature",
        "signature_version": result["signature_version"],
        "signed_data": "canonical message (v2)" if result["signature_version"] == "v2" else "fea_hash (v1 legacy)"
    })

    return result
