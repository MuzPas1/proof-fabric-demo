"""Jira HMAC-SHA256 (X-Hub-Signature) ingestion tests — iteration 45.

Verifies the BUG FIX from api_key to hmac_sha256 (Jira Cloud native scheme).
Also asserts has_credential / has_hmac_secret / has_external_secret UX flags and
backward compatibility with generic + all existing presets.
"""
import os
import time
import uuid
import hmac
import hashlib
import json as _json
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"

RAW_EMAIL = "jane@corp.com"
RAW_DISPLAY = "Jane Doe"
RAW_ASSIGNEE_EMAIL = "john@corp.com"
RAW_ASSIGNEE = "John Smith"
RAW_COMMENT = "Super secret comment body that must never appear raw."


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _payload():
    return {
        "timestamp": int(time.time() * 1000),
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic",
        "user": {"accountId": "acc-abc-123", "displayName": RAW_DISPLAY, "emailAddress": RAW_EMAIL},
        "issue": {
            "key": "REL-42",
            "fields": {
                "summary": "Login page returns 500",
                "issuetype": {"name": "Bug"},
                "project": {"key": "REL", "name": "Release"},
                "status": {"name": "Done"},
                "priority": {"name": "High"},
                "labels": ["urgent"],
                "duedate": "2026-02-01",
                "created": "2026-01-10T09:00:00.000Z",
                "updated": "2026-01-15T10:00:00.000Z",
                "assignee": {"accountId": "acc-xyz-999", "displayName": RAW_ASSIGNEE, "emailAddress": RAW_ASSIGNEE_EMAIL},
            },
        },
        "changelog": {"id": "CL-1", "items": [{"field": "status", "fromString": "To Do", "toString": "Done"}]},
    }


def _create_jira(admin_headers, *, external_secret=None):
    suffix = uuid.uuid4().hex[:8]
    slug = f"jira-hmac-{suffix}"
    body = {
        "name": f"Jira HMAC {suffix}",
        "slug": slug,
        "adapter": "jira",
        "auth_provider": "hmac_sha256",
        "replay_protection": True,
        "auth_config": {
            "signature_scheme": "plain",
            "signature_header": "x-hub-signature",
            "signature_prefix": "sha256=",
            "signature_encoding": "hex",
            "site_url": "https://example.atlassian.net",
            "cloud_id": "cloud-abc-123",
        },
    }
    if external_secret:
        body["secret"] = external_secret
    r = requests.post(f"{API}/admin/integrations", headers=admin_headers, json=body, timeout=30)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    data = r.json()
    iid = data.get("id") or data.get("integration_id") or (data.get("integration") or {}).get("id")
    assert iid, data
    cred = data.get("credential") or data.get("secret")
    en = requests.post(f"{API}/admin/integrations/{iid}/enable", headers=admin_headers, timeout=30)
    assert en.status_code in (200, 204, 404, 409), en.text
    return {"id": iid, "slug": slug, "credential": cred, "external": external_secret}


# ---------- Preset check ----------
def test_jira_preset_is_hmac(admin_headers):
    r = requests.get(f"{API}/admin/integrations/presets", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    presets = r.json()
    if isinstance(presets, dict):
        presets = presets.get("presets") or presets.get("items") or []
    ids = {p["id"] for p in presets}
    for pid in ("generic", "cashfree", "stripe", "razorpay", "github", "slack", "docusign", "shopify", "jira"):
        assert pid in ids, f"missing preset {pid}"
    jira = next(p for p in presets if p["id"] == "jira")
    assert jira["auth_provider"] == "hmac_sha256", jira
    ac = jira.get("auth_config") or {}
    assert ac.get("signature_header") == "x-hub-signature"
    assert ac.get("signature_prefix") == "sha256="
    assert ac.get("signature_encoding") == "hex"
    assert jira.get("replay_protection") is True


# ---------- Minted-secret Jira integration ----------
@pytest.fixture(scope="module")
def jira_minted(admin_headers):
    return _create_jira(admin_headers)


def test_minted_credential_returned(jira_minted):
    assert jira_minted["credential"], "PFP must mint a secret when none provided"
    assert len(jira_minted["credential"]) >= 16


def test_has_credential_flags_minted(admin_headers, jira_minted):
    r = requests.get(f"{API}/admin/integrations/{jira_minted['id']}", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    # public view (may or may not be wrapped)
    view = d.get("integration") or d
    assert view.get("has_credential") is True, f"has_credential missing/false: {view}"
    assert view.get("has_hmac_secret") is True, view
    assert view.get("has_external_secret") is False, view


def test_ingest_valid_hmac_returns_201(jira_minted):
    secret = jira_minted["credential"]
    payload = _payload()
    payload["issue"]["key"] = f"REL-{uuid.uuid4().hex[:6]}"
    raw = _json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    r = requests.post(
        f"{API}/ingest/{jira_minted['slug']}",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature": f"sha256={sig}"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
    body = r.json()
    fea_id = body.get("fea_id") or body.get("id")
    assert fea_id, body
    pytest.jira_hmac_fea_id = fea_id


def test_ingest_no_signature_401(jira_minted):
    payload = _payload()
    r = requests.post(f"{API}/ingest/{jira_minted['slug']}", json=payload, timeout=30)
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


def test_ingest_wrong_signature_401(jira_minted):
    payload = _payload()
    raw = _json.dumps(payload, separators=(",", ":")).encode()
    r = requests.post(
        f"{API}/ingest/{jira_minted['slug']}",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature": "sha256=" + ("0" * 64)},
        timeout=30,
    )
    assert r.status_code == 401


def test_public_verify_and_privacy(jira_minted):
    fea_id = getattr(pytest, "jira_hmac_fea_id", None)
    assert fea_id
    time.sleep(1.0)
    r = requests.get(f"{API}/public/verify/{fea_id}", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("signature_valid") is True, data
    desc = data.get("event_descriptor") or {}
    assert (desc.get("provider") or "").lower() == "jira"
    assert desc.get("provider_category") == "Issue Tracking"
    blob = _json.dumps(data).lower()
    for leak in (RAW_EMAIL.lower(), RAW_ASSIGNEE_EMAIL.lower(), RAW_DISPLAY.lower(), RAW_ASSIGNEE.lower(), RAW_COMMENT.lower()):
        assert leak not in blob, f"raw PII leaked: {leak!r}"


# ---------- External secret variant ----------
@pytest.fixture(scope="module")
def jira_external(admin_headers):
    return _create_jira(admin_headers, external_secret="mySharedSecret123")


def test_external_secret_no_minted_credential(jira_external):
    # When user supplies their own secret, response should NOT include a minted credential
    assert not jira_external["credential"], f"unexpected minted credential: {jira_external['credential']!r}"


def test_has_credential_flags_external(admin_headers, jira_external):
    r = requests.get(f"{API}/admin/integrations/{jira_external['id']}", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    view = d.get("integration") or d
    assert view.get("has_credential") is True, view
    assert view.get("has_external_secret") is True, view


def test_external_secret_ingest_ok(jira_external):
    secret = "mySharedSecret123"
    payload = _payload()
    payload["issue"]["key"] = f"EXT-{uuid.uuid4().hex[:6]}"  # unique to avoid idempotency clash
    raw = _json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    r = requests.post(
        f"{API}/ingest/{jira_external['slug']}",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature": f"sha256={sig}"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"{r.status_code} {r.text}"


# ---------- Backward compat: generic ----------
def test_generic_hmac_backward_compat(admin_headers):
    suffix = uuid.uuid4().hex[:8]
    slug = f"generic-{suffix}"
    body = {"name": f"Generic {suffix}", "slug": slug, "adapter": "generic", "auth_provider": "hmac_sha256", "auth_config": {}}
    r = requests.post(f"{API}/admin/integrations", headers=admin_headers, json=body, timeout=30)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    iid = d.get("id") or d.get("integration_id") or (d.get("integration") or {}).get("id")
    secret = d.get("credential") or d.get("secret")
    assert iid and secret, d
    en = requests.post(f"{API}/admin/integrations/{iid}/enable", headers=admin_headers, timeout=30)
    assert en.status_code in (200, 204, 404, 409)
    payload = {"event_type": "test_event", "id": f"evt-{suffix}", "amount": 100, "currency": "USD"}
    raw = _json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    r = requests.post(
        f"{API}/ingest/{slug}",
        data=raw,
        headers={"Content-Type": "application/json", "X-PFP-Signature": sig},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"generic ingest: {r.status_code} {r.text}"


# ---------- Backward compat: create Cashfree preset via API ----------
def test_cashfree_preset_creation(admin_headers):
    suffix = uuid.uuid4().hex[:8]
    slug = f"cashfree-{suffix}"
    body = {
        "name": f"Cashfree {suffix}",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "auth_config": {"signature_scheme": "plain", "signature_header": "x-webhook-signature"},
    }
    r = requests.post(f"{API}/admin/integrations", headers=admin_headers, json=body, timeout=30)
    assert r.status_code in (200, 201), r.text
