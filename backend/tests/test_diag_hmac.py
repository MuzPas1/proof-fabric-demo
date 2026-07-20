"""Iteration 33 — HMAC diagnostic instrumentation tests.

Verifies non-sensitive diagnostic suffix added to 401 responses AND the
integration public view now surfaces has_hmac_secret / has_external_secret /
signature_scheme booleans. No secret value must ever appear.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://fea-gateway.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"

CASHFREE_SECRET = "cfsk_diag"


@pytest.fixture(scope="module")
def hdr():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _slug(p):
    return f"{p}-{uuid.uuid4().hex[:10]}"


# --- Cashfree diagnostic ----------------------------------------------------

def test_cashfree_create_and_diag(hdr):
    slug = _slug("cfdiag")
    payload = {
        "name": "Cashfree Diag",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "auth_config": {
            "signature_scheme": "cashfree",
            "signature_header": "x-webhook-signature",
            "signature_encoding": "base64",
            "timestamp_header": "x-webhook-timestamp",
        },
        "secret": CASHFREE_SECRET,
    }
    r = requests.post(f"{BASE}/api/admin/integrations", headers=hdr, json=payload, timeout=20)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    # Secret never in response
    assert CASHFREE_SECRET not in json.dumps(data)
    # New diagnostic fields present
    assert data.get("signature_scheme") == "cashfree", data
    assert data.get("has_external_secret") is True, data
    assert data.get("has_hmac_secret") is False, data
    pytest.cf_slug = slug
    pytest.cf_iid = data.get("integration_id")


def test_cashfree_bad_sig_diag_reason():
    slug = pytest.cf_slug
    raw = json.dumps({"event": "PAYMENT_SUCCESS", "event_id": f"e_{uuid.uuid4().hex[:8]}"},
                     separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    bogus = base64.b64encode(b"x" * 32).decode()
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={"Content-Type": "application/json",
                 "x-webhook-timestamp": ts, "x-webhook-signature": bogus},
        timeout=20,
    )
    assert r.status_code == 401, r.text
    body = r.text
    # Diag suffix
    assert "scheme=cashfree" in body, body
    assert "enc=base64" in body, body
    assert "header=present" in body, body
    assert "secret=external" in body, body
    # No secret leak
    assert CASHFREE_SECRET not in body


def test_cashfree_public_get_diag(hdr):
    # via list
    r = requests.get(f"{BASE}/api/admin/integrations", headers=hdr, timeout=15)
    assert r.status_code == 200, r.text
    all_text = r.text
    assert CASHFREE_SECRET not in all_text
    body = r.json()
    items = body if isinstance(body, list) else (body.get("integrations") or body.get("items") or [])
    found = next((i for i in items if i.get("slug") == pytest.cf_slug), None)
    assert found is not None, f"integration {pytest.cf_slug} not in list; sample keys={list(body)[:5] if isinstance(body, dict) else 'list'}"
    assert found.get("signature_scheme") == "cashfree"
    assert found.get("has_external_secret") is True
    assert found.get("has_hmac_secret") is False
    # Direct GET by id
    r2 = requests.get(f"{BASE}/api/admin/integrations/{pytest.cf_iid}", headers=hdr, timeout=15)
    assert r2.status_code == 200, r2.text
    j = r2.json()
    assert j.get("signature_scheme") == "cashfree"
    assert j.get("has_external_secret") is True
    assert j.get("has_hmac_secret") is False
    assert CASHFREE_SECRET not in r2.text


def test_cashfree_valid_still_works():
    slug = pytest.cf_slug
    raw = json.dumps({"event": "PAYMENT_SUCCESS",
                      "event_id": f"e_{uuid.uuid4().hex[:10]}",
                      "amount": 250}, separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    mac = hmac.new(CASHFREE_SECRET.encode(), f"{ts}{raw}".encode(), hashlib.sha256).digest()
    sig = base64.b64encode(mac).decode()
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={"Content-Type": "application/json",
                 "x-webhook-timestamp": ts, "x-webhook-signature": sig},
        timeout=20,
    )
    assert r.status_code == 201, r.text
    assert r.json().get("fea_id")


# --- Generic hmac (plain) diagnostic ---------------------------------------

def test_generic_create_and_diag(hdr):
    slug = _slug("plaindiag")
    payload = {
        "name": "Plain Diag",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
    }
    r = requests.post(f"{BASE}/api/admin/integrations", headers=hdr, json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    secret = (data.get("credential") or data.get("hmac_secret") or data.get("secret")
              or (data.get("credentials") or {}).get("hmac_secret"))
    assert secret, f"expected minted secret in create response: {data}"
    pytest.plain_slug = slug
    pytest.plain_secret = secret
    # Diag fields
    assert data.get("signature_scheme") == "plain"
    assert data.get("has_hmac_secret") is True
    assert data.get("has_external_secret") is False


def test_generic_bad_sig_diag_reason():
    slug = pytest.plain_slug
    raw = json.dumps({"event": "x", "event_id": f"e_{uuid.uuid4().hex[:8]}"},
                     separators=(",", ":"))
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={"Content-Type": "application/json", "x-pfp-signature": "deadbeef"},
        timeout=20,
    )
    assert r.status_code == 401, r.text
    body = r.text
    assert "scheme=plain" in body, body
    assert "enc=hex" in body, body
    assert "header=present" in body, body
    assert "secret=minted" in body, body
    # Secret never leaked
    assert pytest.plain_secret not in body


def test_generic_valid_still_works():
    slug = pytest.plain_slug
    secret = pytest.plain_secret
    raw = json.dumps({"event": "test", "event_id": f"e_{uuid.uuid4().hex[:10]}"},
                     separators=(",", ":"))
    hex_sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={"Content-Type": "application/json", "x-pfp-signature": hex_sig},
        timeout=20,
    )
    assert r.status_code == 201, r.text
    assert r.json().get("fea_id")


# --- Regression: no secret leakage across list/get responses ---------------

def test_no_secret_leak_in_public_views(hdr):
    r = requests.get(f"{BASE}/api/admin/integrations", headers=hdr, timeout=15)
    assert r.status_code == 200
    body = r.text
    assert CASHFREE_SECRET not in body
    assert pytest.plain_secret not in body
    # Generic sensitive keys must not appear in public view
    for forbidden in ("hmac_secret", "external_secret", "token_hash", "basic_password_hash"):
        assert f'"{forbidden}"' not in body, f"public view leaks {forbidden}"


# --- Other presets diagnostic scheme sanity (stripe/slack) -----------------

@pytest.mark.parametrize("scheme,header,enc", [
    ("stripe", "stripe-signature", "hex"),
    ("slack",  "x-slack-signature", "hex"),
])
def test_other_preset_bad_sig_diag(hdr, scheme, header, enc):
    slug = _slug(f"{scheme}diag")
    payload = {
        "name": f"{scheme} diag",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "auth_config": {"signature_scheme": scheme},
        "secret": f"ext_{scheme}_key",
    }
    r = requests.post(f"{BASE}/api/admin/integrations", headers=hdr, json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    created = r.json()
    assert created.get("signature_scheme") == scheme
    assert created.get("has_external_secret") is True

    raw = json.dumps({"id": f"e_{uuid.uuid4().hex[:8]}", "type": "x"}, separators=(",", ":"))
    r = requests.post(
        f"{BASE}/api/ingest/{slug}",
        data=raw.encode(),
        headers={"Content-Type": "application/json",
                 header: "sha256=deadbeef" if scheme != "stripe" else "t=1,v1=deadbeef",
                 "x-slack-request-timestamp": str(int(time.time()))},
        timeout=20,
    )
    assert r.status_code == 401, r.text
    body = r.text
    assert f"scheme={scheme}" in body, body
    assert f"enc={enc}" in body, body
    assert "secret=external" in body, body
    assert f"ext_{scheme}_key" not in body
