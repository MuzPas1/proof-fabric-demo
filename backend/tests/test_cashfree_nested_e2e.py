"""E2E test: Cashfree nested webhook payload -> proof issued (iteration 35).

Verifies the adapter normalization fix by driving real HTTP through the
Cashfree HMAC path with a NESTED payload (data.order.order_id).
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


def _create_cashfree_integration(hdr, secret, field_map=None):
    slug = _slug("cfe2e")
    payload = {
        "name": "Cashfree E2E",
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
    if field_map:
        payload["field_map"] = field_map
    r = requests.post(f"{BASE}/api/admin/integrations", headers=hdr, json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create failed {r.status_code}: {r.text}"
    return slug


def _post(slug, secret, body_dict):
    raw = json.dumps(body_dict, separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    sig = _cf_sig(secret, ts, raw)
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

def test_cashfree_nested_order_id_ingests(hdr):
    secret = "cfsk_nested_" + uuid.uuid4().hex[:8]
    slug = _create_cashfree_integration(hdr, secret)
    order_id = f"order_{uuid.uuid4().hex[:8]}"
    body = {
        "data": {
            "order": {"order_id": order_id, "order_amount": 1.00, "order_currency": "INR"},
            "payment": {"cf_payment_id": 123456, "payment_status": "SUCCESS"},
            "customer_details": {"customer_id": "cust_1"},
        },
        "event_time": "2026-07-20T10:00:01+05:30",
        "type": "PAYMENT_SUCCESS_WEBHOOK",
    }
    r = _post(slug, secret, body)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
    data = r.json()
    assert data.get("fea_id"), f"no fea_id: {data}"
    # If response echoes external_id it must equal the nested order_id
    if "external_id" in data:
        assert data["external_id"] == order_id


def test_cashfree_fallback_cf_payment_id(hdr):
    secret = "cfsk_fb_" + uuid.uuid4().hex[:8]
    slug = _create_cashfree_integration(hdr, secret)
    body = {
        "data": {"payment": {"cf_payment_id": int(time.time())}},
        "type": "PAYMENT_USER_DROPPED_WEBHOOK",
    }
    r = _post(slug, secret, body)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
    assert r.json().get("fea_id")


def test_dotted_field_map_override_e2e(hdr):
    secret = "cfsk_dot_" + uuid.uuid4().hex[:8]
    slug = _create_cashfree_integration(hdr, secret, field_map={"external_id": "data.txn.ref"})
    body = {"data": {"txn": {"ref": f"TXN-{uuid.uuid4().hex[:6]}"}}, "type": "settlement"}
    r = _post(slug, secret, body)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
    assert r.json().get("fea_id")


def test_negative_no_identifier_returns_422(hdr):
    secret = "cfsk_neg_" + uuid.uuid4().hex[:8]
    slug = _create_cashfree_integration(hdr, secret)
    body = {"type": "noop", "data": {"order": {}}}
    r = _post(slug, secret, body)
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
    txt = r.text.lower()
    assert "event validation failed" in txt or "identifier" in txt


def test_flat_payload_regression(hdr):
    secret = "cfsk_flat_" + uuid.uuid4().hex[:8]
    slug = _create_cashfree_integration(hdr, secret)
    body = {
        "id": f"flat_{uuid.uuid4().hex[:8]}",
        "type": "invoice.created",
        "amount": 25000,
        "currency": "USD",
    }
    r = _post(slug, secret, body)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
    assert r.json().get("fea_id")
