"""E2E integration tests for the generalized inbound-auth framework.

Covers backward compat + all new providers (hmac_sha1, hmac stripe scheme,
basic, jwt HS256, oauth2 config, mtls, custom fail-closed), cross-cutting
replay + timestamp, secret redaction, and a real Proof Artifact verify.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid

import jwt as pyjwt
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"


def _rand_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture()
def created_integrations(admin_headers):
    ids = []
    yield ids
    for iid in ids:
        try:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}",
                            headers=admin_headers, timeout=10)
        except Exception:
            pass


def _create(admin_headers, created_integrations, **body):
    body.setdefault("slug", _rand_slug("test"))
    body.setdefault("name", body["slug"])
    body.setdefault("adapter", "generic")
    r = requests.post(f"{BASE_URL}/api/admin/integrations",
                      json=body, headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    created_integrations.append(data["integration_id"])
    return data


def _payload():
    return {
        "type": "invoice.created",
        "id": f"EXT-{uuid.uuid4().hex[:8]}",
        "timestamp": "2026-06-10T12:00:00Z",
        "actor": "system-a",
        "subject": "acct-1",
        "amount": 1000,
        "currency": "USD",
    }


# --- Health / backward compat ---
def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.status_code == 200


def test_hmac_alias_backward_compat(admin_headers, created_integrations):
    """auth_provider='hmac' still authenticates exactly as before (sha256)."""
    integ = _create(admin_headers, created_integrations, auth_provider="hmac")
    secret = integ["credential"]
    body = json.dumps(_payload()).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body,
                      headers={"x-pfp-signature": sig, "Content-Type": "application/json"}, timeout=15)
    assert r.status_code == 201, r.text
    assert r.json().get("fea_id")


# --- HMAC-SHA1 provider ---
def test_hmac_sha1_provider(admin_headers, created_integrations):
    integ = _create(admin_headers, created_integrations, auth_provider="hmac_sha1")
    secret = integ["credential"]
    body = json.dumps(_payload()).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    ok = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body,
                      headers={"x-pfp-signature": sig, "Content-Type": "application/json"}, timeout=15)
    assert ok.status_code == 201, ok.text
    bad = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=json.dumps(_payload()).encode(),
                       headers={"x-pfp-signature": "deadbeef", "Content-Type": "application/json"}, timeout=15)
    assert bad.status_code == 401


# --- HMAC Stripe scheme + stale timestamp ---
def test_hmac_stripe_scheme_fresh_and_stale(admin_headers, created_integrations):
    integ = _create(admin_headers, created_integrations, auth_provider="hmac_sha256",
                    auth_config={"signature_scheme": "stripe"},
                    require_timestamp=True, timestamp_tolerance_seconds=300)
    secret = integ["credential"]
    body = json.dumps(_payload()).encode()
    ts = str(int(time.time()))
    v1 = hmac.new(secret.encode(), f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body,
                     headers={"stripe-signature": f"t={ts},v1={v1}",
                              "Content-Type": "application/json"}, timeout=15)
    assert r.status_code == 201, r.text

    stale_ts = str(int(time.time()) - 3600)
    body2 = json.dumps(_payload()).encode()
    v1_stale = hmac.new(secret.encode(), f"{stale_ts}.{body2.decode()}".encode(), hashlib.sha256).hexdigest()
    stale = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body2,
                         headers={"stripe-signature": f"t={stale_ts},v1={v1_stale}",
                                  "Content-Type": "application/json"}, timeout=15)
    assert stale.status_code == 401, stale.text


# --- Basic ---
def test_basic_provider(admin_headers, created_integrations):
    integ = _create(admin_headers, created_integrations, auth_provider="basic",
                    auth_config={"basic_username": "acme"})
    password = integ["credential"]
    body = json.dumps(_payload()).encode()
    tok = base64.b64encode(f"acme:{password}".encode()).decode()
    r = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body,
                     headers={"authorization": f"Basic {tok}", "Content-Type": "application/json"}, timeout=15)
    assert r.status_code == 201, r.text

    bad = base64.b64encode(b"acme:wrong").decode()
    r2 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=json.dumps(_payload()).encode(),
                      headers={"authorization": f"Basic {bad}", "Content-Type": "application/json"}, timeout=15)
    assert r2.status_code == 401


# --- JWT HS256 ---
def test_jwt_hs256_provider(admin_headers, created_integrations):
    shared = "jwt-shared-secret-min-32-bytes-long!!aaaa"
    integ = _create(admin_headers, created_integrations, auth_provider="jwt",
                    secret=shared,
                    auth_config={"jwt_algorithms": ["HS256"], "issuer": "acme", "audience": "pfp"})
    # jwt provider must not mint a credential
    assert integ.get("credential") is None
    body = json.dumps(_payload()).encode()

    good = pyjwt.encode({"sub": "svc-1", "iss": "acme", "aud": "pfp",
                        "exp": int(time.time()) + 300}, shared, algorithm="HS256")
    r = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body,
                     headers={"authorization": f"Bearer {good}", "Content-Type": "application/json"}, timeout=15)
    assert r.status_code == 201, r.text

    expired = pyjwt.encode({"sub": "x", "iss": "acme", "aud": "pfp",
                           "exp": int(time.time()) - 3600}, shared, algorithm="HS256")
    r2 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=json.dumps(_payload()).encode(),
                      headers={"authorization": f"Bearer {expired}"}, timeout=15)
    assert r2.status_code == 401

    wrong = pyjwt.encode({"sub": "x", "iss": "acme", "aud": "pfp",
                         "exp": int(time.time()) + 300}, "other-secret-that-is-32-bytes-long!", algorithm="HS256")
    r3 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=json.dumps(_payload()).encode(),
                      headers={"authorization": f"Bearer {wrong}"}, timeout=15)
    assert r3.status_code == 401

    unsigned = pyjwt.encode({"sub": "x", "iss": "acme", "aud": "pfp",
                            "exp": int(time.time()) + 300}, key=None, algorithm="none")
    r4 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=json.dumps(_payload()).encode(),
                      headers={"authorization": f"Bearer {unsigned}"}, timeout=15)
    assert r4.status_code == 401


# --- OAuth2 graceful failure ---
def test_oauth2_config_accepted_fails_closed(admin_headers, created_integrations):
    integ = _create(admin_headers, created_integrations, auth_provider="oauth2",
                    auth_config={"oauth_mode": "introspection",
                                 "introspection_url": "https://unreachable.example.invalid/introspect",
                                 "oauth_client_id": "cid"},
                    secret="cs-shh")
    assert integ.get("credential") is None
    r = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=json.dumps(_payload()).encode(),
                     headers={"authorization": "Bearer sometoken",
                              "Content-Type": "application/json"}, timeout=20)
    # must fail closed and NOT be a 500
    assert r.status_code == 401, r.text


# --- mTLS ---
def test_mtls_provider(admin_headers, created_integrations):
    integ = _create(admin_headers, created_integrations, auth_provider="mtls",
                    auth_config={"allowed_fingerprints": ["AA:BB:CC"]})
    assert integ.get("credential") is None
    body = json.dumps(_payload()).encode()
    ok = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body,
                     headers={"x-client-verify": "SUCCESS",
                              "x-client-cert-fingerprint": "AA:BB:CC",
                              "Content-Type": "application/json"}, timeout=15)
    assert ok.status_code == 201, ok.text
    miss = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=json.dumps(_payload()).encode(),
                        headers={"Content-Type": "application/json"}, timeout=15)
    assert miss.status_code == 401
    wrong = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=json.dumps(_payload()).encode(),
                         headers={"x-client-verify": "SUCCESS", "x-client-cert-fingerprint": "ZZ"}, timeout=15)
    assert wrong.status_code in (401, 403)


# --- Custom fail-closed ---
def test_custom_provider_fail_closed(admin_headers, created_integrations):
    integ = _create(admin_headers, created_integrations, auth_provider="custom",
                    auth_config={"custom_handler": "not-registered"})
    r = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=json.dumps(_payload()).encode(),
                     headers={"Content-Type": "application/json"}, timeout=15)
    assert r.status_code == 401


# --- Replay protection ---
def test_replay_protection_hmac(admin_headers, created_integrations):
    integ = _create(admin_headers, created_integrations, auth_provider="hmac_sha256",
                    replay_protection=True)
    secret = integ["credential"]
    body = json.dumps(_payload()).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    hdrs = {"x-pfp-signature": sig, "Content-Type": "application/json"}
    r1 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body, headers=hdrs, timeout=15)
    assert r1.status_code == 201, r1.text
    r2 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body, headers=hdrs, timeout=15)
    assert r2.status_code == 409, r2.text


# --- Secret redaction / no leaks for external providers ---
def test_external_provider_never_leaks_secrets(admin_headers, created_integrations):
    integ = _create(admin_headers, created_integrations, auth_provider="jwt",
                    secret="super-secret-shared-key-not-returned!",
                    auth_config={"jwt_algorithms": ["HS256"], "issuer": "acme", "audience": "pfp",
                                 "client_secret": "should-be-redacted",
                                 "jwks_url": "https://x/jwks"})
    assert integ.get("credential") is None
    for forbidden in ("external_secret", "hmac_secret", "token_hash", "basic_password_hash"):
        assert forbidden not in integ, f"leaked {forbidden} in create response"
    # GET should also not leak
    g = requests.get(f"{BASE_URL}/api/admin/integrations/{integ['integration_id']}",
                    headers=admin_headers, timeout=10)
    assert g.status_code == 200
    got = g.json()
    for forbidden in ("external_secret", "hmac_secret", "token_hash", "basic_password_hash"):
        assert forbidden not in got
    # ALLOW-LIST: client_secret (and any non-approved key) is fully OMITTED
    assert "client_secret" not in got["auth_config"]
    assert got["auth_config"].get("jwks_url") == "https://x/jwks"


# --- End-to-end proof verify ---
def test_ingested_event_produces_verifiable_proof(admin_headers, created_integrations):
    integ = _create(admin_headers, created_integrations, auth_provider="hmac_sha256")
    secret = integ["credential"]
    body = json.dumps(_payload()).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body,
                     headers={"x-pfp-signature": sig, "Content-Type": "application/json"}, timeout=20)
    assert r.status_code == 201, r.text
    fea_id = r.json()["fea_id"]
    v = requests.get(f"{BASE_URL}/api/public/verify/{fea_id}", timeout=15)
    assert v.status_code == 200, v.text
    vj = v.json()
    assert vj.get("fea_id") == fea_id and vj.get("fea_payload"), vj
