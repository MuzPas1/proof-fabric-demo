"""E2E review tests for Crypto Agility + Federated Keys + BYOS (iteration 17)."""
import os
import base64
import json
import time
import pytest
import requests
from nacl.signing import SigningKey

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pfp-api.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
SANDBOX_KEY = "pfp_sandbox_a5fb2bad1924d788c128edf6a31bf1aaa107a9a4"
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!2026"

COMPLIANT = {"kyc": "Pass", "aml": "Pass", "limits": "Within allowed range", "status": "COMPLIANT"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sandbox_headers():
    return {"X-API-Key": SANDBOX_KEY, "Content-Type": "application/json"}


def _fea_body(suite=None, suffix=""):
    body = {
        "idempotency_key": f"TEST_IK_{int(time.time()*1000)}_{suffix}",
        "transaction_id": f"TEST_TXN_{int(time.time()*1000)}_{suffix}",
        "timestamp": "2026-01-15T12:00:00Z",
        "amount": 4200,
        "currency": "USD",
        "payer_id": "TEST_payer",
        "payee_id": "TEST_payee",
    }
    if suite:
        body["signature_suite"] = suite
    return body


# 1. BACKWARD COMPAT - default Ed25519
def test_backward_compat_default_ed25519(sandbox_headers):
    r = requests.post(f"{API}/fea/generate", json=_fea_body(suffix="ed"), headers=sandbox_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["fea_payload"]["algorithm"] == "Ed25519"
    fea_id = data["fea_id"]
    v = requests.get(f"{API}/public/verify/{fea_id}", timeout=20)
    assert v.status_code == 200, v.text
    assert v.json()["signature_valid"] is True


# 2. CRYPTO AGILITY ES256 / ES256K
@pytest.mark.parametrize("suite", ["ES256", "ES256K"])
def test_crypto_agility_es_suites(sandbox_headers, suite):
    r = requests.post(f"{API}/fea/generate", json=_fea_body(suite=suite, suffix=suite), headers=sandbox_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["fea_payload"]["algorithm"] == suite, data["fea_payload"]
    fea_id = data["fea_id"]
    v = requests.get(f"{API}/public/verify/{fea_id}", timeout=20)
    assert v.status_code == 200, v.text
    assert v.json()["signature_valid"] is True


# 3. Unknown suite rejected
def test_unknown_suite_rejected(sandbox_headers):
    body = _fea_body(suite="RSA", suffix="rsa")
    r = requests.post(f"{API}/fea/generate", json=body, headers=sandbox_headers, timeout=20)
    assert r.status_code == 400, r.text


# 4. DEMO workflow unchanged
def test_demo_issue_verify_unchanged():
    payload = {
        "transaction_id": f"TEST_DEMO_{int(time.time()*1000)}",
        "user_id": "TEST_user_demo",
        "amount": "100.00",
        "created_at": "2026-01-15T10:00:00Z",
        "compliance": COMPLIANT,
    }
    issue = requests.post(f"{API}/demo/issue", json=payload, timeout=20)
    assert issue.status_code == 200, issue.text
    pid = issue.json()["proof_id"]
    v = requests.get(f"{API}/demo/verify/{pid}", timeout=20)
    assert v.status_code == 200, v.text
    assert v.json()["valid"] is True


def test_demo_artifact_unchanged():
    payload = {
        "transaction_id": f"TEST_ART_{int(time.time()*1000)}",
        "user_id": "TEST_user_art",
        "amount": "50.00",
        "compliance": COMPLIANT,
        "timestamp": "2026-01-15T10:00:00Z",
    }
    a = requests.post(f"{API}/demo/artifact", json=payload, timeout=20)
    assert a.status_code == 200, a.text
    artifact = a.json()
    v = requests.post(f"{API}/demo/artifact/verify", json=artifact, timeout=20)
    assert v.status_code == 200, v.text
    assert v.json()["valid"] is True


# 5. FEDERATED KEY REGISTRY register/confirm PoP + bad PoP
def test_federated_key_register_confirm(admin_headers):
    sk = SigningKey.generate()
    pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode()
    reg_body = {
        "owner": "partner",
        "algorithm": "Ed25519",
        "key_format": "raw",
        "public_key": pub_b64,
        "label": "TEST_FED_KEY",
    }
    r = requests.post(f"{API}/admin/keys/federated/register", json=reg_body, headers=admin_headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    out = r.json()
    assert out.get("status") == "pending", out
    challenge = out.get("pop_challenge")
    key_id = out.get("public_key_id")
    assert challenge and key_id, out

    # bad PoP
    bad_sig = base64.b64encode(b"x" * 64).decode()
    bad = requests.post(
        f"{API}/admin/keys/federated/confirm",
        json={"public_key_id": key_id, "pop_signature": bad_sig},
        headers=admin_headers, timeout=20,
    )
    assert bad.status_code == 400, bad.text

    # good PoP
    msg = ("PFP_POP_V1::" + challenge).encode()
    pop_sig = base64.b64encode(sk.sign(msg).signature).decode()
    ok = requests.post(
        f"{API}/admin/keys/federated/confirm",
        json={"public_key_id": key_id, "pop_signature": pop_sig},
        headers=admin_headers, timeout=20,
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body.get("status") == "active"
    assert body.get("pop_verified") is True

    # listing - key appears in /api/public/keys with owner=partner
    keys = requests.get(f"{API}/public/keys", timeout=20)
    assert keys.status_code == 200
    payload = keys.json()
    items = payload.get("keys") if isinstance(payload, dict) else payload
    found = [k for k in items if k.get("public_key_id") == key_id or k.get("key_id") == key_id]
    assert found, f"key {key_id} not in /api/public/keys ({len(items)} keys)"
    assert found[0].get("owner") == "partner", found[0]


# 6. BYOS: configure local ES256 signer for sandbox tenant
def test_byos_sandbox_signer(admin_headers, sandbox_headers):
    cfg_body = {"type": "local", "algorithm": "ES256"}
    # NOTE: review_request said tenant_id=sandbox, but the sandbox API key is bound to tenant 'default'
    # (per backend/.env DEFAULT_TENANT_ID + api_key_service.ensure_sandbox_key). So to observe BYOS
    # affecting sandbox-key requests, configure the signer on the 'default' tenant.
    r = requests.post(f"{API}/admin/signers?tenant_id=default", json=cfg_body, headers=admin_headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    assert r.json().get("status") == "configured"

    try:
        # generate FEA with no signature_suite -> should default to ES256 per signer
        gen = requests.post(f"{API}/fea/generate", json=_fea_body(suffix="byos"), headers=sandbox_headers, timeout=20)
        assert gen.status_code == 200, gen.text
        algo = gen.json()["fea_payload"]["algorithm"]
        assert algo == "ES256", f"expected ES256 with BYOS signer, got {algo}"
        fea_id = gen.json()["fea_id"]
        v = requests.get(f"{API}/public/verify/{fea_id}", timeout=20)
        assert v.status_code == 200
        assert v.json()["signature_valid"] is True

        # health
        h = requests.get(f"{API}/admin/signers/health", headers=admin_headers, timeout=20)
        assert h.status_code == 200, h.text
        hj = h.json()
        default_signer = hj.get("default_signer") or hj.get("signers", {}).get("default")
        assert default_signer, hj
        assert default_signer.get("available") is True, default_signer
    finally:
        d = requests.delete(f"{API}/admin/signers?tenant_id=default", headers=admin_headers, timeout=20)
        assert d.status_code in (200, 204), d.text


# 7. Developer portal exposes signing capability
def test_developer_signing_block():
    r = requests.get(f"{API}/developer", timeout=20)
    assert r.status_code == 200
    data = r.json()
    signing = data.get("signing") or data.get("data", {}).get("signing")
    assert signing, f"no signing block in /api/developer (top keys={list(data.keys())[:20]})"
    suites = signing.get("signature_suites", {}).get("supported") or signing.get("signature_suites")
    assert set(["Ed25519", "ES256", "ES256K"]).issubset(set(suites)), suites
    assert signing.get("crypto_agility", {}).get("enabled") is True
    assert signing.get("federated_keys", {}).get("enabled") is True
    assert signing.get("byos", {}).get("enabled") is True
