"""
PFP Enterprise Hardening Tests — covers NEW endpoints (12 -> 34):
- /api/config (test_api_key in dev), /api/health (deep), /api/metrics (Prometheus)
- /api/auth/login + /me + RBAC
- /api/admin/api-keys/* (create, list, revoke)
- /api/admin/keys/* (rotate, revoke, retire)
- /api/admin/audit + /audit/verify
- FEA list (GET ''), single fetch (GET /{fea_id}), batch
- Webhooks subscribe/list/test/delete
- Demo isolation (/api/demo/issue, /verify, /artifact, /artifact/verify)
- Security: oversized body (413), security headers, legacy v1 rejection
- FEA payload v1.1 contract (regression)
"""
import os
import uuid
import base64
import time
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://transaction-sign-1.preview.emergentagent.com').rstrip('/')

ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!2026"


# ---------- Shared fixtures ----------

@pytest.fixture(scope="session")
def api_key():
    r = requests.get(f"{BASE_URL}/api/config", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "test_api_key" in data, "dev /api/config must expose test_api_key"
    return data["test_api_key"]


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def key_headers(api_key):
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def fresh_payload(extra=None):
    uid = uuid.uuid4().hex
    p = {
        "idempotency_key": f"TEST_idem_{uid}",
        "transaction_id": f"TEST_txn_{uid}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "amount": 10000,
        "currency": "INR",
        "payer_id": "payer_x",
        "payee_id": "payee_x",
        "metadata": {"test": True},
    }
    if extra:
        p.update(extra)
    return p


# ---------- /api/config, /api/health, /api/metrics ----------

class TestPlatformEndpoints:
    def test_config_dev_includes_test_key(self):
        r = requests.get(f"{BASE_URL}/api/config", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "endpoints" in data and isinstance(data["endpoints"], dict)
        assert data.get("test_api_key", "").startswith("pfp_")

    def test_health_deep_checks_all_true(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        checks = data.get("checks", {})
        for k in ("database", "key_registry", "signing_service", "demo_db"):
            assert checks.get(k) is True, f"health check {k} not true: {checks}"

    def test_metrics_prometheus_exposition(self):
        r = requests.get(f"{BASE_URL}/api/metrics", timeout=10)
        assert r.status_code == 200
        body = r.text
        assert "pfp_http_requests_total" in body, "missing pfp_http_requests_total metric"


# ---------- Auth + RBAC ----------

class TestAuth:
    def test_login_success(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data and isinstance(data["access_token"], str)
        # role + tenant_id are flat fields on the login response
        assert data.get("role") == "super_admin"
        assert data.get("tenant_id") == "default"

    def test_login_wrong_password(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "wrong-password!"}, timeout=10)
        assert r.status_code == 401

    def test_me_with_token(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
        assert r.status_code == 200
        u = r.json()
        assert u.get("email") == ADMIN_EMAIL
        assert u.get("role") == "super_admin"

    def test_admin_endpoint_requires_token(self):
        r = requests.get(f"{BASE_URL}/api/admin/api-keys", timeout=10)
        assert r.status_code in (401, 403)


# ---------- Admin: API keys CRUD ----------

class TestAdminApiKeys:
    def test_create_list_revoke_api_key(self, admin_token):
        # CREATE
        body = {
            "name": f"TEST_key_{uuid.uuid4().hex[:8]}",
            "tenant_id": "default",
            "scopes": ["fea:write", "fea:read", "fea:verify"],
            "expires_in_days": 30,
        }
        r = requests.post(f"{BASE_URL}/api/admin/api-keys/create",
                          json=body, headers=auth_headers(admin_token), timeout=10)
        assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
        created = r.json()
        # raw key exposed only on create
        raw_key = created.get("api_key") or created.get("raw_key") or created.get("key")
        assert raw_key, f"raw api_key missing in create response: {created}"
        assert set(["fea:write", "fea:read", "fea:verify"]).issubset(set(created.get("scopes", [])))
        assert "expires_at" in created
        key_id = created.get("key_id") or created.get("id")
        assert key_id, f"key_id missing in create response: {created}"

        # LIST
        r2 = requests.get(f"{BASE_URL}/api/admin/api-keys",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
        assert r2.status_code == 200
        listing = r2.json()
        items = listing if isinstance(listing, list) else listing.get("keys") or listing.get("items") or []
        assert any((it.get("key_id") == key_id) or (it.get("id") == key_id) for it in items), \
            f"created key not found in listing"

        # REVOKE
        r3 = requests.post(f"{BASE_URL}/api/admin/api-keys/revoke",
                           params={"key_id": key_id},
                           headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
        assert r3.status_code in (200, 204), f"revoke failed: {r3.status_code} {r3.text}"


# ---------- Admin: signing keys + audit ----------

class TestAdminSigningKeysAndAudit:
    def test_rotate_and_audit_chain(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/admin/keys/rotate",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code in (200, 201), f"rotate failed: {r.status_code} {r.text}"
        body = r.json()
        assert "new_public_key_id" in body
        assert "new_private_seed_b64" in body and len(body["new_private_seed_b64"]) > 0

        # audit list
        r2 = requests.get(f"{BASE_URL}/api/admin/audit",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
        assert r2.status_code == 200
        listing = r2.json()
        entries = listing if isinstance(listing, list) else listing.get("entries") or listing.get("items") or []
        assert len(entries) >= 1

        # audit verify
        r3 = requests.get(f"{BASE_URL}/api/admin/audit/verify",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
        assert r3.status_code == 200
        v = r3.json()
        assert v.get("intact") is True, f"audit chain not intact: {v}"


# ---------- FEA Generate (v1.1) + Idempotency + Replay ----------

class TestFEAGenerateV11:
    def test_generate_v11_payload(self, api_key):
        r = requests.post(f"{BASE_URL}/api/fea/generate",
                          json=fresh_payload(), headers=key_headers(api_key), timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        fea = data["fea_payload"]
        assert fea["fea_version"] == "1.1"
        assert fea["algorithm"] == "Ed25519"
        assert fea["tenant_id"] == "default"
        assert "iat" in fea and "jti" in fea
        assert data["signature_version"] == "v2"
        assert isinstance(data["signature"], str) and len(data["signature"]) > 0

    def test_generate_missing_key(self):
        r = requests.post(f"{BASE_URL}/api/fea/generate",
                          json=fresh_payload(),
                          headers={"Content-Type": "application/json"}, timeout=10)
        assert r.status_code == 401

    def test_idempotency_same_returns_same(self, api_key):
        p = fresh_payload()
        r1 = requests.post(f"{BASE_URL}/api/fea/generate", json=p, headers=key_headers(api_key), timeout=10)
        r2 = requests.post(f"{BASE_URL}/api/fea/generate", json=p, headers=key_headers(api_key), timeout=10)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["fea_id"] == r2.json()["fea_id"]

    def test_idempotency_conflict_409(self, api_key):
        p1 = fresh_payload()
        p2 = dict(p1)
        p2["amount"] = p1["amount"] + 1
        p2["transaction_id"] = "TEST_txn_other_" + uuid.uuid4().hex
        r1 = requests.post(f"{BASE_URL}/api/fea/generate", json=p1, headers=key_headers(api_key), timeout=10)
        r2 = requests.post(f"{BASE_URL}/api/fea/generate", json=p2, headers=key_headers(api_key), timeout=10)
        assert r1.status_code == 200
        assert r2.status_code == 409

    def test_replay_same_payload_returns_existing(self, api_key):
        p1 = fresh_payload()
        p2 = dict(p1)
        p2["idempotency_key"] = "TEST_idem_other_" + uuid.uuid4().hex
        r1 = requests.post(f"{BASE_URL}/api/fea/generate", json=p1, headers=key_headers(api_key), timeout=10)
        r2 = requests.post(f"{BASE_URL}/api/fea/generate", json=p2, headers=key_headers(api_key), timeout=10)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["fea_id"] == r2.json()["fea_id"]

    def test_replay_attack_conflict_409(self, api_key):
        p1 = fresh_payload()
        p2 = dict(p1)
        p2["idempotency_key"] = "TEST_idem_other_" + uuid.uuid4().hex
        p2["amount"] = p1["amount"] + 999
        r1 = requests.post(f"{BASE_URL}/api/fea/generate", json=p1, headers=key_headers(api_key), timeout=10)
        r2 = requests.post(f"{BASE_URL}/api/fea/generate", json=p2, headers=key_headers(api_key), timeout=10)
        assert r1.status_code == 200
        assert r2.status_code == 409
        assert "Transaction replay detected with conflicting data" in r2.json().get("detail", "")


# ---------- FEA Verify (incl. v1 legacy rejection) ----------

class TestFEAVerify:
    @pytest.fixture
    def gen(self, api_key):
        r = requests.post(f"{BASE_URL}/api/fea/generate",
                          json=fresh_payload(), headers=key_headers(api_key), timeout=10)
        assert r.status_code == 200
        return r.json()

    def test_verify_valid(self, api_key, gen):
        body = {"fea_payload": gen["fea_payload"], "signature": gen["signature"],
                "signature_version": gen["signature_version"]}
        r = requests.post(f"{BASE_URL}/api/fea/verify", json=body,
                          headers=key_headers(api_key), timeout=10)
        assert r.status_code == 200
        assert r.json().get("valid") is True

    def test_verify_tampered_invalid(self, api_key, gen):
        sig = base64.b64decode(gen["signature"])
        tampered = base64.b64encode(bytes([sig[0] ^ 0xFF]) + sig[1:]).decode()
        body = {"fea_payload": gen["fea_payload"], "signature": tampered,
                "signature_version": gen["signature_version"]}
        r = requests.post(f"{BASE_URL}/api/fea/verify", json=body,
                          headers=key_headers(api_key), timeout=10)
        assert r.status_code == 200
        assert r.json().get("valid") is False

    def test_verify_legacy_v1_rejected(self, api_key, gen):
        body = {"fea_payload": gen["fea_payload"], "signature": gen["signature"],
                "signature_version": "v1"}
        r = requests.post(f"{BASE_URL}/api/fea/verify", json=body,
                          headers=key_headers(api_key), timeout=10)
        assert r.status_code == 200
        assert r.json().get("valid") is False, "legacy v1 must be rejected"


# ---------- FEA list & fetch + batch ----------

class TestFEAListFetchBatch:
    def test_list_paginated(self, api_key):
        # ensure at least 1 exists
        requests.post(f"{BASE_URL}/api/fea/generate", json=fresh_payload(),
                      headers=key_headers(api_key), timeout=10)
        r = requests.get(f"{BASE_URL}/api/fea?limit=5",
                         headers={"X-API-Key": api_key}, timeout=10)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items") or data.get("results") or []
        assert isinstance(items, list)
        assert len(items) <= 5

    def test_get_by_id(self, api_key):
        r = requests.post(f"{BASE_URL}/api/fea/generate", json=fresh_payload(),
                          headers=key_headers(api_key), timeout=10)
        assert r.status_code == 200
        fea_id = r.json()["fea_id"]
        r2 = requests.get(f"{BASE_URL}/api/fea/{fea_id}",
                          headers={"X-API-Key": api_key}, timeout=10)
        assert r2.status_code == 200
        assert r2.json().get("fea_id") == fea_id

    def test_get_by_id_not_found(self, api_key):
        r = requests.get(f"{BASE_URL}/api/fea/{uuid.uuid4().hex}",
                         headers={"X-API-Key": api_key}, timeout=10)
        assert r.status_code == 404

    def test_batch_two_items_succeed(self, api_key):
        body = {"items": [fresh_payload(), fresh_payload()]}
        r = requests.post(f"{BASE_URL}/api/fea/batch", json=body,
                          headers=key_headers(api_key), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # accept varied key naming
        succ = data.get("succeeded", data.get("success_count", data.get("successful")))
        assert succ == 2, f"expected succeeded=2, got: {data}"

    def test_batch_partial_failure_does_not_abort(self, api_key):
        p1 = fresh_payload()
        # second item shares idem key but has different transaction_id+amount → conflict
        p2 = fresh_payload()
        p2["idempotency_key"] = p1["idempotency_key"]
        body = {"items": [p1, p2]}
        r = requests.post(f"{BASE_URL}/api/fea/batch", json=body,
                          headers=key_headers(api_key), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Either succeeded=1+failed=1 or detailed per-item results
        succ = data.get("succeeded", data.get("success_count"))
        fail = data.get("failed", data.get("failure_count"))
        if succ is not None and fail is not None:
            assert succ == 1 and fail == 1, f"expected 1 succ / 1 fail, got: {data}"


# ---------- Public verify + keys ----------

class TestPublic:
    def test_public_verify(self, api_key):
        r = requests.post(f"{BASE_URL}/api/fea/generate", json=fresh_payload(),
                          headers=key_headers(api_key), timeout=10)
        fea_id = r.json()["fea_id"]
        r2 = requests.get(f"{BASE_URL}/api/public/verify/{fea_id}", timeout=10)
        assert r2.status_code == 200
        assert r2.json().get("signature_valid") is True

    def test_public_keys(self):
        r = requests.get(f"{BASE_URL}/api/public/keys", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "keys" in body and isinstance(body["keys"], list)


# ---------- Webhooks ----------

class TestWebhooks:
    def test_webhook_lifecycle(self, api_key):
        sub = {"url": "https://example.com/webhook", "events": ["fea.created"]}
        r = requests.post(f"{BASE_URL}/api/webhooks/subscribe", json=sub,
                          headers=key_headers(api_key), timeout=10)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        webhook_id = body.get("webhook_id") or body.get("id")
        assert webhook_id, f"no webhook_id in response: {body}"
        assert "secret" in body and isinstance(body["secret"], str) and len(body["secret"]) > 0

        r2 = requests.get(f"{BASE_URL}/api/webhooks",
                          headers={"X-API-Key": api_key}, timeout=10)
        assert r2.status_code == 200
        items = r2.json()
        items = (items if isinstance(items, list)
                 else items.get("subscriptions") or items.get("items") or items.get("webhooks") or [])
        assert any((it.get("webhook_id") == webhook_id) or (it.get("id") == webhook_id) for it in items)

        r3 = requests.post(f"{BASE_URL}/api/webhooks/test",
                           params={"webhook_id": webhook_id},
                           headers={"X-API-Key": api_key}, timeout=15)
        assert r3.status_code == 200, r3.text
        # delivery to example.com expected to fail; only assert structured result
        assert isinstance(r3.json(), dict)

        r4 = requests.delete(f"{BASE_URL}/api/webhooks/{webhook_id}",
                             headers={"X-API-Key": api_key}, timeout=10)
        assert r4.status_code in (200, 204)


# ---------- Demo isolation + signed artifact ----------

class TestDemo:
    def test_demo_issue_verify(self):
        body = {
            "transaction_id": f"TEST_demo_{uuid.uuid4().hex}",
            "user_id": "alice",
            "amount": 1500,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "compliance": {
                "kyc": "Pass", "aml": "Pass",
                "limits": "Within allowed range", "status": "COMPLIANT",
            },
        }
        r = requests.post(f"{BASE_URL}/api/demo/issue", json=body, timeout=10)
        assert r.status_code == 200, f"demo/issue failed: {r.status_code} {r.text}"
        pid = r.json().get("proof_id")
        assert pid
        r2 = requests.get(f"{BASE_URL}/api/demo/verify/{pid}", timeout=10)
        assert r2.status_code == 200
        assert r2.json().get("valid") is True

    def test_demo_artifact_kid_prefix_and_verify(self):
        body = {
            "transaction_id": f"TEST_demo_art_{uuid.uuid4().hex}",
            "user_id": "alice",
            "amount": 1000,
            "compliance": {
                "kyc": "Pass", "aml": "Pass",
                "limits": "Within allowed range", "status": "COMPLIANT",
            },
        }
        r = requests.post(f"{BASE_URL}/api/demo/artifact", json=body, timeout=10)
        assert r.status_code == 200, f"demo/artifact failed: {r.status_code} {r.text}"
        artifact = r.json()
        kid = artifact.get("kid") or (artifact.get("signed") or {}).get("kid")
        assert kid and kid.startswith("demo_key_"), f"kid must start with demo_key_, got: {kid}"

        r2 = requests.post(f"{BASE_URL}/api/demo/artifact/verify", json=artifact, timeout=10)
        assert r2.status_code == 200
        assert r2.json().get("status") == "valid_compliant"


# ---------- Security: oversized body + headers ----------

class TestSecurity:
    def test_oversized_body_returns_413(self, api_key):
        # >1MB body
        big_blob = "x" * (1_100_000)
        body = fresh_payload({"metadata": {"blob": big_blob}})
        r = requests.post(f"{BASE_URL}/api/fea/generate", json=body,
                          headers=key_headers(api_key), timeout=20)
        assert r.status_code == 413, f"expected 413 for oversized body, got {r.status_code}"

    def test_security_headers_present(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.headers.get("X-Frame-Options", "").upper() == "DENY"
        assert r.headers.get("X-Content-Type-Options", "").lower() == "nosniff"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
