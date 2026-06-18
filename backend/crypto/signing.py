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


def get_signing_key() -> SigningKey:
    """Get the production Ed25519 signing key via the KMS abstraction layer.

    The key material is never read directly here — it is resolved through the
    configured KMS provider (local/aws/gcp/azure). The local provider reads the
    ``PRIVATE_KEY`` env seed for development; production deployments use a cloud
    secret store so no plaintext key sits on disk.
    """
    from core.kms import get_kms
    return get_kms().get_signing_key("production")


def get_private_key() -> bytes:
    """Return the raw production seed bytes (compat helper)."""
    return bytes(get_signing_key())


def get_public_key() -> bytes:
    """Get the public key corresponding to the private key."""
    signing_key = get_signing_key()
    return bytes(signing_key.verify_key)


def get_public_key_id() -> str:
    """Generate a stable public key ID from the public key."""
    public_key = get_public_key()
    key_hash = hashlib.sha256(public_key).hexdigest()[:16]
    return f"key_{key_hash}"


# ---------------------------------------------------------------------------
# Crypto-agility helpers — suite-aware production key resolution
# ---------------------------------------------------------------------------
def get_public_key_b64_for(suite_alg: str = "Ed25519") -> str:
    """Production public key (base64) for a given signature suite."""
    from core.kms import get_kms
    return get_kms().get_public_key_b64("production", suite_alg)


def get_public_key_id_for(suite_alg: str = "Ed25519") -> str:
    """Production public key id (kid) for a given signature suite."""
    from core.kms import get_kms
    return get_kms().get_public_key_id("production", suite_alg)


def sign_message(message: str, suite_alg: str = "Ed25519") -> str:
    """
    Sign a message under the selected signature suite (default Ed25519).

    SECURITY: Message is prefixed with "PFP_V2::" to prevent cross-protocol
    signature reuse attacks. The domain prefix is identical across suites; the
    suite (and its key) is disambiguated by the signed ``algorithm`` field.

    Input: canonical JSON string (UTF-8)
    Output: pure base64-encoded signature (Ed25519: 64B; ECDSA: r||s 64B)

    Signing is delegated to the configured KMS provider's ``sign`` method so a
    future native-HSM/remote signer can be enabled by configuration alone, with
    no change to this call site.
    """
    from core.kms import get_kms
    prefixed_message = DOMAIN_PREFIX_V2 + message
    message_bytes = prefixed_message.encode('utf-8')
    signature = get_kms().sign("production", message_bytes, algorithm=suite_alg)
    return base64.b64encode(signature).decode('utf-8')


def sign_hash(hash_hex: str) -> str:
    """
    LEGACY (v1): Sign a hash using Ed25519.
    No domain prefix for backward compatibility.
    """
    from core.kms import get_kms
    hash_bytes = bytes.fromhex(hash_hex)
    signature = get_kms().sign("production", hash_bytes)
    return base64.b64encode(signature).decode('utf-8')


def normalize_signature(signature: str) -> str:
    """Normalize signature by stripping legacy prefix if present."""
    if signature.startswith(LEGACY_V2_PREFIX):
        return signature[len(LEGACY_V2_PREFIX):]
    return signature


def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def verify_signature_v2(message: str, signature_b64: str, public_key_bytes: bytes, algorithm: str = "Ed25519") -> Tuple[bool, Optional[str]]:
    """
    Verify a v2 signature (message-signed with domain prefix) under a suite.
    """
    from crypto import suites
    prefixed_message = DOMAIN_PREFIX_V2 + message
    message_bytes = prefixed_message.encode('utf-8')
    try:
        signature_bytes = base64.b64decode(signature_b64)
    except Exception as e:
        return False, f"Malformed signature encoding: {e}"
    return suites.verify(algorithm, public_key_bytes, message_bytes, signature_bytes)


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
    signature_version: str,
    algorithm: str = "Ed25519"
) -> Tuple[bool, Optional[str]]:
    """
    Verify signature based on version and signature suite.

    v1 (legacy) is Ed25519 hash-signed only. v2 dispatches to the suite
    identified by ``algorithm`` (Ed25519 / ES256 / ES256K).
    """
    raw_sig = normalize_signature(signature)

    if signature_version == SIGNATURE_VERSION_V2:
        return verify_signature_v2(canonical_message, raw_sig, public_key_bytes, algorithm)
    else:
        return verify_signature_v1(fea_hash, raw_sig, public_key_bytes)


def get_public_key_b64() -> str:
    """Get public key as base64 string."""
    return base64.b64encode(get_public_key()).decode('utf-8')


# ---------------------------------------------------------------------------
# Demo signing key (separate from production key — used for demo artifacts)
# ---------------------------------------------------------------------------
def get_demo_signing_key() -> SigningKey:
    """Resolve the DEMO Ed25519 signing key via the KMS abstraction layer.

    This key is intentionally distinct from the production key so demo /
    sandbox artifacts can never be confused with production-issued FEAs.
    """
    from core.kms import get_kms
    return get_kms().get_signing_key("demo")


def get_demo_public_key() -> bytes:
    return bytes(get_demo_signing_key().verify_key)


def get_demo_public_key_b64() -> str:
    return base64.b64encode(get_demo_public_key()).decode("utf-8")


def get_demo_public_key_id() -> str:
    key_hash = hashlib.sha256(get_demo_public_key()).hexdigest()[:16]
    return f"demo_key_{key_hash}"
