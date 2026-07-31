"""Cashfree HMAC scheme verification (iteration 30).

Validates:
 - Creating hmac_sha256 integration with signature_scheme=cashfree + external secret
 - Cashfree-style webhook POST accepted (base64 sig, x-webhook-signature, ms timestamp)
 - Bad signature / hex sig / tampered body -> 401
 - Plain-HMAC regression: default scheme still works with PFP-minted secret / hex sig
"""
import os
import time
import uuid
import json
import hmac
import base64
import hashlib

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://jira-webhook-sim.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in login response: {r.text}"
    return tok


@pytest.fixture(scope="module")
def hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _uslug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _cashfree_sig(secret: str, ts: str, body: str) -> str:
    mac = hmac.new(secret.encode(), f"{ts}{body}".encode(), hashlib.sha256).digest()
    return base64.b64encode(mac).decode()


# ---------------- Cashfree scheme ----------------

def test_cashfree_create_integration(hdr):
    slug = _uslug("cf")
    payload = {
        "name": "Cashfree Test",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "auth_config": {"signature_scheme": "cashfree"},
        "secret": "cfsk_test_merchant_key",
    }
    r = requests.post(f"{BASE}/api/admin/integrations", headers=hdr, json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create failed {r.status_code}: {r.text}"
    data = r.json()
    assert data.get("slug") == slug
    assert data.get("enabled") is True
    # Server should NOT return the merchant secret. hmac_secret should not exist / be set.
    assert "cfsk_test_merchant_key" not in json.dumps(data)
    pytest.cashfree_slug = slug
    pytest.cashfree_secret = "cfsk_test_merchant_key"


def test_cashfree_valid_signature_accepted():
    slug = pytest.cashfree_slug
    secret = pytest.cashfree_secret
    body_dict = {"event": "PAYMENT_SUCCESS", "event_id": f"evt_{uuid.uuid4().hex[:10]}",
                 "order_id": f"ord_{uuid.uuid4().hex[:8]}", "amount": 100}
    raw = json.dumps(body_dict, separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    sig = _cashfree_sig(secret, ts, raw)
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={
            "Content-Type": "application/json",
            "x-webhook-timestamp": ts,
            "x-webhook-signature": sig,
        },
        timeout=20,
    )
    assert r.status_code == 201, f"expected 201 got {r.status_code}: {r.text}"
    data = r.json()
    assert data.get("fea_id"), f"no fea_id in response: {data}"


def test_cashfree_bad_signature_rejected():
    slug = pytest.cashfree_slug
    raw = json.dumps({"event": "PAYMENT_SUCCESS"}, separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    bogus = base64.b64encode(b"x" * 32).decode()
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={"Content-Type": "application/json",
                 "x-webhook-timestamp": ts, "x-webhook-signature": bogus},
        timeout=20,
    )
    assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"
    assert "invalid hmac_sha256 signature" in r.text.lower() or "authentication failed" in r.text.lower()


def test_cashfree_hex_signature_rejected():
    """Sending a HEX (rather than base64) signature must be rejected."""
    slug = pytest.cashfree_slug
    secret = pytest.cashfree_secret
    raw = json.dumps({"event": "PAYMENT_SUCCESS", "id": 1}, separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    hex_sig = hmac.new(secret.encode(), f"{ts}{raw}".encode(), hashlib.sha256).hexdigest()
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={"Content-Type": "application/json",
                 "x-webhook-timestamp": ts, "x-webhook-signature": hex_sig},
        timeout=20,
    )
    assert r.status_code == 401, f"expected 401 for hex sig, got {r.status_code}: {r.text}"


def test_cashfree_tampered_body_rejected():
    slug = pytest.cashfree_slug
    secret = pytest.cashfree_secret
    original = json.dumps({"event": "PAYMENT_SUCCESS", "amount": 100}, separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    sig = _cashfree_sig(secret, ts, original)
    # Tamper with the body but reuse the signature
    tampered = json.dumps({"event": "PAYMENT_SUCCESS", "amount": 999999}, separators=(",", ":"))
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=tampered.encode(),
        headers={"Content-Type": "application/json",
                 "x-webhook-timestamp": ts, "x-webhook-signature": sig},
        timeout=20,
    )
    assert r.status_code == 401, f"expected 401 for tampered body, got {r.status_code}: {r.text}"


# ---------------- Plain HMAC regression ----------------

def test_plain_hmac_create_and_verify(hdr):
    slug = _uslug("plain")
    payload = {
        "name": "Plain HMAC Test",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
    }
    r = requests.post(f"{BASE}/api/admin/integrations", headers=hdr, json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create failed {r.status_code}: {r.text}"
    created = r.json()
    # PFP should mint an hmac_secret and return it (or via a rotate/reveal path)
    secret = (created.get("credential")
              or created.get("hmac_secret")
              or created.get("secret")
              or (created.get("credentials") or {}).get("hmac_secret"))
    if not secret:
        # Try fetching via GET which may include the secret on creation-time
        r2 = requests.get(f"{BASE}/api/admin/integrations/{slug}", headers=hdr, timeout=15)
        if r2.status_code == 200:
            j = r2.json()
            secret = j.get("hmac_secret") or (j.get("credentials") or {}).get("hmac_secret")
    assert secret, f"no PFP-minted hmac_secret exposed at create: {created}"

    raw = json.dumps({"event": "test", "event_id": f"evt_{uuid.uuid4().hex[:10]}", "n": 1}, separators=(",", ":"))
    hex_sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={"Content-Type": "application/json", "x-pfp-signature": hex_sig},
        timeout=20,
    )
    assert r.status_code == 201, f"plain hmac ingest failed {r.status_code}: {r.text}"
    assert r.json().get("fea_id")

    # Bad sig rejected
    r_bad = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={"Content-Type": "application/json", "x-pfp-signature": "deadbeef"},
        timeout=20,
    )
    assert r_bad.status_code == 401, f"plain hmac bad sig expected 401 got {r_bad.status_code}"
