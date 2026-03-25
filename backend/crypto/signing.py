"""Ed25519 signing and verification."""
import base64
import os
import hashlib
from typing import Tuple, Optional
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


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


def sign_hash(hash_hex: str) -> str:
    """
    Sign a hash using Ed25519.
    Input: hex-encoded SHA-256 hash
    Output: base64-encoded signature
    """
    signing_key = get_signing_key()
    hash_bytes = bytes.fromhex(hash_hex)
    signed = signing_key.sign(hash_bytes)
    # Return just the signature (first 64 bytes), not the message
    return base64.b64encode(signed.signature).decode('utf-8')


def verify_signature(hash_hex: str, signature_b64: str, public_key_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Verify a signature using Ed25519.
    Returns (valid, reason) tuple.
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


def get_public_key_b64() -> str:
    """Get public key as base64 string."""
    return base64.b64encode(get_public_key()).decode('utf-8')
