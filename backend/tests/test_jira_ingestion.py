"""Jira provider inbound ingestion integration tests.

Covers:
- Presets list includes Jira and all prior providers
- Admin can create Jira integration (api_key) via presets; token minted once
- Ingest with valid token -> 201 + fea_id
- Ingest with wrong/missing token -> 401
- 7 Jira event types normalize to correct event_type (via admin dry-run test endpoint)
- Public verify returns signature_valid=true + event_descriptor (Jira, Issue Tracking)
- Privacy: no raw email / display name / comment body appears in verify response
- Backward compatibility: generic (hmac_sha256) integration still creates & ingests OK
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"

RAW_EMAIL = "jane@corp.com"
RAW_DISPLAY = "Jane Doe"
RAW_COMMENT = "This is a super secret comment body that must never appear raw."


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _sample_payload(webhook_event="jira:issue_updated", *, changelog_items=None, comment=None, issue_event_type=None):
    return {
        "timestamp": int(time.time() * 1000),
        "webhookEvent": webhook_event,
        "issue_event_type_name": issue_event_type,
        "user": {"accountId": "acc-abc-123", "displayName": RAW_DISPLAY, "emailAddress": RAW_EMAIL},
        "issue": {
            "key": "TEST-42",
            "fields": {
                "summary": "Login page returns 500",
                "issuetype": {"name": "Bug"},
                "project": {"key": "TEST", "name": "Test Project"},
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "labels": ["urgent", "regression"],
                "duedate": "2026-02-01",
                "created": "2026-01-10T09:00:00.000Z",
                "updated": "2026-01-15T10:00:00.000Z",
                "assignee": {"accountId": "acc-xyz-999", "displayName": "John Smith", "emailAddress": "john@corp.com"},
            },
        },
        "changelog": {"id": "CL-1", "items": list(changelog_items or [])},
        "comment": comment or {},
    }


# ---------- Presets ----------
def test_presets_include_jira_and_priors(admin_headers):
    r = requests.get(f"{API}/admin/integrations/presets", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    presets = r.json()
    if isinstance(presets, dict):
        presets = presets.get("presets") or presets.get("items") or []
    ids = {p["id"] for p in presets}
    for pid in ("generic", "cashfree", "stripe", "razorpay", "github", "slack", "docusign", "shopify", "jira"):
        assert pid in ids, f"missing preset {pid}; got {ids}"
    jira = next(p for p in presets if p["id"] == "jira")
    assert jira["adapter"] == "jira"
    assert jira["auth_provider"] == "api_key"
    assert (jira.get("auth_config") or {}).get("token_header") == "x-automation-webhook-token"
    for m in ("api_key", "hmac_sha256", "bearer", "oauth2"):
        assert m in (jira.get("supported_auth_methods") or []), f"missing method {m}"


# ---------- Create Jira integration ----------
@pytest.fixture(scope="module")
def jira_integration(admin_headers):
    suffix = uuid.uuid4().hex[:8]
    slug = f"jira-{suffix}"
    body = {
        "name": f"Jira Test {suffix}",
        "slug": slug,
        "adapter": "jira",
        "auth_provider": "api_key",
        "auth_config": {
            "token_header": "x-automation-webhook-token",
            "site_url": "https://example.atlassian.net",
            "cloud_id": "cloud-abc-123",
        },
    }
    r = requests.post(f"{API}/admin/integrations", headers=admin_headers, json=body, timeout=30)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    data = r.json()
    integration_id = data.get("id") or data.get("integration_id") or (data.get("integration") or {}).get("id")
    credential = data.get("credential") or data.get("token") or data.get("secret") or data.get("api_key")
    assert integration_id, f"no id in response: {data}"
    assert credential, f"no one-time credential returned: {data}"
    # enable it (in case not enabled by default)
    en = requests.post(f"{API}/admin/integrations/{integration_id}/enable", headers=admin_headers, timeout=30)
    # some backends return 200/204/404 (no-op)
    assert en.status_code in (200, 204, 404, 409), en.text
    return {"id": integration_id, "slug": slug, "token": credential}


# ---------- Ingest valid ----------
def test_ingest_valid_token_returns_201(jira_integration):
    payload = _sample_payload(
        changelog_items=[{"field": "status", "fromString": "To Do", "toString": "In Progress"}]
    )
    headers = {
        "Content-Type": "application/json",
        "x-automation-webhook-token": jira_integration["token"],
    }
    r = requests.post(f"{API}/ingest/{jira_integration['slug']}", headers=headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
    body = r.json()
    fea_id = body.get("fea_id") or body.get("id")
    assert fea_id, body
    # stash for downstream verify test
    pytest.jira_fea_id = fea_id


# ---------- Ingest invalid ----------
def test_ingest_wrong_token_401(jira_integration):
    payload = _sample_payload()
    headers = {"Content-Type": "application/json", "x-automation-webhook-token": "wrong-token-xyz"}
    r = requests.post(f"{API}/ingest/{jira_integration['slug']}", headers=headers, json=payload, timeout=30)
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


def test_ingest_missing_token_401(jira_integration):
    payload = _sample_payload()
    r = requests.post(f"{API}/ingest/{jira_integration['slug']}", json=payload, timeout=30)
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


# ---------- 7 event type normalization via dry-run test endpoint ----------
EVENT_CASES = [
    ("issue_created", dict(webhook_event="jira:issue_created", issue_event_type="issue_created")),
    ("issue_updated", dict(webhook_event="jira:issue_updated", changelog_items=[{"field": "summary", "fromString": "a", "toString": "b"}])),
    ("assignee_changed", dict(webhook_event="jira:issue_updated", changelog_items=[{"field": "assignee", "fromString": "a", "toString": "b"}])),
    ("status_changed", dict(webhook_event="jira:issue_updated", changelog_items=[{"field": "status", "fromString": "To Do", "toString": "In Progress"}])),
    ("comment_added", dict(webhook_event="jira:issue_commented", issue_event_type="issue_commented", comment={"id": "c1", "body": RAW_COMMENT})),
    ("attachment_added", dict(webhook_event="jira:issue_updated", changelog_items=[{"field": "attachment", "fromString": None, "toString": "file.pdf"}])),
    ("issue_resolved", dict(webhook_event="jira:issue_updated", issue_event_type="issue_resolved", changelog_items=[{"field": "resolution", "fromString": None, "toString": "Done"}])),
]


@pytest.mark.parametrize("expected,kw", EVENT_CASES)
def test_event_type_normalization(admin_headers, jira_integration, expected, kw):
    payload = _sample_payload(**kw)
    r = requests.post(
        f"{API}/admin/integrations/{jira_integration['id']}/test",
        headers=admin_headers,
        json={"payload": payload, "issue": False},
        timeout=30,
    )
    assert r.status_code == 200, f"{expected}: {r.status_code} {r.text}"
    data = r.json()
    ne = data.get("normalized_event") or data.get("event") or data.get("common_event") or {}
    et = ne.get("event_type") if isinstance(ne, dict) else None
    assert et == expected, f"expected {expected}, got {et}; body={data}"


# ---------- Verify + Privacy ----------
def test_public_verify_and_privacy(jira_integration):
    fea_id = getattr(pytest, "jira_fea_id", None)
    assert fea_id, "must have ingested a proof first"
    time.sleep(1.0)
    r = requests.get(f"{API}/public/verify/{fea_id}", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("signature_valid") is True, data
    desc = data.get("event_descriptor") or {}
    assert desc, "missing event_descriptor"
    assert (desc.get("provider") or "").lower() == "jira"
    assert desc.get("provider_category") == "Issue Tracking"
    assert desc.get("event_source") == "Webhook"
    attrs = desc.get("attributes") or {}
    # non-sensitive metadata present
    assert any("Issue Key" == k or "Summary" == k or "Project" == k for k in attrs.keys()), attrs

    # PRIVACY: raw sensitive strings must not appear anywhere in verify response
    blob = str(data).lower()
    for leak in (RAW_EMAIL.lower(), "jane doe", "john smith", RAW_COMMENT.lower(), "john@corp.com"):
        assert leak not in blob, f"raw PII leaked: {leak!r}"


# ---------- Backward compatibility: generic ----------
def test_generic_integration_backward_compat(admin_headers):
    suffix = uuid.uuid4().hex[:8]
    slug = f"generic-{suffix}"
    body = {
        "name": f"Generic Test {suffix}",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "auth_config": {},
    }
    r = requests.post(f"{API}/admin/integrations", headers=admin_headers, json=body, timeout=30)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    integration_id = d.get("id") or d.get("integration_id") or (d.get("integration") or {}).get("id")
    secret = d.get("credential") or d.get("secret") or d.get("token")
    assert integration_id and secret, d
    en = requests.post(f"{API}/admin/integrations/{integration_id}/enable", headers=admin_headers, timeout=30)
    assert en.status_code in (200, 204, 404, 409), en.text

    # sign a body with the secret
    import hmac, hashlib, json as _json
    payload = {"event_type": "test_event", "id": f"evt-{suffix}", "amount": 100, "currency": "USD"}
    raw = _json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    r = requests.post(
        f"{API}/ingest/{slug}",
        data=raw,
        headers={"Content-Type": "application/json", "X-PFP-Signature": sig},
        timeout=30,
    )
    # If backend applies stricter policy, at least ensure non-401
    assert r.status_code in (200, 201), f"generic ingest failed: {r.status_code} {r.text}"
