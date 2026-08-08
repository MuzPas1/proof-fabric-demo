"""Live-validation tests for Tarabut Balances/Transactions/Account-Data outbound prove endpoints.

Covers:
- POST /api/admin/tarabut/account-data live: expects 200 + consent_required:true, account_count:0
- prove-event for balance_retrieved, transaction_retrieved, account_retrieved => 200 + fea_id
- public FEA verification => valid:true + zero PII leakage (IBAN/PAN/holder name)
- balances/transactions endpoints require account_id (400) and RBAC (401 w/o token)
- regression: presets list + generic HMAC integration simulate ok
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pfp-trust-statement.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"
CUSTOMER_USER_ID = "pfp-blue-001"

IBAN = "BH67CITI00001234567890"
PAN = "453212******7890"
HOLDER = "John Snow"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, r.json()
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tarabut_integration_id(auth_headers):
    """Locate the pre-seeded Tarabut Bahrain integration id."""
    r = requests.get(f"{BASE_URL}/api/admin/integrations", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    for it in items:
        if it.get("slug") == "tarabut-bahrain" or (it.get("adapter") == "tarabut"):
            return it.get("id") or it.get("_id")
    pytest.skip("No tarabut integration seeded")


# ---------- account-data live ----------
def test_account_data_live_consent_required(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/admin/tarabut/account-data",
        headers=auth_headers,
        json={"customer_user_id": CUSTOMER_USER_ID},
        timeout=60,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert body.get("account_count") == 0, body
    assert body.get("consent_required") is True, body


# ---------- prove-event: balance ----------
def _verify_public_proof(fea_id, expected_event_type, forbidden_pii):
    r = requests.get(f"{BASE_URL}/api/fea/public/{fea_id}", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("valid") is True, body
    ev = body.get("artifact", {}).get("event_descriptor", {})
    assert ev.get("event_type") == expected_event_type, ev
    raw = r.text
    for pii in forbidden_pii:
        assert pii not in raw, f"PII '{pii}' leaked in public verification response"


def test_prove_balance_and_verify_no_pii(auth_headers):
    payload = {
        "event": {
            "tarabutEventType": "balance_retrieved",
            "externalId": "acc-9:CLOSINGAVAILABLE",
            "status": "CLOSINGAVAILABLE",
            "amount": "1523.75",
            "currency": "BHD",
            "eventSource": "API",
            "attributes": {"Balance Type": "CLOSINGAVAILABLE", "Amount": "1523.75 BHD"},
            "sensitive": {"account": "acc-9", "iban": IBAN},
        }
    }
    r = requests.post(f"{BASE_URL}/api/admin/tarabut/prove-event", headers=auth_headers, json=payload, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("event_type") == "balance_retrieved", body
    fea_id = body.get("fea_id")
    assert fea_id
    _verify_public_proof(fea_id, "balance_retrieved", [IBAN])


def test_prove_transaction_and_verify_no_pii(auth_headers):
    payload = {
        "event": {
            "tarabutEventType": "transaction_retrieved",
            "externalId": "txn-123",
            "amount": "42.50",
            "currency": "BHD",
            "providerId": "BLUE",
            "eventSource": "API",
            "attributes": {
                "Description": "Grocery Store",
                "Category": "Groceries",
                "Credit/Debit": "Debit",
                "Amount": "42.50 BHD",
            },
            "sensitive": {"account": "acc-9", "pan": PAN},
        }
    }
    r = requests.post(f"{BASE_URL}/api/admin/tarabut/prove-event", headers=auth_headers, json=payload, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("event_type") == "transaction_retrieved", body
    fea_id = body.get("fea_id")
    assert fea_id
    _verify_public_proof(fea_id, "transaction_retrieved", [PAN])


def test_prove_account_and_verify_no_pii(auth_headers):
    payload = {
        "event": {
            "tarabutEventType": "account_retrieved",
            "externalId": "acc-9",
            "status": "ACTIVE",
            "providerId": "BLUE",
            "eventSource": "API",
            "attributes": {"Account Product Type": "CurrentAccount"},
            "sensitive": {"account": "acc-9", "accountHolderName": HOLDER, "iban": IBAN},
        }
    }
    r = requests.post(f"{BASE_URL}/api/admin/tarabut/prove-event", headers=auth_headers, json=payload, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("event_type") == "account_retrieved", body
    fea_id = body.get("fea_id")
    assert fea_id
    _verify_public_proof(fea_id, "account_retrieved", [HOLDER, IBAN])


# ---------- balances/transactions require account_id + RBAC ----------
def test_balances_requires_account_id(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/admin/tarabut/balances",
        headers=auth_headers,
        json={"customer_user_id": CUSTOMER_USER_ID},
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"


def test_transactions_requires_account_id(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/admin/tarabut/transactions",
        headers=auth_headers,
        json={"customer_user_id": CUSTOMER_USER_ID},
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"


def test_balances_rbac_no_token():
    r = requests.post(
        f"{BASE_URL}/api/admin/tarabut/balances",
        json={"customer_user_id": CUSTOMER_USER_ID, "account_id": "acc-9"},
        timeout=30,
    )
    assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"


def test_transactions_rbac_no_token():
    r = requests.post(
        f"{BASE_URL}/api/admin/tarabut/transactions",
        json={"customer_user_id": CUSTOMER_USER_ID, "account_id": "acc-9"},
        timeout=30,
    )
    assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"


def test_balances_live_with_bogus_account(auth_headers):
    """WITH account_id, endpoint should be reachable; upstream may 4xx OR return empty proofs."""
    r = requests.post(
        f"{BASE_URL}/api/admin/tarabut/balances",
        headers=auth_headers,
        json={"customer_user_id": CUSTOMER_USER_ID, "account_id": "nonexistent"},
        timeout=60,
    )
    # accept 200 with empty results, or 4xx upstream error — just NOT 500 and NOT 401/403
    assert r.status_code < 500, f"server error: {r.status_code} {r.text}"
    assert r.status_code not in (401, 403), r.text


# ---------- Regression ----------
def test_presets_list(auth_headers):
    r = requests.get(f"{BASE_URL}/api/admin/integrations/presets", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    presets = body if isinstance(body, list) else body.get("presets", body.get("items", []))
    slugs = set()
    for p in presets:
        slugs.add(p.get("id") or p.get("slug") or p.get("name"))
    expected = {"generic", "cashfree", "stripe", "razorpay", "github", "slack", "docusign", "shopify", "jira", "tarabut"}
    missing = expected - slugs
    assert not missing, f"missing presets: {missing} (got {slugs})"


def test_generic_hmac_simulate_ok(auth_headers):
    slug = f"test-hmac-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": f"TEST HMAC {slug}",
        "slug": slug,
        "adapter": "generic",
        "auth_provider": "hmac_sha256",
        "config": {},
    }
    r = requests.post(f"{BASE_URL}/api/admin/integrations", headers=auth_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create failed {r.status_code} {r.text}"
    integ = r.json()
    integ_id = integ.get("integration_id") or integ.get("id") or integ.get("_id")
    assert integ_id, integ
    try:
        sim = requests.post(f"{BASE_URL}/api/admin/integrations/{integ_id}/simulate", headers=auth_headers, timeout=60)
        assert sim.status_code == 200, sim.text
        body = sim.json()
        assert body.get("ok") is True, body
        # phases
        phases = body.get("phases") or body
        for key in ("connection", "authentication", "proof", "verification"):
            phase = phases.get(key) if isinstance(phases, dict) else None
            if phase is not None:
                # accept either bool True or {ok:true}
                assert phase is True or (isinstance(phase, dict) and (phase.get("ok") is True or phase.get("success") is True)), f"{key} not ok: {phase}"
    finally:
        requests.delete(f"{BASE_URL}/api/admin/integrations/{integ_id}", headers=auth_headers, timeout=30)
