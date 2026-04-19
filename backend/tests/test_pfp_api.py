"""
Proof Fabric Protocol (PFP) API Tests

Tests for:
1. FEA Generation (POST /api/fea/generate)
2. Idempotency (same idempotency_key + same payload → same FEA)
3. Idempotency conflict (same idempotency_key + different payload → 409)
4. Replay protection (different idempotency_key + same transaction_id/timestamp + same payload → existing FEA)
5. Replay attack detection (different idempotency_key + same transaction_id/timestamp + different payload → 409)
6. Key registry persistence (GET /api/public/keys)
7. Public verification (GET /api/public/verify/{fea_id})
8. API verification (POST /api/fea/verify)
9. Edge cases (missing fields, non-existent FEA)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://fea-crypto.preview.emergentagent.com"


class TestSetup:
    """Setup tests - get API key and verify basic connectivity"""
    
    @pytest.fixture(scope="class")
    def api_key(self):
        """Get API key from /api/config"""
        response = requests.get(f"{BASE_URL}/api/config")
        assert response.status_code == 200, f"Failed to get config: {response.text}"
        data = response.json()
        assert "test_api_key" in data, "Missing test_api_key in config"
        return data["test_api_key"]
    
    def test_health_check(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
    
    def test_config_endpoint(self):
        """Test config endpoint returns API key"""
        response = requests.get(f"{BASE_URL}/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "test_api_key" in data
        assert "endpoints" in data
        print(f"✓ Config endpoint passed, API key: {data['test_api_key'][:10]}...")


class TestFEAGeneration:
    """Test FEA generation endpoint"""
    
    @pytest.fixture(scope="class")
    def api_key(self):
        """Get API key from /api/config"""
        response = requests.get(f"{BASE_URL}/api/config")
        assert response.status_code == 200
        return response.json()["test_api_key"]
    
    @pytest.fixture
    def valid_payload(self):
        """Generate a valid FEA payload with unique IDs"""
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        return {
            "idempotency_key": f"TEST_idem_{unique_id}",
            "transaction_id": f"TEST_txn_{unique_id}",
            "timestamp": timestamp,
            "amount": 10000,
            "currency": "INR",
            "payer_id": "payer_hash_123",
            "payee_id": "payee_hash_456",
            "metadata": {"test": True}
        }
    
    def test_generate_fea_success(self, api_key, valid_payload):
        """Test basic FEA generation with fresh data"""
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(
            f"{BASE_URL}/api/fea/generate",
            json=valid_payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"FEA generation failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "fea_id" in data
        assert "fea_payload" in data
        assert "signature" in data
        assert "signature_version" in data
        assert data["signature_version"] == "v2"
        assert "public_key_id" in data
        assert "created_at" in data
        
        # Validate fea_payload structure
        fea_payload = data["fea_payload"]
        assert fea_payload["fea_version"] == "1.0"
        assert "transaction_summary" in fea_payload
        assert fea_payload["transaction_summary"]["transaction_id"] == valid_payload["transaction_id"]
        assert fea_payload["transaction_summary"]["amount"] == valid_payload["amount"]
        assert fea_payload["transaction_summary"]["currency"] == "INR"
        assert "fea_hash" in fea_payload
        
        print(f"✓ FEA generated successfully: {data['fea_id']}")
        return data
    
    def test_generate_fea_missing_api_key(self, valid_payload):
        """Test FEA generation without API key returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/fea/generate",
            json=valid_payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Missing API key correctly returns 401")
    
    def test_generate_fea_missing_required_fields(self, api_key):
        """Test FEA generation with missing required fields returns 400/422"""
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        
        # Missing transaction_id
        incomplete_payload = {
            "idempotency_key": "test_key",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": 1000,
            "currency": "INR",
            "payer_id": "payer",
            "payee_id": "payee"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/fea/generate",
            json=incomplete_payload,
            headers=headers
        )
        
        # FastAPI returns 422 for validation errors
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Missing required fields correctly returns 400/422")


class TestIdempotency:
    """Test idempotency key behavior"""
    
    @pytest.fixture(scope="class")
    def api_key(self):
        """Get API key from /api/config"""
        response = requests.get(f"{BASE_URL}/api/config")
        return response.json()["test_api_key"]
    
    def test_idempotency_same_payload_returns_same_fea(self, api_key):
        """Same idempotency_key + same payload → returns same FEA (200)"""
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        payload = {
            "idempotency_key": f"TEST_idem_same_{unique_id}",
            "transaction_id": f"TEST_txn_same_{unique_id}",
            "timestamp": timestamp,
            "amount": 5000,
            "currency": "USD",
            "payer_id": "payer_same",
            "payee_id": "payee_same"
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        
        # First request
        response1 = requests.post(f"{BASE_URL}/api/fea/generate", json=payload, headers=headers)
        assert response1.status_code == 200, f"First request failed: {response1.text}"
        fea1 = response1.json()
        
        # Second request with same payload
        response2 = requests.post(f"{BASE_URL}/api/fea/generate", json=payload, headers=headers)
        assert response2.status_code == 200, f"Second request failed: {response2.text}"
        fea2 = response2.json()
        
        # Should return the same FEA
        assert fea1["fea_id"] == fea2["fea_id"], "Idempotency failed: different fea_id returned"
        assert fea1["signature"] == fea2["signature"], "Idempotency failed: different signature returned"
        
        print(f"✓ Idempotency works: same payload returns same FEA ({fea1['fea_id']})")
    
    def test_idempotency_conflict_different_payload(self, api_key):
        """Same idempotency_key + different payload → 409 Conflict"""
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        idem_key = f"TEST_idem_conflict_{unique_id}"
        
        payload1 = {
            "idempotency_key": idem_key,
            "transaction_id": f"TEST_txn_conflict1_{unique_id}",
            "timestamp": timestamp,
            "amount": 1000,
            "currency": "INR",
            "payer_id": "payer1",
            "payee_id": "payee1"
        }
        
        payload2 = {
            "idempotency_key": idem_key,  # Same idempotency key
            "transaction_id": f"TEST_txn_conflict2_{unique_id}",  # Different transaction
            "timestamp": timestamp,
            "amount": 2000,  # Different amount
            "currency": "INR",
            "payer_id": "payer2",
            "payee_id": "payee2"
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        
        # First request
        response1 = requests.post(f"{BASE_URL}/api/fea/generate", json=payload1, headers=headers)
        assert response1.status_code == 200, f"First request failed: {response1.text}"
        
        # Second request with different payload but same idempotency key
        response2 = requests.post(f"{BASE_URL}/api/fea/generate", json=payload2, headers=headers)
        assert response2.status_code == 409, f"Expected 409, got {response2.status_code}: {response2.text}"
        
        error_detail = response2.json().get("detail", "")
        assert "Idempotency key already used with different payload" in error_detail, f"Unexpected error: {error_detail}"
        
        print("✓ Idempotency conflict correctly returns 409")


class TestReplayProtection:
    """Test transaction replay protection"""
    
    @pytest.fixture(scope="class")
    def api_key(self):
        """Get API key from /api/config"""
        response = requests.get(f"{BASE_URL}/api/config")
        return response.json()["test_api_key"]
    
    def test_replay_same_payload_returns_existing_fea(self, api_key):
        """Different idempotency_key + same (transaction_id, timestamp) + same payload → returns existing FEA (200)"""
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        txn_id = f"TEST_txn_replay_same_{unique_id}"
        
        payload1 = {
            "idempotency_key": f"TEST_idem_replay1_{unique_id}",
            "transaction_id": txn_id,
            "timestamp": timestamp,
            "amount": 7500,
            "currency": "EUR",
            "payer_id": "payer_replay",
            "payee_id": "payee_replay"
        }
        
        payload2 = {
            "idempotency_key": f"TEST_idem_replay2_{unique_id}",  # Different idempotency key
            "transaction_id": txn_id,  # Same transaction_id
            "timestamp": timestamp,  # Same timestamp
            "amount": 7500,  # Same amount
            "currency": "EUR",  # Same currency
            "payer_id": "payer_replay",  # Same payer
            "payee_id": "payee_replay"  # Same payee
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        
        # First request
        response1 = requests.post(f"{BASE_URL}/api/fea/generate", json=payload1, headers=headers)
        assert response1.status_code == 200, f"First request failed: {response1.text}"
        fea1 = response1.json()
        
        # Second request with different idempotency key but same transaction data
        response2 = requests.post(f"{BASE_URL}/api/fea/generate", json=payload2, headers=headers)
        assert response2.status_code == 200, f"Second request failed: {response2.text}"
        fea2 = response2.json()
        
        # Should return the same FEA (replay protection returns existing)
        assert fea1["fea_id"] == fea2["fea_id"], f"Replay protection failed: different fea_id returned ({fea1['fea_id']} vs {fea2['fea_id']})"
        
        print(f"✓ Replay protection works: same transaction data returns existing FEA ({fea1['fea_id']})")
    
    def test_replay_attack_different_payload_returns_409(self, api_key):
        """Different idempotency_key + same (transaction_id, timestamp) + different payload → 409 with specific message"""
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        txn_id = f"TEST_txn_replay_attack_{unique_id}"
        
        payload1 = {
            "idempotency_key": f"TEST_idem_attack1_{unique_id}",
            "transaction_id": txn_id,
            "timestamp": timestamp,
            "amount": 10000,
            "currency": "INR",
            "payer_id": "payer_attack1",
            "payee_id": "payee_attack1"
        }
        
        payload2 = {
            "idempotency_key": f"TEST_idem_attack2_{unique_id}",  # Different idempotency key
            "transaction_id": txn_id,  # Same transaction_id
            "timestamp": timestamp,  # Same timestamp
            "amount": 99999,  # DIFFERENT amount - replay attack!
            "currency": "INR",
            "payer_id": "payer_attack2",  # Different payer
            "payee_id": "payee_attack2"  # Different payee
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        
        # First request
        response1 = requests.post(f"{BASE_URL}/api/fea/generate", json=payload1, headers=headers)
        assert response1.status_code == 200, f"First request failed: {response1.text}"
        
        # Second request - replay attack attempt
        response2 = requests.post(f"{BASE_URL}/api/fea/generate", json=payload2, headers=headers)
        assert response2.status_code == 409, f"Expected 409 for replay attack, got {response2.status_code}: {response2.text}"
        
        error_detail = response2.json().get("detail", "")
        assert "Transaction replay detected with conflicting data" in error_detail, f"Expected specific error message, got: {error_detail}"
        
        print("✓ Replay attack correctly detected and returns 409 with proper message")


class TestKeyRegistry:
    """Test key registry persistence"""
    
    def test_get_all_keys(self):
        """GET /api/public/keys returns all keys from DB"""
        response = requests.get(f"{BASE_URL}/api/public/keys")
        assert response.status_code == 200, f"Failed to get keys: {response.text}"
        
        data = response.json()
        assert "keys" in data
        assert "total" in data
        assert "active_count" in data
        assert "retired_count" in data
        
        # Should have at least one key
        assert data["total"] >= 1, "Expected at least one key in registry"
        assert len(data["keys"]) >= 1
        
        # Validate key structure
        key = data["keys"][0]
        assert "public_key_id" in key
        assert "public_key" in key
        assert "algorithm" in key
        assert key["algorithm"] == "Ed25519"
        assert "status" in key
        assert key["status"] in ["active", "retired"]
        assert "created_at" in key
        
        print(f"✓ Key registry returns {data['total']} keys ({data['active_count']} active, {data['retired_count']} retired)")
    
    def test_key_registry_persistence(self):
        """Verify key is stored in MongoDB and can be fetched"""
        # Get keys twice to verify persistence
        response1 = requests.get(f"{BASE_URL}/api/public/keys")
        assert response1.status_code == 200
        keys1 = response1.json()["keys"]
        
        response2 = requests.get(f"{BASE_URL}/api/public/keys")
        assert response2.status_code == 200
        keys2 = response2.json()["keys"]
        
        # Keys should be the same (persistent)
        assert len(keys1) == len(keys2), "Key count changed between requests"
        
        # Verify key IDs match
        key_ids1 = {k["public_key_id"] for k in keys1}
        key_ids2 = {k["public_key_id"] for k in keys2}
        assert key_ids1 == key_ids2, "Key IDs changed between requests"
        
        print("✓ Key registry persistence verified")


class TestPublicVerification:
    """Test public verification endpoint"""
    
    @pytest.fixture(scope="class")
    def api_key(self):
        """Get API key from /api/config"""
        response = requests.get(f"{BASE_URL}/api/config")
        return response.json()["test_api_key"]
    
    @pytest.fixture(scope="class")
    def generated_fea(self, api_key):
        """Generate an FEA for verification tests"""
        unique_id = str(uuid.uuid4())
        payload = {
            "idempotency_key": f"TEST_verify_{unique_id}",
            "transaction_id": f"TEST_txn_verify_{unique_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": 25000,
            "currency": "GBP",
            "payer_id": "payer_verify",
            "payee_id": "payee_verify"
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/fea/generate", json=payload, headers=headers)
        assert response.status_code == 200
        return response.json()
    
    def test_public_verify_existing_fea(self, generated_fea):
        """GET /api/public/verify/{fea_id} uses DB-backed key resolution"""
        fea_id = generated_fea["fea_id"]
        
        response = requests.get(f"{BASE_URL}/api/public/verify/{fea_id}")
        assert response.status_code == 200, f"Public verify failed: {response.text}"
        
        data = response.json()
        assert data["fea_id"] == fea_id
        assert data["signature_valid"] == True, f"Signature should be valid, got: {data}"
        assert "fea_payload" in data
        assert "signature" in data
        assert "signature_version" in data
        assert "issuer_id" in data
        assert "created_at" in data
        
        print(f"✓ Public verification successful for FEA {fea_id}")
    
    def test_public_verify_nonexistent_fea(self):
        """GET /api/public/verify/{fea_id} returns 404 for non-existent FEA"""
        fake_fea_id = str(uuid.uuid4())
        
        response = requests.get(f"{BASE_URL}/api/public/verify/{fake_fea_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        error_detail = response.json().get("detail", "")
        assert "FEA not found" in error_detail, f"Expected 'FEA not found' in error, got: {error_detail}"
        
        print("✓ Non-existent FEA correctly returns 404")


class TestAPIVerification:
    """Test API verification endpoint (POST /api/fea/verify)"""
    
    @pytest.fixture(scope="class")
    def api_key(self):
        """Get API key from /api/config"""
        response = requests.get(f"{BASE_URL}/api/config")
        return response.json()["test_api_key"]
    
    @pytest.fixture(scope="class")
    def generated_fea(self, api_key):
        """Generate an FEA for verification tests"""
        unique_id = str(uuid.uuid4())
        payload = {
            "idempotency_key": f"TEST_api_verify_{unique_id}",
            "transaction_id": f"TEST_txn_api_verify_{unique_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": 50000,
            "currency": "JPY",
            "payer_id": "payer_api_verify",
            "payee_id": "payee_api_verify"
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/fea/generate", json=payload, headers=headers)
        assert response.status_code == 200
        return response.json()
    
    def test_api_verify_valid_signature(self, api_key, generated_fea):
        """POST /api/fea/verify uses DB-backed key resolution"""
        verify_payload = {
            "fea_payload": generated_fea["fea_payload"],
            "signature": generated_fea["signature"],
            "signature_version": generated_fea["signature_version"]
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/fea/verify", json=verify_payload, headers=headers)
        
        assert response.status_code == 200, f"API verify failed: {response.text}"
        data = response.json()
        
        assert data["valid"] == True, f"Signature should be valid, got: {data}"
        assert "reason" in data
        assert "signature_version" in data
        assert data["signature_version"] == "v2"
        assert "verified_at" in data
        
        print("✓ API verification successful with valid signature")
    
    def test_api_verify_invalid_signature(self, api_key, generated_fea):
        """POST /api/fea/verify returns invalid for tampered signature"""
        # Tamper with the signature
        import base64
        original_sig = generated_fea["signature"]
        sig_bytes = base64.b64decode(original_sig)
        # Flip some bits
        tampered_bytes = bytes([b ^ 0xFF for b in sig_bytes[:8]]) + sig_bytes[8:]
        tampered_sig = base64.b64encode(tampered_bytes).decode()
        
        verify_payload = {
            "fea_payload": generated_fea["fea_payload"],
            "signature": tampered_sig,
            "signature_version": generated_fea["signature_version"]
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/fea/verify", json=verify_payload, headers=headers)
        
        assert response.status_code == 200, f"API verify request failed: {response.text}"
        data = response.json()
        
        assert data["valid"] == False, f"Tampered signature should be invalid, got: {data}"
        
        print("✓ API verification correctly rejects invalid signature")
    
    def test_api_verify_requires_api_key(self, generated_fea):
        """POST /api/fea/verify requires API key"""
        verify_payload = {
            "fea_payload": generated_fea["fea_payload"],
            "signature": generated_fea["signature"],
            "signature_version": generated_fea["signature_version"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/fea/verify",
            json=verify_payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ API verification correctly requires API key")


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.fixture(scope="class")
    def api_key(self):
        """Get API key from /api/config"""
        response = requests.get(f"{BASE_URL}/api/config")
        return response.json()["test_api_key"]
    
    def test_generate_fea_empty_idempotency_key(self, api_key):
        """Empty idempotency_key should return 400/422"""
        payload = {
            "idempotency_key": "",  # Empty
            "transaction_id": "test_txn",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": 1000,
            "currency": "INR",
            "payer_id": "payer",
            "payee_id": "payee"
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/fea/generate", json=payload, headers=headers)
        
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Empty idempotency_key correctly rejected")
    
    def test_generate_fea_invalid_currency(self, api_key):
        """Invalid currency (not 3 chars) should return 400/422"""
        unique_id = str(uuid.uuid4())
        payload = {
            "idempotency_key": f"TEST_invalid_curr_{unique_id}",
            "transaction_id": f"TEST_txn_invalid_curr_{unique_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": 1000,
            "currency": "INVALID",  # Too long
            "payer_id": "payer",
            "payee_id": "payee"
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/fea/generate", json=payload, headers=headers)
        
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Invalid currency correctly rejected")
    
    def test_generate_fea_negative_amount(self, api_key):
        """Negative amount should return 400/422"""
        unique_id = str(uuid.uuid4())
        payload = {
            "idempotency_key": f"TEST_neg_amount_{unique_id}",
            "transaction_id": f"TEST_txn_neg_amount_{unique_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": -100,  # Negative
            "currency": "INR",
            "payer_id": "payer",
            "payee_id": "payee"
        }
        
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/fea/generate", json=payload, headers=headers)
        
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Negative amount correctly rejected")


# Cleanup fixture to remove test data
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed data after all tests complete"""
    yield
    # Note: In production, you'd want to clean up test data
    # For now, we leave it as the collection was already cleaned
    print("\n✓ Test session complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
