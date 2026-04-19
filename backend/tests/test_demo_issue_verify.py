"""
Backend tests for /api/demo/issue and /api/demo/verify/{proof_id}
Covers: determinism/idempotency, compliance embedding, validation, and verification states.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fea-crypto.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

HEX64 = lambda s: isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s)

COMPLIANT = {
    "kyc": "Pass",
    "aml": "Pass",
    "limits": "Within allowed range",
    "status": "COMPLIANT",
}
NON_COMPLIANT = {
    "kyc": "Fail",
    "aml": "Pass",
    "limits": "Within allowed range",
    "status": "NON-COMPLIANT",
}

BASE_TXN = {
    "transaction_id": "TEST_TXN-ISSUE-001",
    "user_id": "test_user_issue_001",
    "amount": "2450.00",
    "created_at": "2026-01-15T10:00:00Z",
}


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- /demo/issue ----------------

class TestDemoIssue:
    def test_issue_compliant_returns_valid_proof(self, api_client):
        payload = {**BASE_TXN, "compliance": COMPLIANT}
        r = api_client.post(f"{API}/demo/issue", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert HEX64(data["proof_id"])
        assert data["proof_hash"] == data["proof_id"]
        assert data["transaction_id"] == "TEST_TXN-ISSUE-001"
        # ISO UTC
        assert data["issued_at"].endswith("Z")
        assert "T" in data["issued_at"]
        assert data["metadata"]["algorithm"] == "SHA-256"

    def test_issue_non_compliant_produces_different_hash(self, api_client):
        c = api_client.post(f"{API}/demo/issue", json={**BASE_TXN, "compliance": COMPLIANT}).json()
        nc = api_client.post(f"{API}/demo/issue", json={**BASE_TXN, "compliance": NON_COMPLIANT}).json()
        assert c["proof_id"] != nc["proof_id"]
        assert HEX64(nc["proof_id"])

    def test_issue_is_idempotent(self, api_client):
        payload = {**BASE_TXN, "compliance": COMPLIANT}
        a = api_client.post(f"{API}/demo/issue", json=payload).json()
        b = api_client.post(f"{API}/demo/issue", json=payload).json()
        assert a["proof_id"] == b["proof_id"]

    @pytest.mark.parametrize("bad", [
        {"kyc": "Maybe", "aml": "Pass", "limits": "Within allowed range", "status": "COMPLIANT"},
        {"kyc": "Pass", "aml": "Nope", "limits": "Within allowed range", "status": "COMPLIANT"},
        {"kyc": "Pass", "aml": "Pass", "limits": "Too much", "status": "COMPLIANT"},
        {"kyc": "Pass", "aml": "Pass", "limits": "Within allowed range", "status": "MAYBE"},
    ])
    def test_issue_rejects_invalid_compliance_enum(self, api_client, bad):
        r = api_client.post(f"{API}/demo/issue", json={**BASE_TXN, "compliance": bad})
        assert r.status_code == 422, r.text


# ---------------- /demo/verify/{proof_id} ----------------

class TestDemoVerify:
    def test_verify_compliant_proof(self, api_client):
        issued = api_client.post(f"{API}/demo/issue", json={
            **BASE_TXN, "transaction_id": "TEST_TXN-VERIFY-C",
            "compliance": COMPLIANT
        }).json()
        pid = issued["proof_id"]
        r = api_client.get(f"{API}/demo/verify/{pid}")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert data["proof_id"] == pid
        assert data["transaction_id"] == "TEST_TXN-VERIFY-C"
        assert data["compliance"]["status"] == "COMPLIANT"
        assert data["compliance"]["kyc"] == "Pass"
        assert data["issued_at"].endswith("Z")

    def test_verify_non_compliant_proof(self, api_client):
        issued = api_client.post(f"{API}/demo/issue", json={
            **BASE_TXN, "transaction_id": "TEST_TXN-VERIFY-NC",
            "compliance": NON_COMPLIANT
        }).json()
        r = api_client.get(f"{API}/demo/verify/{issued['proof_id']}")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert data["compliance"]["status"] == "NON-COMPLIANT"
        assert data["compliance"]["kyc"] == "Fail"

    def test_verify_unknown_hex_returns_not_found(self, api_client):
        pid = "0" * 64
        r = api_client.get(f"{API}/demo/verify/{pid}")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is False
        assert data["reason"] == "Proof not found"

    @pytest.mark.parametrize("bad", ["not-hex", "abc", "g" * 64, "a" * 63, "a" * 65])
    def test_verify_malformed_proof_id(self, api_client, bad):
        r = api_client.get(f"{API}/demo/verify/{bad}")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is False
        assert data["reason"] == "Malformed Proof ID"


# ---------------- Back-compat: /demo/proof still works ----------------

class TestDemoProofStillWorks:
    def test_stateless_proof_endpoint_unchanged(self, api_client):
        r = api_client.post(f"{API}/demo/proof", json={
            "transaction_id": "TEST_TXN-LEGACY",
            "user_id": "test_legacy",
            "amount": "100.00",
            "created_at": "2026-01-01T00:00:00Z",
        })
        assert r.status_code == 200
        data = r.json()
        assert HEX64(data["proof_hash"])
