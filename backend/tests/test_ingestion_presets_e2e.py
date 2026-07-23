"""End-to-end HTTP tests for the provider-preset feature (iteration 31).

Covers:
 - GET /api/admin/integrations/presets returns 7 well-formed presets w/ no secrets
 - Preset-driven integration creation + webhook ingestion for Cashfree, Razorpay,
   GitHub, Shopify, Slack, Stripe
 - Generic (PFP-minted) HMAC regression: plain hex sig still works and bad sig 401
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

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://proof-fabric-1.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"

FORBIDDEN_SECRET_KEYS = {"hmac_secret", "external_secret", "secret", "token_hash", "basic_password_hash"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _uslug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _hex(secret: str, msg: bytes) -> str:
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def _b64(secret: str, msg: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), msg, hashlib.sha256).digest()).decode()


def _create_integration(hdr, slug, auth_config, secret):
    payload = {
        "name": f"Preset E2E {slug}",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "auth_config": auth_config,
        "secret": secret,
    }
    r = requests.post(f"{BASE}/api/admin/integrations", headers=hdr, json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create {slug}: {r.status_code} {r.text}"
    body = r.json()
    # secret must not leak in response
    assert secret not in json.dumps(body), f"secret leaked in create response for {slug}"
    return body


# ---------------------------------------------------------------------------
# 1) Presets registry endpoint
# ---------------------------------------------------------------------------
def test_presets_endpoint_returns_seven_no_secrets(hdr):
    r = requests.get(f"{BASE}/api/admin/integrations/presets", headers=hdr, timeout=15)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    data = r.json()
    presets = data.get("presets") or data
    assert isinstance(presets, list), f"expected list, got: {data!r}"
    ids = {p["id"] for p in presets}
    expected = {"generic", "cashfree", "stripe", "razorpay", "github", "slack", "shopify"}
    assert expected.issubset(ids), f"missing presets: {expected - ids}"
    for p in presets:
        assert p.get("auth_provider"), f"preset {p.get('id')} missing auth_provider"
        assert "auth_config" in p
        leaked = set(p.keys()) & FORBIDDEN_SECRET_KEYS
        assert not leaked, f"preset {p['id']} exposes secret keys: {leaked}"
        # nested check
        for k in (p.get("auth_config") or {}):
            assert k not in FORBIDDEN_SECRET_KEYS, f"auth_config leaks {k}"


def test_presets_endpoint_requires_auth():
    r = requests.get(f"{BASE}/api/admin/integrations/presets", timeout=15)
    assert r.status_code in (401, 403), f"expected auth challenge, got {r.status_code}"


# ---------------------------------------------------------------------------
# 2) Cashfree end-to-end
# ---------------------------------------------------------------------------
def test_cashfree_preset_e2e(hdr):
    slug = _uslug("cf")
    secret = "cfsk_test_" + uuid.uuid4().hex[:8]
    _create_integration(hdr, slug, {
        "signature_scheme": "cashfree",
        "signature_header": "x-webhook-signature",
        "signature_encoding": "base64",
        "timestamp_header": "x-webhook-timestamp",
    }, secret)

    body = json.dumps({"event": "PAYMENT_SUCCESS", "event_id": f"evt_{uuid.uuid4().hex[:10]}"},
                      separators=(",", ":")).encode()
    ts = str(int(time.time() * 1000))
    # Official Cashfree SDK: signatureString = timestamp + rawBody (NO dot separator)
    sig = _b64(secret, ts.encode() + body)
    r = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                      headers={"Content-Type": "application/json",
                               "x-webhook-timestamp": ts, "x-webhook-signature": sig}, timeout=20)
    assert r.status_code == 201, f"cashfree ingest: {r.status_code} {r.text}"
    assert r.json().get("fea_id")

    # Negative: old dot format must now FAIL
    ts2 = str(int(time.time() * 1000))
    body2 = json.dumps({"event": "PAYMENT_SUCCESS", "event_id": f"evt_{uuid.uuid4().hex[:10]}"},
                       separators=(",", ":")).encode()
    dot_sig = _b64(secret, f"{ts2}.".encode() + body2)
    r_dot = requests.post(f"{BASE}/api/ingest/{slug}", data=body2,
                          headers={"Content-Type": "application/json",
                                   "x-webhook-timestamp": ts2, "x-webhook-signature": dot_sig}, timeout=20)
    assert r_dot.status_code == 401, f"dot format should be rejected, got {r_dot.status_code}: {r_dot.text}"
    assert "invalid hmac_sha256 signature" in r_dot.text.lower() or "authentication failed" in r_dot.text.lower()

    r_bad = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                          headers={"Content-Type": "application/json",
                                   "x-webhook-timestamp": ts, "x-webhook-signature": "nope"}, timeout=20)
    assert r_bad.status_code == 401


# ---------------------------------------------------------------------------
# 3) Razorpay end-to-end
# ---------------------------------------------------------------------------
def test_razorpay_preset_e2e(hdr):
    slug = _uslug("rzp")
    secret = "rzp_whsec_" + uuid.uuid4().hex[:8]
    _create_integration(hdr, slug, {
        "signature_scheme": "plain",
        "signature_header": "x-razorpay-signature",
        "signature_encoding": "hex",
    }, secret)
    body = json.dumps({"event": "payment.captured",
                       "event_id": f"evt_{uuid.uuid4().hex[:10]}"}, separators=(",", ":")).encode()
    sig = _hex(secret, body)
    r = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                      headers={"Content-Type": "application/json",
                               "X-Razorpay-Signature": sig}, timeout=20)
    assert r.status_code == 201, f"razorpay: {r.status_code} {r.text}"
    assert r.json().get("fea_id")

    r_bad = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                          headers={"Content-Type": "application/json",
                                   "X-Razorpay-Signature": "deadbeef"}, timeout=20)
    assert r_bad.status_code == 401


# ---------------------------------------------------------------------------
# 4) GitHub end-to-end
# ---------------------------------------------------------------------------
def test_github_preset_e2e(hdr):
    slug = _uslug("gh")
    secret = "ghsecret_" + uuid.uuid4().hex[:8]
    _create_integration(hdr, slug, {
        "signature_scheme": "plain",
        "signature_header": "x-hub-signature-256",
        "signature_prefix": "sha256=",
        "signature_encoding": "hex",
    }, secret)
    body = json.dumps({"zen": "Keep it simple",
                       "event_id": f"evt_{uuid.uuid4().hex[:10]}"}, separators=(",", ":")).encode()
    sig = "sha256=" + _hex(secret, body)
    r = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                      headers={"Content-Type": "application/json",
                               "X-Hub-Signature-256": sig}, timeout=20)
    assert r.status_code == 201, f"github: {r.status_code} {r.text}"
    assert r.json().get("fea_id")


# ---------------------------------------------------------------------------
# 5) Shopify end-to-end
# ---------------------------------------------------------------------------
def test_shopify_preset_e2e(hdr):
    slug = _uslug("shop")
    secret = "shpss_" + uuid.uuid4().hex[:8]
    _create_integration(hdr, slug, {
        "signature_scheme": "plain",
        "signature_header": "x-shopify-hmac-sha256",
        "signature_encoding": "base64",
    }, secret)
    body = json.dumps({"order_id": 123,
                       "event_id": f"evt_{uuid.uuid4().hex[:10]}"}, separators=(",", ":")).encode()
    sig = _b64(secret, body)
    r = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                      headers={"Content-Type": "application/json",
                               "X-Shopify-Hmac-Sha256": sig}, timeout=20)
    assert r.status_code == 201, f"shopify: {r.status_code} {r.text}"
    assert r.json().get("fea_id")


# ---------------------------------------------------------------------------
# 6) Slack end-to-end (timestamp + v0= prefix)
# ---------------------------------------------------------------------------
def test_slack_preset_e2e(hdr):
    slug = _uslug("slack")
    secret = "slack_signing_" + uuid.uuid4().hex[:8]
    _create_integration(hdr, slug, {
        "signature_scheme": "slack",
        "signature_header": "x-slack-signature",
        "timestamp_header": "x-slack-request-timestamp",
        "signature_prefix": "v0=",
        "signature_encoding": "hex",
    }, secret)
    body = json.dumps({"token": "abc", "team_id": "T1",
                       "event_id": f"evt_{uuid.uuid4().hex[:10]}"}, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    sig = "v0=" + _hex(secret, f"v0:{ts}:".encode() + body)
    r = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                      headers={"Content-Type": "application/json",
                               "X-Slack-Signature": sig,
                               "X-Slack-Request-Timestamp": ts}, timeout=20)
    # Slack may not be strictly required by review; accept 201 or gracefully skip on non-401 issue
    assert r.status_code == 201, f"slack: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# 7) Stripe end-to-end (t=,v1=)
# ---------------------------------------------------------------------------
def test_stripe_preset_e2e(hdr):
    slug = _uslug("stripe")
    secret = "whsec_" + uuid.uuid4().hex[:8]
    _create_integration(hdr, slug, {
        "signature_scheme": "stripe",
        "signature_header": "stripe-signature",
        "signature_encoding": "hex",
    }, secret)
    body = json.dumps({"id": f"evt_{uuid.uuid4().hex[:10]}",
                       "type": "charge.succeeded"}, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    v1 = _hex(secret, f"{ts}.".encode() + body)
    r = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                      headers={"Content-Type": "application/json",
                               "Stripe-Signature": f"t={ts},v1={v1}"}, timeout=20)
    assert r.status_code == 201, f"stripe: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# 8) Regression: generic plain HMAC (PFP-minted)
# ---------------------------------------------------------------------------
def test_generic_pfp_minted_hmac_regression(hdr):
    slug = _uslug("gen")
    r = requests.post(f"{BASE}/api/admin/integrations", headers=hdr, json={
        "name": "Generic PFP", "slug": slug, "adapter": "generic",
        "auth_provider": "hmac_sha256",
    }, timeout=15)
    assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
    created = r.json()
    secret = (created.get("credential") or created.get("hmac_secret")
              or created.get("secret") or (created.get("credentials") or {}).get("hmac_secret"))
    assert secret, f"no PFP-minted hmac_secret at create: {created}"

    body = json.dumps({"event": "test", "event_id": f"evt_{uuid.uuid4().hex[:10]}"},
                      separators=(",", ":")).encode()
    sig = _hex(secret, body)
    r = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                      headers={"Content-Type": "application/json",
                               "X-PFP-Signature": sig}, timeout=20)
    assert r.status_code == 201, f"generic ingest: {r.status_code} {r.text}"
    assert r.json().get("fea_id")

    r_bad = requests.post(f"{BASE}/api/ingest/{slug}", data=body,
                          headers={"Content-Type": "application/json",
                                   "X-PFP-Signature": "deadbeef"}, timeout=20)
    assert r_bad.status_code == 401
