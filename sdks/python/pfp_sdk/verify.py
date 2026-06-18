"""Independent FEA / artifact verification (no PFP server round-trip required).

Crypto-agile: the signature suite is read from the signed payload's
``algorithm`` field (Ed25519 default; ES256 = secp256r1; ES256K = secp256k1).
ECDSA signatures are raw r||s (64 bytes) with enforced low-S (anti-malleability),
matching the PFP signing format.
"""
import base64
import hashlib
import hmac

from .canonicalize import canonicalize_to_json

DOMAIN_PREFIX_V2 = "PFP_V2::"
ARTIFACT_DOMAIN_PREFIX = b"PFP_ARTIFACT_V1::"

# Curve group orders (for low-S enforcement).
_N_R1 = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_N_K1 = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def _verify_suite(algorithm: str, public_key: bytes, message: bytes, signature: bytes) -> bool:
    alg = algorithm or "Ed25519"
    if alg in ("Ed25519", "EdDSA"):
        from nacl.signing import VerifyKey
        try:
            VerifyKey(public_key).verify(message, signature)
            return True
        except Exception:
            return False
    if alg in ("ES256", "ES256K"):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        if len(signature) != 64:
            return False
        curve = ec.SECP256R1() if alg == "ES256" else ec.SECP256K1()
        order = _N_R1 if alg == "ES256" else _N_K1
        r = int.from_bytes(signature[:32], "big")
        s = int.from_bytes(signature[32:], "big")
        # Reject non-canonical / high-S signatures (anti-malleability).
        if r == 0 or s == 0 or r >= order or s >= order or s > order // 2:
            return False
        try:
            pub = ec.EllipticCurvePublicKey.from_encoded_point(curve, public_key)
            pub.verify(encode_dss_signature(r, s), message, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False
    return False


def verify_fea(fea_payload: dict, signature_b64: str, public_key_b64: str, algorithm: str = None) -> dict:
    """Independently verify an FEA payload + signature (any supported suite).

    Returns {"valid": bool, "reason": str|None}. The public key comes from
    GET /api/public/keys (match on public_key_id); its `algorithm` matches the
    payload's `algorithm` field."""
    claimed_hash = fea_payload.get("fea_hash")
    if not claimed_hash:
        return {"valid": False, "reason": "Missing fea_hash"}

    payload_wo_hash = {k: v for k, v in fea_payload.items() if k != "fea_hash"}
    computed = hashlib.sha256(canonicalize_to_json(payload_wo_hash).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(computed, claimed_hash):
        return {"valid": False, "reason": "Hash mismatch: payload tampered"}

    alg = algorithm or fea_payload.get("algorithm", "Ed25519")
    canonical_full = canonicalize_to_json(fea_payload)
    message = (DOMAIN_PREFIX_V2 + canonical_full).encode("utf-8")
    ok = _verify_suite(alg, base64.b64decode(public_key_b64), message, base64.b64decode(signature_b64))
    return {"valid": ok, "reason": None if ok else "Invalid signature"}


def verify_artifact(artifact: dict, public_key_b64: str, algorithm: str = None) -> dict:
    """Independently verify a downloadable signed artifact (schema v1)."""
    sig = artifact.get("signature")
    proof_id = artifact.get("proof_id")
    if not sig or not proof_id:
        return {"valid": False, "reason": "Missing signature/proof_id"}
    base = {k: v for k, v in artifact.items() if k not in ("signature",)}
    base_for_id = {k: v for k, v in base.items() if k != "proof_id"}
    expected = hashlib.sha256(canonicalize_to_json(base_for_id).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(expected, str(proof_id)):
        return {"valid": False, "reason": "proof_id mismatch"}
    alg = algorithm or artifact.get("algorithm", "Ed25519")
    message = ARTIFACT_DOMAIN_PREFIX + canonicalize_to_json(base).encode("utf-8")
    ok = _verify_suite(alg, base64.b64decode(public_key_b64), message, base64.b64decode(sig))
    return {"valid": ok, "reason": None if ok else "Invalid signature"}
