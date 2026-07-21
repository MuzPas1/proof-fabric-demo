"""End-to-end HTTP tests for the generic HMAC provider — Tazapay body-field
signed payload, plus Cashfree and Razorpay regressions.

The generic branch of HmacProvider now supports `{body:dotted.path}` in
`signed_payload_format` and an optional `timestamp_field` from the body — this
is what unblocks Tazapay (signs event_id + rawBody + created_at with NO
separator, base64 in the `webhook-signature` header).
"""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"

UA = {"User-Agent": "Mozilla/5.0 (pytest ingestion e2e)"}


# ---------------- fixtures ----------------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers=UA, timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", **UA}


def _create_integration(admin_headers, *, slug, secret, auth_config):
    body = {
        "name": f"E2E {slug}",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "secret": secret,
        "auth_config": auth_config,
    }
    r = requests.post(f"{BASE_URL}/api/admin/integrations",
                      json=body, headers=admin_headers, timeout=15)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    data = r.json()
    iid = data.get("integration_id") or data.get("id")
    assert iid
    # enable
    e = requests.post(f"{BASE_URL}/api/admin/integrations/{iid}/enable",
                      headers=admin_headers, timeout=15)
    assert e.status_code in (200, 204), f"enable failed: {e.status_code} {e.text}"
    return iid


def _delete_integration(admin_headers, iid):
    try:
        requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}",
                        headers=admin_headers, timeout=10)
    except Exception:
        pass


# ---------------- Tazapay body-field HMAC ----------------

def test_tazapay_generic_body_field_hmac_accepted(admin_headers):
    slug = f"tazapay-e2e-{uuid.uuid4().hex[:8]}"
    secret = "tzp_test_secret_" + uuid.uuid4().hex[:12]
    auth_config = {
        "signature_header": "webhook-signature",
        "signature_encoding": "base64",
        "signed_payload_format": "{body:id}{body}{body:created_at}",
        "timestamp_field": "created_at",
    }
    iid = _create_integration(admin_headers, slug=slug, secret=secret, auth_config=auth_config)
    try:
        event_id = f"evt_test_{uuid.uuid4().hex[:10]}"
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        payload = {
            "id": event_id,
            "type": "payment.completed",
            "created_at": created_at,
            "data": {"id": f"pay_{uuid.uuid4().hex[:12]}", "amount": 1234, "currency": "USD"},
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signed = event_id.encode() + raw_body + created_at.encode()
        sig = base64.b64encode(hmac.new(secret.encode(), signed, hashlib.sha256).digest()).decode()

        headers = {"Content-Type": "application/json", "webhook-signature": sig, **UA}
        r = requests.post(f"{BASE_URL}/api/ingest/{slug}",
                          data=raw_body, headers=headers, timeout=20)
        assert r.status_code in (200, 201), f"expected 201, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("fea_id") or body.get("id") or body.get("accepted"), body
    finally:
        _delete_integration(admin_headers, iid)


def test_tazapay_generic_body_field_hmac_bad_sig_rejected(admin_headers):
    slug = f"tazapay-bad-{uuid.uuid4().hex[:8]}"
    secret = "tzp_test_secret_" + uuid.uuid4().hex[:12]
    auth_config = {
        "signature_header": "webhook-signature",
        "signature_encoding": "base64",
        "signed_payload_format": "{body:id}{body}{body:created_at}",
        "timestamp_field": "created_at",
    }
    iid = _create_integration(admin_headers, slug=slug, secret=secret, auth_config=auth_config)
    try:
        event_id = f"evt_test_{uuid.uuid4().hex[:10]}"
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        payload = {"id": event_id, "type": "payment.completed", "created_at": created_at,
                   "data": {"id": "pay_xyz"}}
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        bad_sig = base64.b64encode(b"\x00" * 32).decode()

        r = requests.post(f"{BASE_URL}/api/ingest/{slug}",
                          data=raw_body,
                          headers={"Content-Type": "application/json",
                                   "webhook-signature": bad_sig, **UA},
                          timeout=20)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"
    finally:
        _delete_integration(admin_headers, iid)


# ---------------- Cashfree regression ----------------

def test_cashfree_scheme_regression(admin_headers):
    slug = f"cashfree-e2e-{uuid.uuid4().hex[:8]}"
    secret = "cf_test_secret_" + uuid.uuid4().hex[:12]
    iid = _create_integration(admin_headers, slug=slug, secret=secret,
                              auth_config={"signature_scheme": "cashfree"})
    try:
        order_id = f"ord_{uuid.uuid4().hex[:10]}"
        payload = {"type": "PAYMENT_SUCCESS_WEBHOOK",
                   "data": {"order": {"order_id": order_id, "order_amount": 100},
                            "payment": {"payment_status": "SUCCESS"}}}
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ts_ms = str(int(time.time() * 1000))
        signed = (ts_ms.encode() + raw_body)
        sig = base64.b64encode(hmac.new(secret.encode(), signed, hashlib.sha256).digest()).decode()

        r = requests.post(f"{BASE_URL}/api/ingest/{slug}",
                          data=raw_body,
                          headers={"Content-Type": "application/json",
                                   "x-webhook-signature": sig,
                                   "x-webhook-timestamp": ts_ms, **UA},
                          timeout=20)
        assert r.status_code in (200, 201), f"expected 201, got {r.status_code}: {r.text}"
    finally:
        _delete_integration(admin_headers, iid)


# ---------------- Razorpay plain HMAC regression ----------------

def test_razorpay_style_plain_hex_hmac_regression(admin_headers):
    slug = f"razorpay-e2e-{uuid.uuid4().hex[:8]}"
    secret = "rzp_test_secret_" + uuid.uuid4().hex[:12]
    iid = _create_integration(
        admin_headers, slug=slug, secret=secret,
        auth_config={"signature_header": "x-razorpay-signature"},
    )
    try:
        payload = {"id": f"evt_{uuid.uuid4().hex[:10]}",
                   "event": "payment.captured",
                   "payload": {"payment": {"entity": {"id": f"pay_{uuid.uuid4().hex[:10]}",
                                                        "amount": 500}}}}
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

        r = requests.post(f"{BASE_URL}/api/ingest/{slug}",
                          data=raw_body,
                          headers={"Content-Type": "application/json",
                                   "x-razorpay-signature": sig, **UA},
                          timeout=20)
        assert r.status_code in (200, 201), f"expected 201, got {r.status_code}: {r.text}"
    finally:
        _delete_integration(admin_headers, iid)
