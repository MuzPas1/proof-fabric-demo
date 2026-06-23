"""
Backend tests for the Developer Portal sandbox flow.

Covers the full public lifecycle exercised by the in-browser playground:
  1. POST /api/demo/sandbox-key  -> issues a real, scoped, short-lived key
  2. POST /api/fea/generate      -> signs a Proof Artifact with that key
  3. GET  /api/public/verify/... -> independently verifies it (no auth)
"""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://deterministic-ledger-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _new_sandbox_key():
    r = requests.post(f"{API}/demo/sandbox-key", timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def test_sandbox_key_shape():
    data = _new_sandbox_key()
    assert data["api_key"].startswith("pfp_sandbox_")
    assert data["tenant_id"] == "sandbox"
    assert set(["fea:write", "fea:read", "fea:verify"]).issubset(set(data["scopes"]))
    assert data["expires_at"]  # short-lived
    assert "key_id" in data


def test_sandbox_keys_are_unique():
    a = _new_sandbox_key()["api_key"]
    b = _new_sandbox_key()["api_key"]
    assert a != b


def test_full_lifecycle_generate_then_verify():
    key = _new_sandbox_key()["api_key"]

    body = {
        "idempotency_key": "pytest-portal-001",
        "transaction_id": "EVT-PYTEST-001",
        "timestamp": "2026-06-15T10:00:00Z",
        "amount": 245000,
        "currency": "USD",
        "payer_id": "sha256:7b9c",
        "payee_id": "sha256:a14d",
    }
    gen = requests.post(
        f"{API}/fea/generate",
        headers={"X-API-Key": key, "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    assert gen.status_code == 200, gen.text
    proof = gen.json()
    assert proof["fea_id"]
    assert proof["signature"]
    assert proof["signature_version"] == "v2"
    assert proof["fea_payload"]["fea_hash"]

    ver = requests.get(f"{API}/public/verify/{proof['fea_id']}", timeout=30)
    assert ver.status_code == 200, ver.text
    v = ver.json()
    assert v["signature_valid"] is True
    assert v["fea_payload"]["fea_hash"] == proof["fea_payload"]["fea_hash"]


def test_generate_without_key_is_unauthorized():
    body = {
        "idempotency_key": "pytest-noauth-001",
        "transaction_id": "EVT-NOAUTH-001",
        "timestamp": "2026-06-15T10:00:00Z",
        "amount": 100,
        "currency": "USD",
        "payer_id": "sha256:1",
        "payee_id": "sha256:2",
    }
    r = requests.post(f"{API}/fea/generate", json=body, timeout=30)
    assert r.status_code == 401, r.text
