"""End-to-end tests for Tarabut Gateway OAuth wiring + RS256 webhook + regression.

Covers the review request:
 1) POST /api/admin/tarabut/oauth-config stores creds; secret redacted in public view
 2) POST /api/admin/tarabut/connectivity - live sandbox token acquisition
 3) POST /api/admin/tarabut/connect/intent - live Create Intent + PFP proof
 4) GET  /api/fea/public/{fea_id} - descriptor/auth_method/PII redaction
 5) POST /api/admin/tarabut/accounts - 200 (empty account_count is OK)
 6) RS256 inbound webhook: signed=201, tampered=401
 7) Regression: presets list, generic + jira simulate ok:true
"""
import os
import json
import base64
import secrets
import time

import pytest
import requests
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://pfp-trust-statement.preview.emergentagent.com"
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"

TARABUT_CLIENT_ID = "4d869fd0-f71e-4c9b-80f9-fe0e3ba0a3b0"
TARABUT_CLIENT_SECRET = "7bYxs8nGGlCUFloKK1UMP3a0y0kw7RU7H8uUrLreT5UhInjuAL5SlUdEZERv3Q0v"
TARABUT_REDIRECT_URI = "http://localhost:3000/callback"


# ----------------------------- fixtures -----------------------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tarabut_integration(h):
    """Create a fresh tarabut integration with random slug."""
    slug = f"tarabut-qa-{secrets.token_hex(4)}"
    payload = {
        "name": "TEST_TarabutQA",
        "slug": slug,
        "adapter": "tarabut",
        "auth_provider": "rsa_sha256",
        "auth_config": {"accept_unverified": "false"},
    }
    r = requests.post(f"{BASE_URL}/api/admin/integrations", headers=h, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create tarabut integration failed: {r.status_code} {r.text}"
    data = r.json()
    integration_id = data["integration_id"]
    yield {"id": integration_id, "slug": slug}
    # teardown
    try:
        requests.delete(f"{BASE_URL}/api/admin/integrations/{integration_id}", headers=h, timeout=15)
    except Exception:
        pass


# ----------------------------- tests -----------------------------
class TestOAuthConfig:
    def test_configure_oauth_and_verify_secret_redacted(self, h, tarabut_integration):
        r = requests.post(
            f"{BASE_URL}/api/admin/tarabut/oauth-config", headers=h,
            json={
                "integration_id": tarabut_integration["id"],
                "client_id": TARABUT_CLIENT_ID,
                "client_secret": TARABUT_CLIENT_SECRET,
                "redirect_uri": TARABUT_REDIRECT_URI,
                "region": "bahrain",
            }, timeout=30)
        assert r.status_code == 200, f"oauth-config: {r.status_code} {r.text}"
        d = r.json()
        assert d["oauth_client_id"] == TARABUT_CLIENT_ID
        assert d["redirect_uri"] == TARABUT_REDIRECT_URI
        assert d["region"] == "bahrain"
        assert d["client_secret_stored"] is True

        # Verify secret is redacted in public view
        g = requests.get(f"{BASE_URL}/api/admin/integrations/{tarabut_integration['id']}", headers=h, timeout=15)
        assert g.status_code == 200
        gd = g.json()
        assert gd.get("has_external_secret") is True
        raw = json.dumps(gd)
        assert TARABUT_CLIENT_SECRET not in raw, "client_secret leaked in GET response!"


class TestLiveConnectivity:
    def test_connectivity_token_acquired(self, h, tarabut_integration):
        # oauth-config must be applied first (done in prior test class if run in order)
        # Ensure config regardless of order:
        requests.post(
            f"{BASE_URL}/api/admin/tarabut/oauth-config", headers=h,
            json={"integration_id": tarabut_integration["id"], "client_id": TARABUT_CLIENT_ID,
                  "client_secret": TARABUT_CLIENT_SECRET, "redirect_uri": TARABUT_REDIRECT_URI,
                  "region": "bahrain"}, timeout=30)
        r = requests.post(f"{BASE_URL}/api/admin/tarabut/connectivity", headers=h, json={}, timeout=45)
        assert r.status_code == 200, f"connectivity failed: {r.status_code} {r.text}"
        d = r.json()
        assert d.get("ok") is True
        assert d.get("token_acquired") is True
        # token must not leak
        assert "token" not in d or not isinstance(d.get("token"), str) or len(d.get("token", "")) == 0


class TestLiveConnectIntent:
    def test_intent_and_public_proof(self, h, tarabut_integration):
        requests.post(
            f"{BASE_URL}/api/admin/tarabut/oauth-config", headers=h,
            json={"integration_id": tarabut_integration["id"], "client_id": TARABUT_CLIENT_ID,
                  "client_secret": TARABUT_CLIENT_SECRET, "redirect_uri": TARABUT_REDIRECT_URI,
                  "region": "bahrain"}, timeout=30)

        cust_id = "pfp-qa-1"
        body = {
            "user": {"customerUserId": cust_id, "email": "a@b.com", "firstName": "John", "lastName": "Snow"},
            "provider_id": "BLUE",
            "redirect_url": "http://localhost:3000/callback",
        }
        r = requests.post(f"{BASE_URL}/api/admin/tarabut/connect/intent", headers=h, json=body, timeout=45)
        assert r.status_code == 200, f"intent failed: {r.status_code} {r.text}"
        d = r.json()
        assert "tarabut" in d and "proof" in d
        assert d["tarabut"].get("intentId")
        assert d["tarabut"].get("connectUrl")
        fea_id = d["proof"]["fea_id"]
        assert fea_id
        assert d["proof"].get("event_type") == "intent_created"

        # Verify public proof
        time.sleep(1)
        pr = requests.get(f"{BASE_URL}/api/fea/public/{fea_id}", timeout=20)
        assert pr.status_code == 200, f"public verify failed: {pr.status_code} {pr.text}"
        pd = pr.json()
        assert pd.get("valid") is True
        ed = (pd.get("artifact") or {}).get("event_descriptor") or pd.get("event_descriptor") or {}
        assert ed.get("provider") == "Tarabut", f"provider mismatch: {ed}"
        assert "RSA" in (ed.get("auth_method") or "") and "RS256" in (ed.get("auth_method") or "")
        raw = json.dumps(pd)
        assert cust_id not in raw, "customerUserId leaked in public verify response"


class TestAccounts:
    def test_accounts_returns_200(self, h, tarabut_integration):
        requests.post(
            f"{BASE_URL}/api/admin/tarabut/oauth-config", headers=h,
            json={"integration_id": tarabut_integration["id"], "client_id": TARABUT_CLIENT_ID,
                  "client_secret": TARABUT_CLIENT_SECRET, "redirect_uri": TARABUT_REDIRECT_URI,
                  "region": "bahrain"}, timeout=30)
        r = requests.post(f"{BASE_URL}/api/admin/tarabut/accounts", headers=h,
                          json={"customer_user_id": "pfp-qa-1"}, timeout=45)
        assert r.status_code == 200, f"accounts failed: {r.status_code} {r.text}"
        d = r.json()
        assert "account_count" in d


class TestRS256Webhook:
    def test_signed_ok_and_tampered_rejected(self, h, tarabut_integration):
        # Generate RSA-2048 keypair
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        kid = "qa-key-1"

        # Configure webhook key
        r = requests.post(f"{BASE_URL}/api/admin/tarabut/webhook-key", headers=h, json={
            "integration_id": tarabut_integration["id"], "public_key": pem, "key_id": kid,
        }, timeout=20)
        assert r.status_code == 200, f"webhook-key failed: {r.status_code} {r.text}"

        # Enable integration
        e = requests.post(f"{BASE_URL}/api/admin/integrations/{tarabut_integration['id']}/enable",
                          headers=h, timeout=15)
        assert e.status_code in (200, 204), f"enable failed: {e.status_code} {e.text}"

        # Build a tarabut event body
        body_obj = {
            "tarabutEventType": "payment_completed",
            "externalId": f"pay-{secrets.token_hex(6)}",
            "eventSource": "WEBHOOK",
            "status": "COMPLETED",
            "amount": 12.50,
            "currency": "BHD",
            "attributes": {},
            "sensitive": {},
        }
        raw = json.dumps(body_obj, separators=(",", ":")).encode()
        sig = key.sign(raw, padding.PKCS1v15(), hashes.SHA256())
        sig_b64 = base64.b64encode(sig).decode()

        ingest_url = f"{BASE_URL}/api/ingest/{tarabut_integration['slug']}"

        # Signed - expect 201
        r_ok = requests.post(ingest_url, data=raw, headers={
            "Content-Type": "application/json",
            "x-signature": sig_b64,
            "x-signature-keyid": kid,
        }, timeout=30)
        assert r_ok.status_code == 201, f"signed post expected 201 got {r_ok.status_code}: {r_ok.text}"
        assert r_ok.json().get("fea_id")

        # Tampered - append a byte, same signature -> expect 401
        r_bad = requests.post(ingest_url, data=raw + b"X", headers={
            "Content-Type": "application/json",
            "x-signature": sig_b64,
            "x-signature-keyid": kid,
        }, timeout=30)
        assert r_bad.status_code == 401, f"tampered post expected 401 got {r_bad.status_code}: {r_bad.text}"


class TestRegression:
    def test_presets_include_all_providers(self, h):
        r = requests.get(f"{BASE_URL}/api/admin/integrations/presets", headers=h, timeout=15)
        assert r.status_code == 200
        presets = [p.get("id") or p.get("slug") or p.get("preset_id") or p.get("key") for p in r.json().get("presets", [])]
        # try multiple key names
        raw = json.dumps(r.json())
        for name in ["generic", "cashfree", "stripe", "razorpay", "github", "slack",
                     "docusign", "shopify", "jira", "tarabut"]:
            assert name in raw, f"preset '{name}' missing from presets list"

    def test_generic_hmac_simulate(self, h):
        slug = f"gen-qa-{secrets.token_hex(4)}"
        payload = {"name": "TEST_GenericQA", "slug": slug, "adapter": "generic",
                   "auth_provider": "hmac_sha256"}
        c = requests.post(f"{BASE_URL}/api/admin/integrations", headers=h, json=payload, timeout=20)
        assert c.status_code in (200, 201), c.text
        iid = c.json()["integration_id"]
        try:
            s = requests.post(f"{BASE_URL}/api/admin/integrations/{iid}/simulate", headers=h, timeout=30)
            assert s.status_code == 200, s.text
            sd = s.json()
            assert sd.get("ok") is True, f"generic simulate not ok: {sd}"
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=h, timeout=15)

    def test_jira_simulate(self, h):
        slug = f"jira-qa-{secrets.token_hex(4)}"
        payload = {"name": "TEST_JiraQA", "slug": slug, "adapter": "jira",
                   "auth_provider": "hmac_sha256"}
        c = requests.post(f"{BASE_URL}/api/admin/integrations", headers=h, json=payload, timeout=20)
        assert c.status_code in (200, 201), c.text
        iid = c.json()["integration_id"]
        try:
            s = requests.post(f"{BASE_URL}/api/admin/integrations/{iid}/simulate", headers=h, timeout=30)
            assert s.status_code == 200, s.text
            sd = s.json()
            assert sd.get("ok") is True, f"jira simulate not ok: {sd}"
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=h, timeout=15)
