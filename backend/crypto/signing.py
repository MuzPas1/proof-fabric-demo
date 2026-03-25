"""Ed25519 signing and verification.

SIGNING MODEL (v2):
- Ed25519 signs the canonical JSON message with DOMAIN PREFIX
- Domain prefix: "PFP_V2::" prevents cross-protocol attacks
- Signature is pure base64 (no prefix in output)
"""
import base64
import os
import hashlib
import hmac
from typing import Tuple, Optional
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


# Signature versions
SIGNATURE_VERSION_V2 = "v2"  # Message-signed with domain prefix
SIGNATURE_VERSION_V1 = "v1"  # Hash-signed (legacy)

# Legacy prefix (for backward compatibility only)
LEGACY_V2_PREFIX = "v2:"

# Domain separator for cross-protocol attack prevention
DOMAIN_PREFIX_V2 = "PFP_V2::"


def get_private_key() -> bytes:
    """Get Ed25519 private key from environment (base64 encoded)."""
    key_b64 = os.environ.get('PRIVATE_KEY')
    if not key_b64:
        raise ValueError("PRIVATE_KEY environment variable not set")
    return base64.b64decode(key_b64)


def get_signing_key() -> SigningKey:
    """Get Ed25519 signing key from environment."""
    seed = get_private_key()
    if len(seed) == 64:
        seed = seed[:32]
    return SigningKey(seed)


def get_public_key() -> bytes:
    """Get the public key corresponding to the private key."""
    signing_key = get_signing_key()
    return bytes(signing_key.verify_key)


def get_public_key_id() -> str:
    """Generate a stable public key ID from the public key."""
    public_key = get_public_key()
    key_hash = hashlib.sha256(public_key).hexdigest()[:16]
    return f"key_{key_hash}"


def sign_message(message: str) -> str:
    """
    Sign a message directly using Ed25519 with domain prefix.
    
    SECURITY: Message is prefixed with "PFP_V2::" to prevent
    cross-protocol signature reuse attacks.
    
    Input: canonical JSON string (UTF-8)
    Output: pure base64-encoded signature
    """
    signing_key = get_signing_key()
    # Add domain prefix for cross-protocol attack prevention
    prefixed_message = DOMAIN_PREFIX_V2 + message
    message_bytes = prefixed_message.encode('utf-8')
    signed = signing_key.sign(message_bytes)
    return base64.b64encode(signed.signature).decode('utf-8')


def sign_hash(hash_hex: str) -> str:
    """
    LEGACY (v1): Sign a hash using Ed25519.
    No domain prefix for backward compatibility.
    """
    signing_key = get_signing_key()
    hash_bytes = bytes.fromhex(hash_hex)
    signed = signing_key.sign(hash_bytes)
    return base64.b64encode(signed.signature).decode('utf-8')


def normalize_signature(signature: str) -> str:
    """Normalize signature by stripping legacy prefix if present."""
    if signature.startswith(LEGACY_V2_PREFIX):
        return signature[len(LEGACY_V2_PREFIX):]
    return signature


def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def verify_signature_v2(message: str, signature_b64: str, public_key_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Verify a v2 signature (message-signed with domain prefix).
    """
    try:
        verify_key = VerifyKey(public_key_bytes)
        # Add domain prefix (must match signing)
        prefixed_message = DOMAIN_PREFIX_V2 + message
        message_bytes = prefixed_message.encode('utf-8')
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
    No domain prefix for backward compatibility.
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
    """
    raw_sig = normalize_signature(signature)
    
    if signature_version == SIGNATURE_VERSION_V2:
        return verify_signature_v2(canonical_message, raw_sig, public_key_bytes)
    else:
        return verify_signature_v1(fea_hash, raw_sig, public_key_bytes)


def get_public_key_b64() -> str:
    """Get public key as base64 string."""
    return base64.b64encode(get_public_key()).decode('utf-8')
