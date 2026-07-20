"""E2E tests (iteration 36): recursive deep-search identifier fallback and
non-sensitive missing-id diagnostic on the /api/ingest/{slug} Cashfree path.

Complements test_cashfree_nested_e2e.py by covering:
  * DEEP-NEST fallback (id nested deeper than aliased dotted paths)
  * cf_payment_id-only fallback (regression re-check)
  * MISSING-ID diagnostic: 422 with 'Payload structure: top-level keys=...;
    data.* keys=...' — key NAMES only, no VALUES leaked.
  * Regression: flat id, and bad-signature short-circuits before normalize.
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

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL not set"
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _cf_sig(secret: str, ts: str, body: str) -> str:
    mac = hmac.new(secret.encode(), f"{ts}{body}".encode(), hashlib.sha256).digest()
    return base64.b64encode(mac).decode()


def _create_cf(hdr, secret):
    slug = _slug("cfdeep")
    payload = {
        "name": "Cashfree Deep",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "auth_config": {
            "signature_scheme": "cashfree",
            "signature_header": "x-webhook-signature",
            "signature_encoding": "base64",
            "timestamp_header": "x-webhook-timestamp",
        },
        "secret": secret,
        "default_currency": "INR",
    }
    r = requests.post(f"{BASE}/api/admin/integrations", headers=hdr, json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create failed {r.status_code}: {r.text}"
    return slug


def _post(slug, secret, body_dict, tamper=False):
    raw = json.dumps(body_dict, separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    sig = _cf_sig(secret, ts, raw)
    if tamper:
        sig = base64.b64encode(b"x" * 32).decode()
    return requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={
            "Content-Type": "application/json",
            "x-webhook-timestamp": ts,
            "x-webhook-signature": sig,
        },
        timeout=20,
    )


# ---------------- Tests ----------------

def test_deep_nested_order_id_resolves_via_recursive_search(hdr):
    """Payload nests order_id one level deeper than the alias path -> should still 201."""
    secret = "cfsk_deep_" + uuid.uuid4().hex[:8]
    slug = _create_cf(hdr, secret)
    order_id = f"deep_{uuid.uuid4().hex[:8]}"
    body = {
        "type": "PAYMENT_SUCCESS_WEBHOOK",
        "data": {"wrapper": {"order": {"order_id": order_id}}},
    }
    r = _post(slug, secret, body)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
    assert r.json().get("fea_id")


def test_cf_payment_id_only_fallback(hdr):
    secret = "cfsk_cfp_" + uuid.uuid4().hex[:8]
    slug = _create_cf(hdr, secret)
    body = {"type": "PAYMENT_USER_DROPPED_WEBHOOK",
            "data": {"payment": {"cf_payment_id": int(time.time())}}}
    r = _post(slug, secret, body)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
    assert r.json().get("fea_id")


def test_missing_id_returns_422_with_structure_hint_names_only(hdr):
    """422 must include 'Payload structure: top-level keys=[...]; data.* keys=[...]'
    with KEY NAMES only. No payload VALUES may leak in the error body."""
    secret = "cfsk_miss_" + uuid.uuid4().hex[:8]
    slug = _create_cf(hdr, secret)
    # Use distinctive VALUES that must NOT appear in the response.
    secret_value = "SECRET_VALUE_LEAK_CHECK_" + uuid.uuid4().hex
    body = {
        "type": "PING",
        "data": {"meta": {"note": secret_value, "correlation": "corrVALUEmustNotLeak"}},
    }
    r = _post(slug, secret, body)
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
    text = r.text
    # Structure diagnostic present with key NAMES
    assert "Payload structure" in text, f"missing structure hint: {text}"
    assert "top-level keys=" in text, f"missing top-level keys hint: {text}"
    assert "data.* keys=" in text, f"missing data.* keys hint: {text}"
    # Key NAMES appear
    assert "type" in text and "data" in text and "meta" in text
    # VALUES must NOT appear
    assert secret_value not in text, "payload value leaked in error!"
    assert "corrVALUEmustNotLeak" not in text, "payload value leaked in error!"
    assert "PING" not in text, f"payload value 'PING' leaked in error: {text}"


def test_flat_id_regression(hdr):
    secret = "cfsk_flat2_" + uuid.uuid4().hex[:8]
    slug = _create_cf(hdr, secret)
    body = {"id": f"flat_{uuid.uuid4().hex[:8]}", "type": "invoice.created"}
    r = _post(slug, secret, body)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
    assert r.json().get("fea_id")


def test_bad_signature_rejected_before_normalize(hdr):
    """Auth must run before normalization: bad signature must yield 401,
    NOT 422 (and must not expose payload structure)."""
    secret = "cfsk_bad_" + uuid.uuid4().hex[:8]
    slug = _create_cf(hdr, secret)
    body = {"type": "PING", "data": {"order": {"order_id": "x"}}}
    r = _post(slug, secret, body, tamper=True)
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"
    assert "Payload structure" not in r.text
