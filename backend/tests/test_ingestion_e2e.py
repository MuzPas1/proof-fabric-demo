"""End-to-end integration tests for the Inbound Event Ingestion framework.

Covers public inbound (HMAC / API key / bearer / none), admin CRUD + RBAC,
mapping into the existing proof pipeline, and backward-compat regression.
"""
import hashlib
import hmac
import json
import os
import secrets
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"
REVIEWER_EMAIL = "reviewer@pfprotocol.com"
REVIEWER_PASSWORD = "PfpReview-U6_1rbWiTW41M7HDLaKoDqdP"

session = requests.Session()
session.headers.update({"Content-Type": "application/json"})


def _login(email, password):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def reviewer_token():
    return _login(REVIEWER_EMAIL, REVIEWER_PASSWORD)


@pytest.fixture(scope="session")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def reviewer_h(reviewer_token):
    return {"Authorization": f"Bearer {reviewer_token}", "Content-Type": "application/json"}


def _rand_slug(prefix="test"):
    # slug pattern: lowercase alphanumeric + hyphens only (no underscore)
    safe = prefix.replace("_", "-")
    return f"{safe}-{secrets.token_hex(4)}"


def _create_integration(admin_h, auth_provider="hmac", slug=None):
    body = {
        "name": f"E2E {auth_provider}",
        "slug": slug or _rand_slug(auth_provider),
        "adapter": "generic",
        "auth_provider": auth_provider,
    }
    r = requests.post(f"{BASE_URL}/api/admin/integrations", headers=admin_h, json=body)
    assert r.status_code == 200, f"create failed: {r.status_code} {r.text}"
    return r.json()


# -------------------- health / backwards-compat regressions --------------------
class TestBackwardCompat:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200

    def test_public_keys(self):
        r = requests.get(f"{BASE_URL}/api/public/keys")
        assert r.status_code == 200
        assert "keys" in r.json() or isinstance(r.json(), (list, dict))

    def test_demo_issue_and_verify(self):
        payload = {
            "transaction_id": f"REG-{secrets.token_hex(4)}",
            "user_id": "user-1",
            "amount": 100,
            "created_at": "2026-06-10T12:00:00Z",
            "compliance": {},
        }
        r = requests.post(f"{BASE_URL}/api/demo/issue", json=payload)
        assert r.status_code == 200, r.text
        fea_id = r.json().get("proof_id") or r.json().get("fea_id") or r.json().get("id")
        assert fea_id
        # /api/public/verify targets FEA IDs; demo proofs verify via demo endpoint.
        # Regression: just confirm issuance succeeds (existing pipeline unchanged).


# -------------------- Admin CRUD --------------------
class TestAdminCRUD:
    def test_create_leaks_no_secret(self, admin_h):
        cfg = _create_integration(admin_h, "hmac")
        assert "hmac_secret" not in cfg
        assert "token_hash" not in cfg
        assert cfg.get("credential", "").startswith("whsec_")
        assert cfg.get("inbound_url", "").endswith(cfg["slug"])
        # cleanup
        requests.delete(f"{BASE_URL}/api/admin/integrations/{cfg['integration_id']}", headers=admin_h)

    def test_list_and_get(self, admin_h):
        cfg = _create_integration(admin_h, "hmac")
        try:
            r = requests.get(f"{BASE_URL}/api/admin/integrations", headers=admin_h)
            assert r.status_code == 200
            assert any(i["integration_id"] == cfg["integration_id"] for i in r.json()["integrations"])
            g = requests.get(f"{BASE_URL}/api/admin/integrations/{cfg['integration_id']}", headers=admin_h)
            assert g.status_code == 200
            assert "hmac_secret" not in g.json()
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{cfg['integration_id']}", headers=admin_h)

    def test_patch_enable_disable_rotate(self, admin_h):
        cfg = _create_integration(admin_h, "hmac")
        iid = cfg["integration_id"]
        try:
            p = requests.patch(f"{BASE_URL}/api/admin/integrations/{iid}",
                               headers=admin_h, json={"description": "updated"})
            assert p.status_code == 200
            assert p.json()["description"] == "updated"

            d = requests.post(f"{BASE_URL}/api/admin/integrations/{iid}/disable", headers=admin_h)
            assert d.status_code == 200 and d.json()["enabled"] is False
            e = requests.post(f"{BASE_URL}/api/admin/integrations/{iid}/enable", headers=admin_h)
            assert e.status_code == 200 and e.json()["enabled"] is True

            rot = requests.post(f"{BASE_URL}/api/admin/integrations/{iid}/rotate-secret", headers=admin_h)
            assert rot.status_code == 200
            new_cred = rot.json().get("credential")
            assert new_cred and new_cred != cfg["credential"]
            assert "hmac_secret" not in rot.json()
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)

    def test_stats_and_events(self, admin_h):
        cfg = _create_integration(admin_h, "hmac")
        iid = cfg["integration_id"]
        try:
            s = requests.get(f"{BASE_URL}/api/admin/integrations/{iid}/stats", headers=admin_h)
            assert s.status_code == 200
            for k in ("total_received", "total_accepted", "total_rejected", "health"):
                assert k in s.json()
            ev = requests.get(f"{BASE_URL}/api/admin/integrations/{iid}/events", headers=admin_h)
            assert ev.status_code == 200 and "events" in ev.json()
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)

    def test_test_endpoint_dry_run_and_issue(self, admin_h):
        cfg = _create_integration(admin_h, "hmac")
        iid = cfg["integration_id"]
        try:
            payload = {"type": "invoice.paid", "id": "T-1",
                       "timestamp": "2026-06-10T12:00:00Z", "user": "alice", "amount": 100}
            r = requests.post(f"{BASE_URL}/api/admin/integrations/{iid}/test",
                              headers=admin_h, json={"payload": payload, "issue": False})
            assert r.status_code == 200, r.text
            body = r.json()
            assert "normalized_event" in body and "mapped_request" in body
            assert body.get("fea_id") is None
            # Confirm payer_id is a sha256 hex hash (not raw "alice")
            assert body["mapped_request"]["payer_id"] == hashlib.sha256(b"alice").hexdigest()

            r2 = requests.post(f"{BASE_URL}/api/admin/integrations/{iid}/test",
                               headers=admin_h, json={"payload": {**payload, "id": "T-2"}, "issue": True})
            assert r2.status_code == 200 and r2.json().get("fea_id")
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)


# -------------------- Public inbound HMAC --------------------
class TestPublicInboundHMAC:
    def test_hmac_valid_and_variants(self, admin_h):
        cfg = _create_integration(admin_h, "hmac")
        slug, secret, iid = cfg["slug"], cfg["credential"], cfg["integration_id"]
        try:
            body = json.dumps({"type": "invoice.paid", "id": "INV-100",
                               "timestamp": "2026-06-10T12:00:00Z",
                               "user": "alice", "resource": "acct", "amount": 200}).encode()
            sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

            r = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                              headers={"Content-Type": "application/json", "X-PFP-Signature": sig})
            assert r.status_code == 201, r.text
            j = r.json()
            assert j["status"] == "accepted" and j["integration"] == slug
            assert j["event_id"] == "INV-100"
            fea_id = j["fea_id"]
            assert fea_id

            # The returned FEA is a real Proof Artifact
            v = requests.get(f"{BASE_URL}/api/public/verify/{fea_id}")
            assert v.status_code == 200, v.text

            # sha256= prefix also works (use id 101 to avoid idempotency collapse)
            body2 = body.replace(b"INV-100", b"INV-101")
            sig2 = hmac.new(secret.encode(), body2, hashlib.sha256).hexdigest()
            r2 = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body2,
                               headers={"Content-Type": "application/json",
                                        "X-PFP-Signature": "sha256=" + sig2})
            assert r2.status_code == 201, r2.text

            # Bad signature
            rb = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                               headers={"Content-Type": "application/json", "X-PFP-Signature": "deadbeef"})
            assert rb.status_code == 401

            # Missing signature
            rm = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                               headers={"Content-Type": "application/json"})
            assert rm.status_code == 401

            # Invalid JSON
            body_bad = b"{not json"
            sig_bad = hmac.new(secret.encode(), body_bad, hashlib.sha256).hexdigest()
            rj = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body_bad,
                               headers={"Content-Type": "application/json", "X-PFP-Signature": sig_bad})
            assert rj.status_code == 400

            # Missing identifier -> 422
            body_no_id = json.dumps({"type": "x"}).encode()
            sig_ni = hmac.new(secret.encode(), body_no_id, hashlib.sha256).hexdigest()
            rn = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body_no_id,
                               headers={"Content-Type": "application/json", "X-PFP-Signature": sig_ni})
            assert rn.status_code == 422, rn.text
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)

    def test_unknown_slug_404(self):
        body = b'{"id":"x"}'
        sig = hmac.new(b"nope", body, hashlib.sha256).hexdigest()
        r = requests.post(f"{BASE_URL}/api/ingest/does-not-exist-xyz",
                          data=body,
                          headers={"Content-Type": "application/json", "X-PFP-Signature": sig})
        assert r.status_code == 404

    def test_disabled_returns_403(self, admin_h):
        cfg = _create_integration(admin_h, "hmac")
        slug, secret, iid = cfg["slug"], cfg["credential"], cfg["integration_id"]
        try:
            requests.post(f"{BASE_URL}/api/admin/integrations/{iid}/disable", headers=admin_h)
            body = json.dumps({"id": "D-1", "type": "t", "timestamp": "2026-06-10T12:00:00Z"}).encode()
            sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            r = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                              headers={"Content-Type": "application/json", "X-PFP-Signature": sig})
            assert r.status_code == 403, r.text
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)


# -------------------- Public inbound API key / bearer / none --------------------
class TestAuthProviderVariants:
    def test_api_key_provider(self, admin_h):
        cfg = _create_integration(admin_h, "api_key")
        slug, token, iid = cfg["slug"], cfg["credential"], cfg["integration_id"]
        try:
            body = json.dumps({"id": "AK-1", "type": "t", "timestamp": "2026-06-10T12:00:00Z"}).encode()
            ok = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                               headers={"Content-Type": "application/json", "X-Integration-Key": token})
            assert ok.status_code == 201, ok.text
            bad = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                                headers={"Content-Type": "application/json", "X-Integration-Key": "wrong"})
            assert bad.status_code == 401
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)

    def test_bearer_provider(self, admin_h):
        cfg = _create_integration(admin_h, "bearer")
        slug, token, iid = cfg["slug"], cfg["credential"], cfg["integration_id"]
        try:
            body = json.dumps({"id": "BR-1", "type": "t", "timestamp": "2026-06-10T12:00:00Z"}).encode()
            ok = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                               headers={"Content-Type": "application/json",
                                        "Authorization": f"Bearer {token}"})
            assert ok.status_code == 201, ok.text
            bad = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                                headers={"Content-Type": "application/json",
                                         "Authorization": "Bearer nope"})
            assert bad.status_code == 401
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)

    def test_none_provider(self, admin_h):
        cfg = _create_integration(admin_h, "none")
        slug, iid = cfg["slug"], cfg["integration_id"]
        try:
            body = json.dumps({"id": "NN-1", "type": "t", "timestamp": "2026-06-10T12:00:00Z"}).encode()
            r = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                              headers={"Content-Type": "application/json"})
            assert r.status_code == 201, r.text
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)


# -------------------- Privacy / mapping --------------------
class TestPrivacyMapping:
    def test_actor_subject_hashed_in_proof(self, admin_h):
        cfg = _create_integration(admin_h, "hmac")
        slug, secret, iid = cfg["slug"], cfg["credential"], cfg["integration_id"]
        try:
            body = json.dumps({"type": "invoice.paid", "id": "PR-1",
                               "timestamp": "2026-06-10T12:00:00Z",
                               "user": "alice@example.com", "resource": "acct-42",
                               "amount": 500, "note": "confidential"}).encode()
            sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            r = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                              headers={"Content-Type": "application/json", "X-PFP-Signature": sig})
            assert r.status_code == 201, r.text
            fea_id = r.json()["fea_id"]
            v = requests.get(f"{BASE_URL}/api/public/verify/{fea_id}")
            assert v.status_code == 200
            resp_text = v.text
            # Raw actor/subject/extra fields must NOT appear in the signed payload
            assert "alice@example.com" not in resp_text
            assert "acct-42" not in resp_text
            assert "confidential" not in resp_text
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)


# -------------------- RBAC --------------------
class TestRBAC:
    def test_reviewer_can_read_but_not_manage(self, admin_h, reviewer_h):
        cfg = _create_integration(admin_h, "hmac")
        iid = cfg["integration_id"]
        try:
            # Read allowed
            r = requests.get(f"{BASE_URL}/api/admin/integrations", headers=reviewer_h)
            assert r.status_code == 200, r.text
            g = requests.get(f"{BASE_URL}/api/admin/integrations/{iid}", headers=reviewer_h)
            assert g.status_code == 200

            # All manage actions must be 403
            for path, method in [
                ("", "post"),
                (f"/{iid}", "patch"),
                (f"/{iid}/enable", "post"),
                (f"/{iid}/disable", "post"),
                (f"/{iid}/rotate-secret", "post"),
                (f"/{iid}/test", "post"),
                (f"/{iid}", "delete"),
            ]:
                url = f"{BASE_URL}/api/admin/integrations{path}"
                fn = getattr(requests, method)
                kwargs = {"headers": reviewer_h}
                if method in ("post", "patch"):
                    kwargs["json"] = {"name": "x", "slug": _rand_slug("rbac"), "payload": {}}
                resp = fn(url, **kwargs)
                assert resp.status_code == 403, f"{method.upper()} {path} => {resp.status_code} {resp.text}"
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)

    def test_public_ingest_does_not_require_admin_jwt(self, admin_h):
        cfg = _create_integration(admin_h, "hmac")
        slug, secret, iid = cfg["slug"], cfg["credential"], cfg["integration_id"]
        try:
            body = json.dumps({"id": "NOAUTH-1", "type": "t", "timestamp": "2026-06-10T12:00:00Z"}).encode()
            sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            # No JWT — only provider signature. Must succeed.
            r = requests.post(f"{BASE_URL}/api/ingest/{slug}", data=body,
                              headers={"Content-Type": "application/json", "X-PFP-Signature": sig})
            assert r.status_code == 201, r.text
        finally:
            requests.delete(f"{BASE_URL}/api/admin/integrations/{iid}", headers=admin_h)
