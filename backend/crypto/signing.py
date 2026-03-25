"""Ed25519 signing and verification.

SIGNING MODEL (v2):
- Ed25519 signs the canonical JSON message DIRECTLY
- NOT the SHA-256 hash (legacy v1 model)

This is cryptographically correct for Ed25519 which is designed
to sign messages directly (it internally uses SHA-512 for hashing).
"""
import base64
import os
import hashlib
from typing import Tuple, Optional
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


# Signature version prefix for backward compatibility
SIGNATURE_VERSION_V2 = "v2:"  # New: signs canonical JSON directly
# v1 (legacy): no prefix, signs SHA-256 hash


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
    Sign a message directly using Ed25519 (v2 model).
    
    Input: canonical JSON string (UTF-8)
    Output: base64-encoded signature with v2 prefix
    
    This is the cryptographically correct way to use Ed25519.
    Ed25519 internally handles hashing (SHA-512) as part of the signing process.
    """
    signing_key = get_signing_key()
    message_bytes = message.encode('utf-8')
    signed = signing_key.sign(message_bytes)
    # Return signature with v2 prefix for version detection
    signature_b64 = base64.b64encode(signed.signature).decode('utf-8')
    return f"{SIGNATURE_VERSION_V2}{signature_b64}"


def sign_hash(hash_hex: str) -> str:
    """
    LEGACY (v1): Sign a hash using Ed25519.
    
    Input: hex-encoded SHA-256 hash
    Output: base64-encoded signature (no prefix = v1)
    
    DEPRECATED: Use sign_message() for new FEAs.
    Kept for backward compatibility verification.
    """
    signing_key = get_signing_key()
    hash_bytes = bytes.fromhex(hash_hex)
    signed = signing_key.sign(hash_bytes)
    # No prefix = legacy v1 signature
    return base64.b64encode(signed.signature).decode('utf-8')


def verify_signature_v2(message: str, signature_b64: str, public_key_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Verify a v2 signature (message-signed).
    
    Input:
    - message: canonical JSON string
    - signature_b64: base64-encoded signature (without v2: prefix)
    - public_key_bytes: raw public key bytes
    """
    try:
        verify_key = VerifyKey(public_key_bytes)
        message_bytes = message.encode('utf-8')
        signature_bytes = base64.b64decode(signature_b64)
        verify_key.verify(message_bytes, signature_bytes)
        return True, None
    except BadSignatureError:
        return False, "Invalid signature (v2 message-signed)"
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
        return False, "Invalid signature (v1 hash-signed)"
    except Exception as e:
        return False, f"Verification error: {str(e)}"


def is_v2_signature(signature: str) -> bool:
    """Check if signature uses v2 format (message-signed)."""
    return signature.startswith(SIGNATURE_VERSION_V2)


def extract_signature_data(signature: str) -> Tuple[str, str]:
    """
    Extract version and raw signature from signature string.
    
    Returns: (version, raw_signature_b64)
    - version: "v1" or "v2"
    - raw_signature_b64: base64-encoded signature without prefix
    """
    if signature.startswith(SIGNATURE_VERSION_V2):
        return "v2", signature[len(SIGNATURE_VERSION_V2):]
    else:
        return "v1", signature


def verify_signature(
    canonical_message: str,
    fea_hash: str,
    signature: str,
    public_key_bytes: bytes
) -> Tuple[bool, Optional[str]]:
    """
    Verify signature with automatic version detection.
    
    Supports both:
    - v2: signature on canonical JSON message (correct Ed25519 usage)
    - v1: signature on SHA-256 hash (legacy)
    
    Input:
    - canonical_message: full canonical JSON of fea_payload
    - fea_hash: the fea_hash field value (for v1 verification)
    - signature: signature string (may have v2: prefix)
    - public_key_bytes: raw public key bytes
    """
    version, raw_sig = extract_signature_data(signature)
    
    if version == "v2":
        return verify_signature_v2(canonical_message, raw_sig, public_key_bytes)
    else:
        # v1 legacy: verify against hash
        return verify_signature_v1(fea_hash, raw_sig, public_key_bytes)


def get_public_key_b64() -> str:
    """Get public key as base64 string."""
    return base64.b64encode(get_public_key()).decode('utf-8')
