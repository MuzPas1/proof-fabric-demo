"""Generate shipped cross-SDK test vectors (one per signature suite).

Writes sdks/test_vectors.json:
  { "fea": [ {suite, algorithm, public_key_b64, public_key_id, fea_payload,
              signature, expected_valid} ... ] }

These vectors let any SDK prove independent verification + canonicalization
parity for Ed25519 / ES256 / ES256K against bytes produced by the live signer.
"""
import base64
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")

from crypto import suites
from crypto.canonicalize import canonicalize_to_json
from crypto.signing import sign_message, get_public_key_b64_for, get_public_key_id_for
from services.fea_service import build_fea_payload, compute_fea_hash
from models.fea import GenerateFEARequest
from core.kms import get_kms

OUT = Path(__file__).resolve().parent / "test_vectors.json"


def build_vector(suite: str) -> dict:
    req = GenerateFEARequest(
        idempotency_key=f"vec-{suite}", transaction_id=f"TXN-VECTOR-{suite}",
        timestamp="2026-06-10T12:00:00Z", amount=250000, currency="USD",
        payer_id="payer-token-abc", payee_id="payee-token-xyz",
        metadata={"note": "cross-sdk vector", "region": "global"},
    )
    payload = build_fea_payload(req, tenant_id="acme", suite_alg=suite)
    payload["fea_hash"] = compute_fea_hash(payload)
    sig = sign_message(canonicalize_to_json(payload), suite_alg=suite)
    return {
        "suite": suite,
        "algorithm": suite,
        "public_key_b64": get_public_key_b64_for(suite),
        "public_key_id": get_public_key_id_for(suite),
        "fea_payload": payload,
        "signature": sig,
        "expected_valid": True,
    }


def main():
    kms = get_kms()
    vectors = []
    for suite in suites.SUPPORTED_ALGORITHMS:
        if suite != "Ed25519" and not kms.supports_algorithm("production", suite):
            print(f"skip {suite}: no key configured")
            continue
        vectors.append(build_vector(suite))
        print(f"built vector: {suite}")
    OUT.write_text(json.dumps({"fea": vectors}, indent=2))
    print(f"wrote {OUT} ({len(vectors)} vectors)")


if __name__ == "__main__":
    main()
