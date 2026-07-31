"""E2E tests for DocuSign HMAC verification + regression on other providers.

Covers:
- Valid DocuSign webhook (X-DocuSign-Signature-1)
- Missing signature header -> 401 with detailed reason
- Bad signature -> 401
- Multi-key any-match (sig-1 wrong, sig-2 correct) -> 201
- Case-insensitive header -> 201
- Exact-bytes verification (tamper trailing space) -> 401
- Regression: Razorpay, Cashfree, GitHub HMAC webhooks still work
"""
import os
import hmac
import hashlib
import base64
import json
import time
import secrets
import uuid
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://jira-webhook-sim.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = 'admin@pfprotocol.com'
ADMIN_PASSWORD = 'PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT'

DOCUSIGN_SLUG = 'docusign-test'
DOCUSIGN_SECRET = 'ds_preview_secret_123'


def _b64_hmac_sha256(secret: str, body: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def _hex_hmac_sha256(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


# ---------------- DocuSign tests ----------------

class TestDocuSignHmac:
    def _post(self, slug, body_bytes, headers):
        return requests.post(f"{BASE_URL}/api/ingest/{slug}",
                             data=body_bytes,
                             headers={"Content-Type": "application/json", **headers},
                             timeout=15)

    def test_valid_signature(self):
        env_id = f"ENV-TEST-{secrets.token_hex(4)}"
        body = json.dumps({"event": "envelope-completed",
                           "data": {"envelopeId": env_id, "status": "completed"}}).encode()
        sig = _b64_hmac_sha256(DOCUSIGN_SECRET, body)
        r = self._post(DOCUSIGN_SLUG, body, {"X-DocuSign-Signature-1": sig})
        assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("status") == "accepted"
        assert data.get("event_id") == env_id
        assert "fea_id" in data and data["fea_id"]

    def test_missing_signature(self):
        body = json.dumps({"event": "envelope-completed",
                           "data": {"envelopeId": "ENV-MISSING", "status": "completed"}}).encode()
        r = self._post(DOCUSIGN_SLUG, body, {})
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"
        reason = r.text.lower()
        assert "scheme=docusign" in reason, f"reason missing scheme=docusign: {r.text}"
        assert "header=missing" in reason, f"reason missing header=missing: {r.text}"
        assert "headers_seen" in reason, f"reason missing headers_seen: {r.text}"

    def test_bad_signature(self):
        body = json.dumps({"event": "envelope-completed",
                           "data": {"envelopeId": "ENV-BAD", "status": "completed"}}).encode()
        r = self._post(DOCUSIGN_SLUG, body, {"X-DocuSign-Signature-1": "AAAAinvalidBASE64sig=="})
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"
        low = r.text.lower()
        assert "scheme=docusign" in low
        assert "header=present" in low

    def test_multi_key_any_match(self):
        env_id = f"ENV-MULTI-{secrets.token_hex(4)}"
        body = json.dumps({"event": "envelope-completed",
                           "data": {"envelopeId": env_id, "status": "completed"}}).encode()
        good = _b64_hmac_sha256(DOCUSIGN_SECRET, body)
        r = self._post(DOCUSIGN_SLUG, body, {
            "X-DocuSign-Signature-1": "WRONGSIG",
            "X-DocuSign-Signature-2": good,
        })
        assert r.status_code == 201, f"expected 201 got {r.status_code}: {r.text}"
        assert r.json().get("event_id") == env_id

    def test_case_insensitive_header(self):
        env_id = f"ENV-CASE-{secrets.token_hex(4)}"
        body = json.dumps({"event": "envelope-completed",
                           "data": {"envelopeId": env_id, "status": "completed"}}).encode()
        sig = _b64_hmac_sha256(DOCUSIGN_SECRET, body)
        r = self._post(DOCUSIGN_SLUG, body, {"x-docusign-signature-1": sig})
        assert r.status_code == 201, f"expected 201 got {r.status_code}: {r.text}"

    def test_exact_bytes_tamper(self):
        body = json.dumps({"event": "envelope-completed",
                           "data": {"envelopeId": "ENV-TAMPER", "status": "completed"}}).encode()
        sig = _b64_hmac_sha256(DOCUSIGN_SECRET, body)
        tampered = body + b" "
        r = self._post(DOCUSIGN_SLUG, tampered, {"X-DocuSign-Signature-1": sig})
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"


# ---------------- Regression tests ----------------

def _create_integration(token, payload):
    r = requests.post(f"{BASE_URL}/api/admin/integrations",
                      headers={"Authorization": f"Bearer {token}"},
                      json=payload, timeout=15)
    return r


class TestRegressionOtherProviders:
    def test_razorpay(self, admin_token):
        slug = f"rzp-test-{secrets.token_hex(3)}"
        secret = f"rzp_secret_{secrets.token_hex(6)}"
        payload = {
            "slug": slug,
            "name": "Razorpay Regression",
            "adapter": "generic",
            "auth_provider": "hmac_sha256",
            "auth_config": {
                "signature_scheme": "plain",
                "signature_header": "x-razorpay-signature",
                "signature_encoding": "hex",
            },
            "secret": secret,
        }
        r = _create_integration(admin_token, payload)
        if r.status_code not in (200, 201):
            pytest.skip(f"Could not create razorpay integration: {r.status_code} {r.text[:200]}")
        body = json.dumps({"event": "payment.captured",
                           "payload": {"payment": {"entity": {"id": f"pay_{secrets.token_hex(6)}"}}}}).encode()
        sig = _hex_hmac_sha256(secret, body)
        resp = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                             headers={"Content-Type": "application/json",
                                      "X-Razorpay-Signature": sig}, timeout=15)
        assert resp.status_code == 201, f"razorpay expected 201 got {resp.status_code}: {resp.text}"

    def test_cashfree(self, admin_token):
        slug = f"cf-test-{secrets.token_hex(3)}"
        secret = f"cf_secret_{secrets.token_hex(6)}"
        payload = {
            "slug": slug,
            "name": "Cashfree Regression",
            "adapter": "generic",
            "auth_provider": "hmac_sha256",
            "auth_config": {
                "signature_scheme": "cashfree",
                "signature_header": "x-webhook-signature",
                "signature_encoding": "base64",
                "timestamp_header": "x-webhook-timestamp",
            },
            "require_timestamp": True,
            "timestamp_tolerance_seconds": 300,
            "secret": secret,
        }
        r = _create_integration(admin_token, payload)
        if r.status_code not in (200, 201):
            pytest.skip(f"Could not create cashfree integration: {r.status_code} {r.text[:200]}")
        ts = str(int(time.time()))
        body = json.dumps({"type": "PAYMENT_SUCCESS_WEBHOOK",
                           "data": {"order": {"order_id": f"ord_{secrets.token_hex(6)}"}}}).encode()
        signed = (ts.encode() + body)
        sig = base64.b64encode(hmac.new(secret.encode(), signed, hashlib.sha256).digest()).decode()
        resp = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                             headers={"Content-Type": "application/json",
                                      "x-webhook-signature": sig,
                                      "x-webhook-timestamp": ts}, timeout=15)
        assert resp.status_code == 201, f"cashfree expected 201 got {resp.status_code}: {resp.text}"

    def test_github(self, admin_token):
        slug = f"gh-test-{secrets.token_hex(3)}"
        secret = f"gh_secret_{secrets.token_hex(6)}"
        payload = {
            "slug": slug,
            "name": "GitHub Regression",
            "adapter": "generic",
            "auth_provider": "hmac_sha256",
            "auth_config": {
                "signature_scheme": "plain",
                "signature_header": "x-hub-signature-256",
                "signature_prefix": "sha256=",
                "signature_encoding": "hex",
            },
            "secret": secret,
        }
        r = _create_integration(admin_token, payload)
        if r.status_code not in (200, 201):
            pytest.skip(f"Could not create github integration: {r.status_code} {r.text[:200]}")
        body = json.dumps({"action": "opened",
                           "issue": {"id": secrets.randbelow(10_000_000),
                                     "number": 42,
                                     "node_id": f"MDU6SXNzdWV{secrets.token_hex(4)}"}}).encode()
        sig = "sha256=" + _hex_hmac_sha256(secret, body)
        resp = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                             headers={"Content-Type": "application/json",
                                      "X-Hub-Signature-256": sig,
                                      "X-GitHub-Event": "issues"}, timeout=15)
        assert resp.status_code == 201, f"github expected 201 got {resp.status_code}: {resp.text}"
