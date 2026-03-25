"""FEA verification service."""
import base64
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

from crypto.canonicalize import canonicalize_to_json
from crypto.hashing import compute_sha256
from crypto.signing import verify_signature, get_public_key


def verify_fea(fea_payload: Dict[str, Any], signature: str, public_key_registry: Dict[str, bytes]) -> Tuple[bool, Optional[str]]:
    """
    Verify an FEA payload and signature.
    
    Process:
    1. Extract fea_hash from payload
    2. Recreate canonical JSON (without fea_hash field)
    3. Recompute hash
    4. Verify computed hash matches fea_hash
    5. Fetch public key via public_key_id
    6. Verify signature
    
    Returns (valid, reason) tuple.
    """
    # Step 1: Extract claimed hash
    claimed_hash = fea_payload.get('fea_hash')
    if not claimed_hash:
        return False, "Missing fea_hash in payload"
    
    # Step 2 & 3: Recreate canonical JSON and recompute hash
    payload_without_hash = {k: v for k, v in fea_payload.items() if k != 'fea_hash'}
    canonical_json = canonicalize_to_json(payload_without_hash)
    computed_hash = compute_sha256(canonical_json)
    
    # Step 4: Verify hash matches
    if computed_hash != claimed_hash:
        return False, "Hash mismatch: payload has been tampered with"
    
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
    
    # Step 6: Verify signature
    return verify_signature(claimed_hash, signature, public_key_bytes)


def verify_fea_public(fea_payload: Dict[str, Any], signature: str) -> Tuple[bool, Optional[str]]:
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
