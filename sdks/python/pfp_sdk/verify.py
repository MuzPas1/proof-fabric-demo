"""Independent FEA verification (no PFP server round-trip required)."""
import base64
import hashlib
import hmac

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from .canonicalize import canonicalize_to_json

DOMAIN_PREFIX_V2 = "PFP_V2::"
ARTIFACT_DOMAIN_PREFIX = b"PFP_ARTIFACT_V1::"


def verify_fea(fea_payload: dict, signature_b64: str, public_key_b64: str) -> dict:
    """Independently verify an FEA payload + Ed25519 signature.

    Returns {"valid": bool, "reason": str|None}. Requires the issuer's public
    key (fetch from GET /api/public/keys, match on public_key_id)."""
    claimed_hash = fea_payload.get("fea_hash")
    if not claimed_hash:
        return {"valid": False, "reason": "Missing fea_hash"}

    payload_wo_hash = {k: v for k, v in fea_payload.items() if k != "fea_hash"}
    computed = hashlib.sha256(canonicalize_to_json(payload_wo_hash).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(computed, claimed_hash):
        return {"valid": False, "reason": "Hash mismatch: payload tampered"}

    canonical_full = canonicalize_to_json(fea_payload)
    message = (DOMAIN_PREFIX_V2 + canonical_full).encode("utf-8")
    try:
        VerifyKey(base64.b64decode(public_key_b64)).verify(message, base64.b64decode(signature_b64))
        return {"valid": True, "reason": None}
    except BadSignatureError:
        return {"valid": False, "reason": "Invalid signature"}
    except Exception as e:
        return {"valid": False, "reason": f"Verification error: {e}"}


def verify_artifact(artifact: dict, public_key_b64: str) -> dict:
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
    message = ARTIFACT_DOMAIN_PREFIX + canonicalize_to_json(base).encode("utf-8")
    try:
        VerifyKey(base64.b64decode(public_key_b64)).verify(message, base64.b64decode(sig))
        return {"valid": True, "reason": None}
    except Exception:
        return {"valid": False, "reason": "Invalid signature"}
