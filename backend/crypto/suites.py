"""Signature Suite registry — crypto agility layer.

PFP signs the SAME deterministic canonical message (with the existing
``PFP_V2::`` domain prefix applied by the caller) under a selectable signature
suite. The suite is identified by the ``algorithm`` field which is part of the
SIGNED payload (algorithm-confusion defense) and by the resolved registry key's
algorithm at verification time.

Supported suites
----------------
* ``Ed25519`` — EdDSA over Curve25519 (DEFAULT; existing behaviour, PyNaCl).
* ``ES256``   — ECDSA over secp256r1 (NIST P-256) with SHA-256.
* ``ES256K``  — ECDSA over secp256k1 with SHA-256.

Encoding
--------
* Ed25519 signature: raw 64-byte signature, base64.
* ECDSA signature: raw ``r || s`` (32 + 32 = 64 bytes), base64 — JOSE/ES256
  style — for trivial cross-SDK parity. **Low-S canonical form is enforced on
  BOTH sign and verify** (anti-malleability / deterministic verification).

Public key bytes
----------------
* Ed25519: raw 32-byte public key.
* ECDSA: X9.62 uncompressed point ``0x04 || X || Y`` (65 bytes).

This module is intentionally pure crypto — it holds NO key material and performs
NO I/O. Key resolution lives in the KMS / signer layer.
"""
from __future__ import annotations

import base64
from typing import Optional, Tuple

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

ALG_ED25519 = "Ed25519"
ALG_ES256 = "ES256"
ALG_ES256K = "ES256K"

SUPPORTED_ALGORITHMS = (ALG_ED25519, ALG_ES256, ALG_ES256K)

# Curve group orders (public constants).
_SECP256R1_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

_EC_CURVE = {ALG_ES256: ec.SECP256R1, ALG_ES256K: ec.SECP256K1}
_EC_ORDER = {ALG_ES256: _SECP256R1_N, ALG_ES256K: _SECP256K1_N}

# Accept a few common aliases, normalize to canonical suite ids.
_ALIASES = {
    "ed25519": ALG_ED25519,
    "eddsa": ALG_ED25519,
    "es256": ALG_ES256,
    "secp256r1": ALG_ES256,
    "p-256": ALG_ES256,
    "prime256v1": ALG_ES256,
    "es256k": ALG_ES256K,
    "secp256k1": ALG_ES256K,
}


def normalize_algorithm(alg: Optional[str]) -> str:
    """Map an algorithm string / alias to a canonical suite id (defaults Ed25519)."""
    if not alg:
        return ALG_ED25519
    return _ALIASES.get(alg.strip().lower(), alg.strip())


def is_supported(alg: Optional[str]) -> bool:
    return normalize_algorithm(alg) in SUPPORTED_ALGORITHMS


def is_ecdsa(alg: str) -> bool:
    return normalize_algorithm(alg) in (ALG_ES256, ALG_ES256K)


# ---------------------------------------------------------------------------
# ECDSA helpers (raw r||s, low-S)
# ---------------------------------------------------------------------------

def _ecdsa_der_to_raw(der: bytes, order: int) -> bytes:
    r, s = decode_dss_signature(der)
    # Enforce low-S (canonical) form.
    if s > order // 2:
        s = order - s
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def _ecdsa_raw_to_der(raw: bytes, order: int) -> bytes:
    if len(raw) != 64:
        raise ValueError("ECDSA raw signature must be 64 bytes (r||s)")
    r = int.from_bytes(raw[:32], "big")
    s = int.from_bytes(raw[32:], "big")
    # Strict anti-malleability: reject high-S signatures on verify.
    if s == 0 or r == 0 or s > order // 2 or r >= order or s >= order:
        raise ValueError("non-canonical ECDSA signature (high-S or out of range)")
    return encode_dss_signature(r, s)


# ---------------------------------------------------------------------------
# Sign
# ---------------------------------------------------------------------------

def sign(alg: str, private_key, message: bytes) -> bytes:
    """Sign ``message`` (already domain-prefixed by the caller) under ``alg``.

    ``private_key`` is the suite-native key object:
      * Ed25519 -> nacl.signing.SigningKey
      * ES256/ES256K -> cryptography EllipticCurvePrivateKey
    Returns raw signature bytes (Ed25519: 64; ECDSA: r||s 64).
    """
    alg = normalize_algorithm(alg)
    if alg == ALG_ED25519:
        return private_key.sign(message).signature
    if alg in (ALG_ES256, ALG_ES256K):
        der = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
        return _ecdsa_der_to_raw(der, _EC_ORDER[alg])
    raise ValueError(f"Unsupported signature suite: {alg}")


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify(alg: str, public_key_bytes: bytes, message: bytes, signature: bytes) -> Tuple[bool, Optional[str]]:
    """Verify a signature under ``alg``. Returns (valid, reason)."""
    alg = normalize_algorithm(alg)
    try:
        if alg == ALG_ED25519:
            VerifyKey(public_key_bytes).verify(message, signature)
            return True, None
        if alg in (ALG_ES256, ALG_ES256K):
            curve = _EC_CURVE[alg]()
            pub = ec.EllipticCurvePublicKey.from_encoded_point(curve, public_key_bytes)
            der = _ecdsa_raw_to_der(signature, _EC_ORDER[alg])
            pub.verify(der, message, ec.ECDSA(hashes.SHA256()))
            return True, None
        return False, f"Unsupported signature suite: {alg}"
    except BadSignatureError:
        return False, "Invalid signature"
    except InvalidSignature:
        return False, "Invalid signature"
    except Exception as e:
        return False, f"Verification error: {e}"


# ---------------------------------------------------------------------------
# Public key helpers
# ---------------------------------------------------------------------------

def public_key_bytes(alg: str, private_key) -> bytes:
    """Extract the raw public key bytes for a suite-native private key."""
    alg = normalize_algorithm(alg)
    if alg == ALG_ED25519:
        return bytes(private_key.verify_key)
    if alg in (ALG_ES256, ALG_ES256K):
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        return private_key.public_key().public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        )
    raise ValueError(f"Unsupported signature suite: {alg}")


def validate_public_key_bytes(alg: str, public_key_bytes_in: bytes) -> bool:
    """Validate that ``public_key_bytes_in`` is a well-formed public key for ``alg``."""
    alg = normalize_algorithm(alg)
    try:
        if alg == ALG_ED25519:
            VerifyKey(public_key_bytes_in)
            return True
        if alg in (ALG_ES256, ALG_ES256K):
            curve = _EC_CURVE[alg]()
            ec.EllipticCurvePublicKey.from_encoded_point(curve, public_key_bytes_in)
            return True
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWK <-> raw public key (federated trust)
# ---------------------------------------------------------------------------

def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


_JWK_CRV = {ALG_ES256: "P-256", ALG_ES256K: "secp256k1"}


def jwk_to_public_key_bytes(jwk: dict) -> Tuple[str, bytes]:
    """Convert a JWK to (algorithm, raw public key bytes). Raises ValueError."""
    if not isinstance(jwk, dict):
        raise ValueError("JWK must be an object")
    kty = jwk.get("kty")
    crv = jwk.get("crv")
    if kty == "OKP" and crv == "Ed25519":
        x = _b64url_decode(jwk["x"])
        if len(x) != 32:
            raise ValueError("Ed25519 JWK x must be 32 bytes")
        return ALG_ED25519, x
    if kty == "EC":
        for alg, jcrv in _JWK_CRV.items():
            if crv == jcrv:
                x = _b64url_decode(jwk["x"])
                y = _b64url_decode(jwk["y"])
                if len(x) != 32 or len(y) != 32:
                    raise ValueError("EC JWK x/y must be 32 bytes each")
                return alg, b"\x04" + x + y
        raise ValueError(f"Unsupported EC curve: {crv}")
    raise ValueError(f"Unsupported JWK kty/crv: {kty}/{crv}")


def public_key_bytes_to_jwk(alg: str, public_key_bytes_in: bytes) -> dict:
    """Convert raw public key bytes to a JWK."""
    alg = normalize_algorithm(alg)
    if alg == ALG_ED25519:
        return {"kty": "OKP", "crv": "Ed25519", "x": _b64url_encode(public_key_bytes_in)}
    if alg in (ALG_ES256, ALG_ES256K):
        if len(public_key_bytes_in) != 65 or public_key_bytes_in[0] != 0x04:
            raise ValueError("EC public key must be 65-byte uncompressed point")
        return {
            "kty": "EC",
            "crv": _JWK_CRV[alg],
            "x": _b64url_encode(public_key_bytes_in[1:33]),
            "y": _b64url_encode(public_key_bytes_in[33:65]),
        }
    raise ValueError(f"Unsupported signature suite: {alg}")


def spki_pem_to_public_key_bytes(pem_or_der_bytes: bytes) -> Tuple[str, bytes]:
    """Parse an SPKI public key (PEM or DER) → (algorithm, raw public key bytes)."""
    from cryptography.hazmat.primitives.serialization import (
        load_pem_public_key, load_der_public_key, Encoding, PublicFormat,
    )
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed
    key = None
    try:
        key = load_pem_public_key(pem_or_der_bytes)
    except Exception:
        key = load_der_public_key(pem_or_der_bytes)
    if isinstance(key, _ed.Ed25519PublicKey):
        raw = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return ALG_ED25519, raw
    if isinstance(key, ec.EllipticCurvePublicKey):
        name = key.curve.name
        if name == "secp256r1":
            alg = ALG_ES256
        elif name == "secp256k1":
            alg = ALG_ES256K
        else:
            raise ValueError(f"Unsupported EC curve: {name}")
        raw = key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        return alg, raw
    raise ValueError("Unsupported SPKI key type")

