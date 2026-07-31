"""Iteration 46 — Test Webhook Simulator + Verify page business layer + backward compat.

Covers:
- POST /api/admin/integrations/{id}/simulate for Jira HMAC (all 4 steps success, real proof).
- Simulate for a generic PFP-signed HMAC integration (ok:true, verifies via /public/verify).
- Simulate does NOT bump accepted/rejected counters (event recorded as 'test').
- Backward compat: Jira HMAC signed ingest still returns 201; existing proof still verifies.
- Presets list still contains all 9 providers.
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

KNOWN_JIRA_FEA = "c5d02a1f-ab24-4118-89e8-bda23fd854c9"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _uniq(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _create_and_enable(admin_headers, body):
    r = requests.post(f"{API}/admin/integrations", headers=admin_headers, json=body, timeout=30)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    cfg = r.json()
    iid = cfg["integration_id"]
    er = requests.post(f"{API}/admin/integrations/{iid}/enable", headers=admin_headers, timeout=30)
    assert er.status_code == 200, er.text
    return cfg


# -------------------- Simulate: Jira HMAC --------------------
def test_simulate_jira_hmac(admin_headers):
    slug = _uniq("sim-jira")
    cfg = _create_and_enable(admin_headers, {
        "name": "Sim Jira",
        "slug": slug,
        "adapter": "jira",
        "auth_provider": "hmac_sha256",
        "auth_config": {
            "signature_scheme": "plain",
            "signature_header": "x-hub-signature",
            "signature_prefix": "sha256=",
            "signature_encoding": "hex",
        },
    })
    iid = cfg["integration_id"]
    assert cfg.get("credential"), "expected minted credential (whsec_)"

    r = requests.post(f"{API}/admin/integrations/{iid}/simulate", headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True, data
    assert data.get("fea_id"), data
    assert data.get("sample_event_type") == "status_changed", data
    steps = {s["key"]: s for s in data["steps"]}
    for k in ("connection", "authentication", "proof", "verification"):
        assert steps[k]["status"] == "success", (k, steps[k])
    assert "verified" in steps["authentication"]["detail"].lower()

    # The minted proof must verify publicly.
    vr = requests.get(f"{API}/public/verify/{data['fea_id']}", timeout=30)
    assert vr.status_code == 200
    vj = vr.json()
    assert vj.get("signature_valid") is True, vj

    # Simulate should NOT inflate accepted/rejected counters.
    sr = requests.get(f"{API}/admin/integrations/{iid}/stats", headers=admin_headers, timeout=30)
    assert sr.status_code == 200
    stats = sr.json()
    # 'test' events must not be counted in accepted/rejected
    assert (stats.get("total_accepted") or 0) == 0, stats
    assert (stats.get("total_rejected") or 0) == 0, stats


# -------------------- Simulate: generic HMAC --------------------
def test_simulate_generic_hmac(admin_headers):
    slug = _uniq("sim-gen")
    cfg = _create_and_enable(admin_headers, {
        "name": "Sim Generic",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "auth_config": {"signature_scheme": "plain", "signature_header": "x-pfp-signature", "signature_encoding": "hex"},
    })
    iid = cfg["integration_id"]
    assert cfg.get("credential")

    r = requests.post(f"{API}/admin/integrations/{iid}/simulate", headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True, data
    steps = {s["key"]: s["status"] for s in data["steps"]}
    assert steps == {"connection": "success", "authentication": "success", "proof": "success", "verification": "success"}, steps

    vr = requests.get(f"{API}/public/verify/{data['fea_id']}", timeout=30).json()
    assert vr.get("signature_valid") is True


# -------------------- Backward compat: Jira HMAC inbound ingest still works --------------------
def test_jira_hmac_inbound_ingest_still_works(admin_headers):
    slug = _uniq("bc-jira")
    cfg = _create_and_enable(admin_headers, {
        "name": "BC Jira",
        "slug": slug,
        "adapter": "jira",
        "auth_provider": "hmac_sha256",
        "auth_config": {
            "signature_scheme": "plain",
            "signature_header": "x-hub-signature",
            "signature_prefix": "sha256=",
            "signature_encoding": "hex",
        },
    })
    secret = cfg["credential"]
    payload = {
        "timestamp": int(time.time() * 1000),
        "webhookEvent": "jira:issue_updated",
        "issue_event_type_name": "issue_generic",
        "user": {"accountId": "acc-1", "displayName": "T"},
        "issue": {
            "key": f"BC-{uuid.uuid4().hex[:4]}",
            "fields": {
                "summary": "BC test",
                "issuetype": {"name": "Task"},
                "project": {"key": "BC", "name": "BC"},
                "status": {"name": "Done"},
                "priority": {"name": "Low"},
                "labels": [],
                "duedate": "2026-06-01",
                "created": "2026-01-10T09:00:00.000Z",
                "updated": "2026-01-15T10:00:00.000Z",
            },
        },
        "changelog": {"id": "CL-BC", "items": [{"field": "status", "fromString": "To Do", "toString": "Done"}]},
    }
    raw = _json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    r = requests.post(
        f"{API}/ingest/{slug}",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature": f"sha256={sig}"},
        timeout=30,
    )
    assert r.status_code == 201, f"{r.status_code} {r.text}"
    assert r.json().get("fea_id")


# -------------------- Backward compat: existing known-good Jira proof still verifies --------------------
def test_known_jira_proof_still_verifies():
    r = requests.get(f"{API}/public/verify/{KNOWN_JIRA_FEA}", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("signature_valid") is True, data
    # Business-layer readable event descriptor should exist
    ed = data.get("event_descriptor") or {}
    assert (ed.get("provider") or "").lower() == "jira", ed


# -------------------- Presets endpoint still returns all 9 providers --------------------
def test_presets_all_nine(admin_headers):
    r = requests.get(f"{API}/admin/integrations/presets", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["presets"]}
    expected = {"generic", "cashfree", "stripe", "razorpay", "github", "slack", "docusign", "shopify", "jira"}
    assert expected.issubset(ids), ids
