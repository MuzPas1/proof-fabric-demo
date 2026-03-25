"""Ed25519 signing and verification.

SIGNING MODEL (v2):
- Ed25519 signs the canonical JSON message DIRECTLY
- Signature is pure base64 (no prefix)
- Version is stored in FEA structure as "signature_version" field
"""
import base64
import os
import hashlib
from typing import Tuple, Optional
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


# Signature versions
SIGNATURE_VERSION_V2 = "v2"  # Message-signed (correct Ed25519 usage)
SIGNATURE_VERSION_V1 = "v1"  # Hash-signed (legacy)

# Legacy prefix (for backward compatibility only)
LEGACY_V2_PREFIX = "v2:"


def get_private_key() -> bytes:
    """Get Ed25519 private key from environment (base64 encoded)."""
    key_b64 = os.environ.get('PRIVATE_KEY')
    if not key_b64:
        raise ValueError("PRIVATE_KEY environment variable not set")
    return base64.b64decode(key_b64)


def get_signing_key() -> SigningKey:
    """Get Ed25519 signing key from environment."""
    seed = get_private_key()
    # Ed25519 seed is 32 bytes
    if len(seed) == 64:
        # Full keypair provided, extract seed (first 32 bytes)
        seed = seed[:32]
    return SigningKey(seed)


def get_public_key() -> bytes:
    """Get the public key corresponding to the private key."""
    signing_key = get_signing_key()
    return bytes(signing_key.verify_key)


def get_public_key_id() -> str:
    """Generate a stable public key ID from the public key."""
    public_key = get_public_key()
    # Use first 8 bytes of SHA-256 hash as ID
    key_hash = hashlib.sha256(public_key).hexdigest()[:16]
    return f"key_{key_hash}"


def sign_message(message: str) -> str:
    """
    Sign a message directly using Ed25519.
    
    Input: canonical JSON string (UTF-8)
    Output: pure base64-encoded signature (NO prefix)
    
    This is the cryptographically correct way to use Ed25519.
    """
    signing_key = get_signing_key()
    message_bytes = message.encode('utf-8')
    signed = signing_key.sign(message_bytes)
    # Return PURE base64 signature - no prefix
    return base64.b64encode(signed.signature).decode('utf-8')


def sign_hash(hash_hex: str) -> str:
    """
    LEGACY (v1): Sign a hash using Ed25519.
    
    Input: hex-encoded SHA-256 hash
    Output: base64-encoded signature
    
    DEPRECATED: Use sign_message() for new FEAs.
    """
    signing_key = get_signing_key()
    hash_bytes = bytes.fromhex(hash_hex)
    signed = signing_key.sign(hash_bytes)
    return base64.b64encode(signed.signature).decode('utf-8')


def normalize_signature(signature: str) -> str:
    """
    Normalize signature by stripping legacy prefix if present.
    Returns pure base64 signature.
    """
    if signature.startswith(LEGACY_V2_PREFIX):
        return signature[len(LEGACY_V2_PREFIX):]
    return signature


def detect_signature_version(signature: str, fea_payload: dict) -> str:
    """
    Detect signature version from FEA payload or signature format.
    
    Priority:
    1. signature_version field in payload (explicit)
    2. Legacy v2: prefix in signature
    3. Default to v1 (hash-signed)
    """
    # Check explicit version field first
    if 'signature_version' in fea_payload:
        return fea_payload['signature_version']
    
    # Check for legacy prefix
    if signature.startswith(LEGACY_V2_PREFIX):
        return SIGNATURE_VERSION_V2
    
    # Default to v1 (legacy hash-signed)
    return SIGNATURE_VERSION_V1


def verify_signature_v2(message: str, signature_b64: str, public_key_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Verify a v2 signature (message-signed).
    
    Input:
    - message: canonical JSON string
    - signature_b64: pure base64-encoded signature
    - public_key_bytes: raw public key bytes
    """
    try:
        verify_key = VerifyKey(public_key_bytes)
        message_bytes = message.encode('utf-8')
        signature_bytes = base64.b64decode(signature_b64)
        verify_key.verify(message_bytes, signature_bytes)
        return True, None
    except BadSignatureError:
        return False, "Invalid signature"
    except Exception as e:
        return False, f"Verification error: {str(e)}"


def verify_signature_v1(hash_hex: str, signature_b64: str, public_key_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Verify a v1 signature (hash-signed) - LEGACY.
    
    Input:
    - hash_hex: hex-encoded SHA-256 hash
    - signature_b64: base64-encoded signature
    - public_key_bytes: raw public key bytes
    """
    try:
        verify_key = VerifyKey(public_key_bytes)
        hash_bytes = bytes.fromhex(hash_hex)
        signature_bytes = base64.b64decode(signature_b64)
        verify_key.verify(hash_bytes, signature_bytes)
        return True, None
    except BadSignatureError:
        return False, "Invalid signature"
    except Exception as e:
        return False, f"Verification error: {str(e)}"


def verify_signature(
    canonical_message: str,
    fea_hash: str,
    signature: str,
    public_key_bytes: bytes,
    signature_version: str
) -> Tuple[bool, Optional[str]]:
    """
    Verify signature based on version.
    
    Input:
    - canonical_message: full canonical JSON of fea_payload
    - fea_hash: the fea_hash field value (for v1 verification)
    - signature: signature string (may have legacy prefix)
    - public_key_bytes: raw public key bytes
    - signature_version: "v1" or "v2"
    """
    # Normalize signature (strip legacy prefix if present)
    raw_sig = normalize_signature(signature)
    
    if signature_version == SIGNATURE_VERSION_V2:
        return verify_signature_v2(canonical_message, raw_sig, public_key_bytes)
    else:
        # v1 legacy: verify against hash
        return verify_signature_v1(fea_hash, raw_sig, public_key_bytes)


def get_public_key_b64() -> str:
    """Get public key as base64 string."""
    return base64.b64encode(get_public_key()).decode('utf-8')
