"""Offline unit tests: crypto, canonicalization, signing roundtrip, SDK parity.

These run without a live server (only env + libs). Used by CI for regression.
"""
import base64
import os
import sys
from pathlib import Path

import pytest

# Ensure backend + python SDK are importable
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent / "sdks" / "python"))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "pfp_ci")
os.environ.setdefault("PRIVATE_KEY", "8vU9cBlfDyl7lnuubAUtxAPlZQ5uAuGtHShS6OhwZ9Y=")
os.environ.setdefault("DEMO_PRIVATE_KEY", "QcFX/GCV2fy9sOFXsoBSla9JD/SbEZMw9HSmmESCQhM=")
os.environ.setdefault("KMS_PROVIDER", "local")

from crypto.canonicalize import canonicalize_to_json  # noqa: E402
from crypto.signing import (  # noqa: E402
    sign_message, get_public_key_b64, get_demo_public_key_b64,
    get_public_key_id, get_demo_public_key_id, DOMAIN_PREFIX_V2,
)
from services.fea_service import build_fea_payload, compute_fea_hash  # noqa: E402
from models.fea import GenerateFEARequest  # noqa: E402

import pfp_sdk.canonicalize as sdk_canon  # noqa: E402
from pfp_sdk.verify import verify_fea as sdk_verify_fea  # noqa: E402


def test_canonicalization_determinism():
    a = {"b": 1, "a": 2, "nested": {"z": None, "y": 3}}
    b = {"a": 2, "nested": {"y": 3}, "b": 1}
    assert canonicalize_to_json(a) == canonicalize_to_json(b)


def test_canonicalization_drops_nulls_and_collapses_floats():
    out = canonicalize_to_json({"x": None, "amt": 100.0, "flag": True})
    assert '"x"' not in out
    assert '"amt":100' in out  # float->int
    assert '"flag":true' in out


def test_sdk_canonicalization_parity():
    payload = {
        "fea_version": "1.1", "amount": 250000, "ts": "2026-06-10T12:00:00Z",
        "nested": {"b": 2, "a": 1}, "drop": None,
    }
    assert canonicalize_to_json(payload) == sdk_canon.canonicalize_to_json(payload)


def test_kms_separate_demo_key():
    # Production and demo keys must differ.
    assert get_public_key_b64() != get_demo_public_key_b64()
    assert get_public_key_id() != get_demo_public_key_id()
    assert get_demo_public_key_id().startswith("demo_key_")


def test_fea_sign_verify_roundtrip_and_sdk_verify():
    req = GenerateFEARequest(
        idempotency_key="k1", transaction_id="TXN-1", timestamp="2026-06-10T12:00:00Z",
        amount=99900, currency="usd", payer_id="p", payee_id="q",
    )
    payload = build_fea_payload(req, tenant_id="acme")
    payload["fea_hash"] = compute_fea_hash(payload)
    sig = sign_message(canonicalize_to_json(payload))

    # SDK independent verification with the production public key
    pub = get_public_key_b64()
    result = sdk_verify_fea(payload, sig, pub)
    assert result["valid"] is True

    # v1.1 hardening fields present and signed
    assert payload["tenant_id"] == "acme"
    assert payload["algorithm"] == "Ed25519"
    assert "iat" in payload and "jti" in payload


def test_tampered_payload_fails_sdk_verify():
    req = GenerateFEARequest(
        idempotency_key="k2", transaction_id="TXN-2", timestamp="2026-06-10T12:00:00Z",
        amount=100, currency="inr", payer_id="p", payee_id="q",
    )
    payload = build_fea_payload(req, tenant_id="acme")
    payload["fea_hash"] = compute_fea_hash(payload)
    sig = sign_message(canonicalize_to_json(payload))
    payload["transaction_summary"]["amount"] = 999999  # tamper
    assert sdk_verify_fea(payload, sig, get_public_key_b64())["valid"] is False


def test_domain_prefix_constant():
    assert DOMAIN_PREFIX_V2 == "PFP_V2::"
