"""AI Provenance & Accountability — detached, signed, privacy-preserving envelope
(Trust Layer 2, Phase 2).

Mirrors the time-anchor design: a provenance envelope is produced AFTER signing
and stored beside the proof, so it NEVER changes the signed payload, ``fea_hash``,
``fea_id`` or the signature. The envelope binds to the proof's existing
``fea_hash`` and is itself signed by the platform key (Ed25519, domain-separated)
so it is tamper-evident and independently verifiable. ONLY hashes and
non-sensitive identity metadata are stored — never raw prompts, inputs, outputs,
or business content.

Vendor-neutral by construction: identity fields are free-form strings (no
provider is special-cased). Verification is additive to signature verification.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Dict

from crypto.canonicalize import canonicalize_to_json
from crypto.hashing import compute_sha256
from crypto import suites

PROV_DOMAIN_PREFIX = "PFP_AIPROV_V1::"
ENVELOPE_VERSION = "1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def content_hash_of(content: Dict) -> str:
    """Deterministic SHA-256 over the canonical provenance content (PFP-JCS)."""
    return compute_sha256(canonicalize_to_json(content))


def binding_message(fea_hash: str, content_hash: str, recorded_at: str) -> bytes:
    """Domain-separated message the platform signs to attest the provenance.

    Binds the proof (``fea_hash``) to the provenance content (``content_hash``)
    at ``recorded_at`` so the envelope cannot be lifted onto another proof.
    """
    return f"{PROV_DOMAIN_PREFIX}{fea_hash}:{content_hash}@{recorded_at}".encode("utf-8")


def sign_envelope(fea_hash: str, content: Dict) -> Dict:
    """Build a signed, detached provenance envelope binding the proof's fea_hash.

    Signs with the platform production Ed25519 key via the KMS abstraction — the
    same trust root that signs proofs, so provenance attestation inherits the
    platform's key lifecycle (and verifies against the public key registry).
    """
    from core.kms import get_kms

    recorded_at = _now_iso()
    chash = content_hash_of(content)
    msg = binding_message(fea_hash, chash, recorded_at)
    kms = get_kms()
    sig = kms.sign("production", msg, algorithm=suites.ALG_ED25519)
    kid = kms.get_public_key_id("production", suites.ALG_ED25519)
    return {
        "envelope_version": ENVELOPE_VERSION,
        "recorded_at": recorded_at,
        "fea_hash": fea_hash,
        "content": content,
        "content_hash": chash,
        "binding": {
            "alg": "Ed25519",
            "domain": PROV_DOMAIN_PREFIX,
            "public_key_id": kid,
            "signature": base64.b64encode(sig).decode("ascii"),
        },
    }


def verify_binding_signature(envelope: Dict, public_key_bytes: bytes) -> bool:
    """Verify the envelope's Ed25519 binding signature against a public key."""
    binding = envelope.get("binding") or {}
    try:
        msg = binding_message(
            envelope.get("fea_hash"),
            envelope.get("content_hash"),
            envelope.get("recorded_at"),
        )
        sig = base64.b64decode(binding.get("signature", ""))
        ok, _ = suites.verify(suites.ALG_ED25519, public_key_bytes, msg, sig)
        return bool(ok)
    except Exception:  # noqa: BLE001
        return False
