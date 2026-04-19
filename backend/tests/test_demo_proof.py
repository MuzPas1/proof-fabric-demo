"""Tests for POST /api/demo/proof — Two-Party Proof Comparison."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fea-crypto.preview.emergentagent.com").rstrip("/")
ENDPOINT = f"{BASE_URL}/api/demo/proof"


DEFAULT = {
    "transaction_id": "TXN-8F2C-2026-00418",
    "user_id": "user_92341",
    "amount": "2450.00",
    "created_at": "2026-02-10T14:23:00Z",
}


@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- Basic endpoint validation ---
class TestDemoProofBasic:
    def test_happy_path_returns_proof(self, client):
        r = client.post(ENDPOINT, json=DEFAULT)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "proof_hash" in data and isinstance(data["proof_hash"], str)
        assert len(data["proof_hash"]) == 64  # SHA-256 hex
        assert "normalized_payload" in data
        np = data["normalized_payload"]
        assert np["transaction_id"] == "TXN-8F2C-2026-00418"
        assert np["user_id"] == "user_92341"
        assert np["amount"] == "2450.00"
        assert np["created_at"].endswith("Z")
        assert "metadata" in data
        assert data["metadata"]["algorithm"] == "SHA-256"
        assert "sorted-keys" in data["metadata"]["canonicalization"]

    def test_determinism_same_input_same_hash(self, client):
        h1 = client.post(ENDPOINT, json=DEFAULT).json()["proof_hash"]
        h2 = client.post(ENDPOINT, json=DEFAULT).json()["proof_hash"]
        assert h1 == h2


# --- Normalization equivalence ---
class TestDemoProofNormalization:
    def test_user_id_casing_and_whitespace(self, client):
        a = {**DEFAULT, "user_id": "Alice"}
        b = {**DEFAULT, "user_id": "  alice  "}
        ha = client.post(ENDPOINT, json=a).json()["proof_hash"]
        hb = client.post(ENDPOINT, json=b).json()["proof_hash"]
        assert ha == hb, "user_id trim+lowercase should produce identical proof_hash"

    def test_amount_formats_equivalent(self, client):
        a = {**DEFAULT, "amount": 100.5}
        b = {**DEFAULT, "amount": "100.50"}
        c = {**DEFAULT, "amount": "  100.5 "}
        ha = client.post(ENDPOINT, json=a).json()["proof_hash"]
        hb = client.post(ENDPOINT, json=b).json()["proof_hash"]
        hc = client.post(ENDPOINT, json=c).json()["proof_hash"]
        assert ha == hb == hc
        # normalized to 2 decimals
        np = client.post(ENDPOINT, json=a).json()["normalized_payload"]
        assert np["amount"] == "100.50"

    def test_transaction_id_whitespace_trim(self, client):
        a = {**DEFAULT, "transaction_id": "TXN-1"}
        b = {**DEFAULT, "transaction_id": "  TXN-1  "}
        ha = client.post(ENDPOINT, json=a).json()["proof_hash"]
        hb = client.post(ENDPOINT, json=b).json()["proof_hash"]
        assert ha == hb

    def test_timestamp_iso_normalized(self, client):
        r = client.post(ENDPOINT, json=DEFAULT)
        assert r.status_code == 200
        ts = r.json()["normalized_payload"]["created_at"]
        # Expected ISO 8601 UTC with millisecond .000Z
        assert ts.endswith("Z")
        assert ".000Z" in ts or ts.endswith(".000Z")


# --- Differentiation ---
class TestDemoProofDifferentiation:
    def test_different_amount_produces_different_hash(self, client):
        a = {**DEFAULT, "amount": "2450.00"}
        b = {**DEFAULT, "amount": "2450.01"}
        ha = client.post(ENDPOINT, json=a).json()["proof_hash"]
        hb = client.post(ENDPOINT, json=b).json()["proof_hash"]
        assert ha != hb

    def test_different_user_id_produces_different_hash(self, client):
        a = {**DEFAULT, "user_id": "user_1"}
        b = {**DEFAULT, "user_id": "user_2"}
        ha = client.post(ENDPOINT, json=a).json()["proof_hash"]
        hb = client.post(ENDPOINT, json=b).json()["proof_hash"]
        assert ha != hb


# --- Validation errors ---
class TestDemoProofValidation:
    def test_invalid_amount_returns_400(self, client):
        r = client.post(ENDPOINT, json={**DEFAULT, "amount": "not-a-number"})
        assert r.status_code == 400, r.text

    def test_empty_amount_returns_400(self, client):
        r = client.post(ENDPOINT, json={**DEFAULT, "amount": "   "})
        assert r.status_code == 400, r.text

    def test_invalid_timestamp_returns_400(self, client):
        r = client.post(ENDPOINT, json={**DEFAULT, "created_at": "not-a-timestamp"})
        assert r.status_code == 400, r.text

    def test_missing_required_field_returns_422(self, client):
        payload = {k: v for k, v in DEFAULT.items() if k != "user_id"}
        r = client.post(ENDPOINT, json=payload)
        assert r.status_code == 422
