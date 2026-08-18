"""Regression test after removing emergentintegrations from requirements.txt.
Verifies backend startup, auth, Tarabut proof pipeline, and ingestion framework."""
import os
import uuid
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback to reading frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PW = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_health():
    r = requests.get(f"{BASE}/api/health", timeout=10)
    assert r.status_code == 200


def test_auth_login(token):
    assert isinstance(token, str) and len(token) > 10


def test_tarabut_prove_and_public_verify(headers):
    event = {
        "type": "PAYMENT_STATUS_CHANGE",
        "paymentId": "ci-regress-1",
        "status": "COMPLETED",
        "amount": 10.95,
        "currency": "BHD",
        "payerToken": "tok",
        "destinationAccount": "BHD1",
    }
    r = requests.post(f"{BASE}/api/admin/tarabut/prove-event", headers=headers, json={"event": event}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    fea_id = data.get("fea_id") or (data.get("artifact") or {}).get("fea_id")
    assert fea_id, f"no fea_id in {data}"

    # Public verify
    r2 = requests.get(f"{BASE}/api/fea/public/{fea_id}", timeout=15)
    assert r2.status_code == 200, r2.text
    pub = r2.json()
    assert pub.get("valid") is True, f"not valid: {pub}"
    # PII check
    body_str = r2.text
    assert "tok" not in body_str or "payerToken" not in body_str, "payerToken leak"
    # more precise: ensure raw payerToken value 'tok' not present as PII field
    assert '"payerToken"' not in body_str, "payerToken field leaked in public payload"


def test_presets_lists_all_10(headers):
    r = requests.get(f"{BASE}/api/admin/integrations/presets", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    presets = data.get("presets") or data
    ids = {p.get("id") for p in presets}
    expected = {"generic", "cashfree", "stripe", "razorpay", "github", "slack", "docusign", "shopify", "jira", "tarabut"}
    assert expected.issubset(ids), f"missing presets: {expected - ids}"


def test_integration_create_and_simulate(headers):
    slug = f"ci-regress-{uuid.uuid4().hex[:8]}"
    payload = {
        "provider": "generic",
        "slug": slug,
        "name": "CI Regress",
        "auth_type": "hmac_sha256",
        "secret": "s" * 32,
    }
    r = requests.post(f"{BASE}/api/admin/integrations", headers=headers, json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    iid = r.json().get("integration_id") or r.json().get("id")
    assert iid
    try:
        sr = requests.post(f"{BASE}/api/admin/integrations/{iid}/simulate", headers=headers, json={}, timeout=30)
        assert sr.status_code == 200, sr.text
        sd = sr.json()
        assert sd.get("ok") is True, f"simulate not ok: {sd}"
    finally:
        requests.delete(f"{BASE}/api/admin/integrations/{iid}", headers=headers, timeout=15)
