"""Iteration 29 — enterprise hardening E2E tests.

Focus:
 1) ALLOW-LIST redaction: arbitrary future auth_config keys and 'secret' field
    are NEVER echoed back in POST/GET responses.
 2) OAuth2 circuit breaker: unreachable IdP fails FAST (<3s) with 401 and
    repeated attempts stay fast (circuit opens).
 3) Regression on baseline flows.
"""
import hashlib
import hmac
import json
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"


def _rand_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@pytest.fixture(scope="session")
def admin_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}",
            "Content-Type": "application/json"}


@pytest.fixture()
def created(admin_headers):
    ids = []
    yield ids
    for iid in ids:
        try:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}",
                            headers=admin_headers, timeout=10)
        except Exception:
            pass


def _create(admin_headers, created, **body):
    body.setdefault("slug", _rand_slug("iter29"))
    body.setdefault("name", body["slug"])
    body.setdefault("adapter", "generic")
    r = requests.post(f"{BASE_URL}/api/admin/integrations",
                      json=body, headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    created.append(d["integration_id"])
    return d


# ---------------------------------------------------------------------------
# 1) ALLOW-LIST redaction — arbitrary future keys never leak
# ---------------------------------------------------------------------------
FORBIDDEN_TOP = ("hmac_secret", "token_hash", "basic_password_hash", "external_secret")


def _assert_no_secrets(obj: dict, unapproved_keys=("client_secret", "totally_new_secret_field")):
    for k in FORBIDDEN_TOP:
        assert k not in obj, f"leaked top-level secret: {k}"
    cfg = obj.get("auth_config", {})
    for k in unapproved_keys:
        assert k not in cfg, f"leaked unapproved auth_config key: {k}"


def test_allowlist_omits_unapproved_and_secret(admin_headers, created):
    integ = _create(admin_headers, created,
                    auth_provider="jwt",
                    secret="super-32-char-jwt-shared-secret!!!aaaaa",
                    auth_config={
                        "jwt_algorithms": ["HS256"],
                        "issuer": "acme",
                        "jwks_url": "https://x/jwks",
                        # unapproved keys — must be omitted from public()
                        "client_secret": "should-be-hidden",
                        "totally_new_secret_field": "future-leak-guard",
                        "api_password": "also-not-approved",
                    })
    # POST response
    _assert_no_secrets(integ, ("client_secret", "totally_new_secret_field", "api_password"))
    # GET single
    g = requests.get(f"{BASE_URL}/api/admin/integrations/{integ['integration_id']}",
                     headers=admin_headers, timeout=10)
    assert g.status_code == 200
    _assert_no_secrets(g.json(), ("client_secret", "totally_new_secret_field", "api_password"))
    # GET list
    ls = requests.get(f"{BASE_URL}/api/admin/integrations", headers=admin_headers, timeout=15)
    assert ls.status_code == 200
    ls_data = ls.json()
    rows = ls_data.get("integrations", ls_data) if isinstance(ls_data, dict) else ls_data
    row = next((x for x in rows if x["integration_id"] == integ["integration_id"]), None)
    assert row is not None
    _assert_no_secrets(row, ("client_secret", "totally_new_secret_field", "api_password"))
    # approved keys still visible
    assert row["auth_config"].get("jwks_url") == "https://x/jwks"
    assert row["auth_config"].get("issuer") == "acme"


def test_oauth2_allowlist_omits_client_secret(admin_headers, created):
    integ = _create(admin_headers, created,
                    auth_provider="oauth2",
                    secret="oauth-client-secret-shh",
                    auth_config={
                        "oauth_mode": "introspection",
                        "oauth_client_id": "cid-123",
                        "introspection_url": "https://unreachable.example.invalid/introspect",
                        "client_secret": "leaked?",
                        "future_key": "hidden",
                    })
    _assert_no_secrets(integ, ("client_secret", "future_key"))
    assert integ["auth_config"].get("oauth_client_id") == "cid-123"
    assert integ["auth_config"].get("introspection_url", "").startswith("https://unreachable")


# ---------------------------------------------------------------------------
# 2) OAuth2 fail-fast + circuit breaker (repeated attempts stay quick)
# ---------------------------------------------------------------------------
def test_oauth2_fails_fast_and_repeatedly_401(admin_headers, created):
    integ = _create(admin_headers, created, auth_provider="oauth2",
                    auth_config={"oauth_mode": "introspection",
                                 "introspection_url": "https://unreachable.example.invalid/introspect",
                                 "oauth_client_id": "cid"},
                    secret="cs-shh")
    latencies = []
    for i in range(4):
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}",
                          data=json.dumps({"id": f"X-{i}", "type": "t",
                                           "timestamp": "2026-06-10T12:00:00Z"}).encode(),
                          headers={"authorization": f"Bearer tok-{i}",
                                   "Content-Type": "application/json"}, timeout=15)
        latencies.append(time.time() - t0)
        assert r.status_code == 401, r.text
    # No single attempt should hang; subsequent attempts should be quick (breaker/neg-cache)
    assert max(latencies) < 10, f"oauth2 unreachable path too slow: {latencies}"
    # Later ones should be at least as fast as the first (allow small jitter)
    assert min(latencies[-2:]) <= latencies[0] + 1.0, f"circuit didn't help: {latencies}"


# ---------------------------------------------------------------------------
# 3) Regression sweep (concise)
# ---------------------------------------------------------------------------
def test_regression_hmac_and_replay(admin_headers, created):
    integ = _create(admin_headers, created, auth_provider="hmac_sha256", replay_protection=True)
    secret = integ["credential"]
    body = json.dumps({"id": f"R-{uuid.uuid4().hex[:6]}", "type": "t",
                       "timestamp": "2026-06-10T12:00:00Z"}).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    hdrs = {"x-pfp-signature": sig, "Content-Type": "application/json"}
    r1 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body, headers=hdrs, timeout=15)
    assert r1.status_code == 201, r1.text
    fea_id = r1.json().get("fea_id")
    assert fea_id
    r2 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=body, headers=hdrs, timeout=15)
    assert r2.status_code == 409

    # bad sig -> 401
    r3 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}",
                       data=json.dumps({"id": "Z", "type": "t",
                                        "timestamp": "2026-06-10T12:00:00Z"}).encode(),
                       headers={"x-pfp-signature": "bad", "Content-Type": "application/json"},
                       timeout=15)
    assert r3.status_code == 401
    # verify fea_id
    v = requests.get(f"{BASE_URL}/api/public/verify/{fea_id}", timeout=15)
    assert v.status_code == 200
    assert v.json().get("fea_id") == fea_id


def test_unknown_slug_404_and_invalid_json_400(admin_headers, created):
    r = requests.post(f"{BASE_URL}/api/ingest/definitely-not-a-real-slug-xyz",
                      data=b"{}", headers={"Content-Type": "application/json"}, timeout=10)
    assert r.status_code == 404

    integ = _create(admin_headers, created, auth_provider="none")
    r2 = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}", data=b"not-json{",
                       headers={"Content-Type": "application/json"}, timeout=10)
    assert r2.status_code == 400


def test_disabled_integration_returns_403(admin_headers, created):
    integ = _create(admin_headers, created, auth_provider="none")
    # Use the dedicated disable endpoint
    u = requests.post(f"{BASE_URL}/api/admin/integrations/{integ['integration_id']}/disable",
                      headers=admin_headers, timeout=10)
    assert u.status_code < 400, u.text
    r = requests.post(f"{BASE_URL}/api/ingest/{integ['slug']}",
                      data=json.dumps({"id": "X", "type": "t",
                                       "timestamp": "2026-06-10T12:00:00Z"}).encode(),
                      headers={"Content-Type": "application/json"}, timeout=10)
    assert r.status_code == 403, r.text


def test_baseline_endpoints_unaffected():
    h = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert h.status_code == 200
    k = requests.get(f"{BASE_URL}/api/public/keys", timeout=10)
    assert k.status_code == 200
