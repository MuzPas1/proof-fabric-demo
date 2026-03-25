#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Proof Fabric Protocol (PFP)
Tests all endpoints including authentication, FEA generation, verification, and public endpoints.
"""
import requests
import json
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# External URL from frontend/.env
BASE_URL = "https://fea-verify-engine.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"

class PFPAPITester:
    def __init__(self):
        self.api_key = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })
    
    def test_api_health(self) -> bool:
        """Test API health check endpoint"""
        try:
            response = requests.get(f"{API_URL}/", timeout=10)
            success = response.status_code == 200
            data = response.json() if success else {}
            
            if success and "status" in data and data["status"] == "operational":
                self.log_test("API Health Check", True)
                return True
            else:
                self.log_test("API Health Check", False, f"Status: {response.status_code}, Data: {data}")
                return False
        except Exception as e:
            self.log_test("API Health Check", False, str(e))
            return False
    
    def test_get_config(self) -> bool:
        """Test config endpoint and get test API key"""
        try:
            response = requests.get(f"{API_URL}/config", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                if "test_api_key" in data:
                    self.api_key = data["test_api_key"]
                    self.log_test("Get Config & API Key", True, f"API Key: {self.api_key[:20]}...")
                    return True
                else:
                    self.log_test("Get Config & API Key", False, "No test_api_key in response")
                    return False
            else:
                self.log_test("Get Config & API Key", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Get Config & API Key", False, str(e))
            return False
    
    def test_public_keys(self) -> bool:
        """Test public key registry endpoint"""
        try:
            response = requests.get(f"{API_URL}/public/keys", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                if "keys" in data:
                    self.log_test("Public Key Registry", True, f"Found {len(data['keys'])} keys")
                    return True
                else:
                    self.log_test("Public Key Registry", False, "No keys field in response")
                    return False
            else:
                self.log_test("Public Key Registry", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Public Key Registry", False, str(e))
            return False
    
    def test_fea_generation(self) -> Optional[Dict[str, Any]]:
        """Test FEA generation with valid payload"""
        if not self.api_key:
            self.log_test("FEA Generation", False, "No API key available")
            return None
        
        try:
            payload = {
                "idempotency_key": f"test_idem_{int(time.time())}",
                "transaction_id": f"test_txn_{int(time.time())}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "amount": 10000,
                "currency": "INR",
                "payer_id": "test_payer_hash_123",
                "payee_id": "test_payee_hash_456",
                "metadata": {"test": "data", "ref": "TEST-001"}
            }
            
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(f"{API_URL}/fea/generate", json=payload, headers=headers, timeout=15)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                required_fields = ["fea_id", "fea_hash", "signature", "public_key_id", "fea_payload"]
                if all(field in data for field in required_fields):
                    self.log_test("FEA Generation", True, f"FEA ID: {data['fea_id']}")
                    return data
                else:
                    missing = [f for f in required_fields if f not in data]
                    self.log_test("FEA Generation", False, f"Missing fields: {missing}")
                    return None
            else:
                error_detail = response.json().get("detail", "Unknown error") if response.content else "No response"
                self.log_test("FEA Generation", False, f"Status: {response.status_code}, Error: {error_detail}")
                return None
        except Exception as e:
            self.log_test("FEA Generation", False, str(e))
            return None
    
    def test_fea_idempotency_same_payload(self, original_fea: Dict[str, Any]) -> bool:
        """Test FEA generation idempotency - same key + same payload returns same FEA"""
        if not self.api_key or not original_fea:
            self.log_test("FEA Idempotency (Same Payload)", False, "Prerequisites not met")
            return False
        
        try:
            # Use same payload as original
            payload = {
                "idempotency_key": "test_idem_same",
                "transaction_id": "test_txn_same",
                "timestamp": "2024-01-15T10:30:00Z",
                "amount": 10000,
                "currency": "INR",
                "payer_id": "test_payer_same",
                "payee_id": "test_payee_same"
            }
            
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            # First request
            response1 = requests.post(f"{API_URL}/fea/generate", json=payload, headers=headers, timeout=15)
            if response1.status_code != 200:
                self.log_test("FEA Idempotency (Same Payload)", False, f"First request failed: {response1.status_code}")
                return False
            
            fea1 = response1.json()
            
            # Second request with same payload
            response2 = requests.post(f"{API_URL}/fea/generate", json=payload, headers=headers, timeout=15)
            if response2.status_code != 200:
                self.log_test("FEA Idempotency (Same Payload)", False, f"Second request failed: {response2.status_code}")
                return False
            
            fea2 = response2.json()
            
            # Should return same FEA
            if fea1["fea_id"] == fea2["fea_id"] and fea1["fea_hash"] == fea2["fea_hash"]:
                self.log_test("FEA Idempotency (Same Payload)", True, "Same FEA returned")
                return True
            else:
                self.log_test("FEA Idempotency (Same Payload)", False, "Different FEAs returned")
                return False
        except Exception as e:
            self.log_test("FEA Idempotency (Same Payload)", False, str(e))
            return False
    
    def test_fea_idempotency_different_payload(self) -> bool:
        """Test FEA generation idempotency conflict - same key + different payload rejected"""
        if not self.api_key:
            self.log_test("FEA Idempotency (Different Payload)", False, "No API key available")
            return False
        
        try:
            idempotency_key = f"test_conflict_{int(time.time())}"
            
            # First payload
            payload1 = {
                "idempotency_key": idempotency_key,
                "transaction_id": "test_txn_conflict_1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "amount": 10000,
                "currency": "INR",
                "payer_id": "test_payer_conflict",
                "payee_id": "test_payee_conflict"
            }
            
            # Second payload with same idempotency key but different data
            payload2 = {
                "idempotency_key": idempotency_key,
                "transaction_id": "test_txn_conflict_2",  # Different transaction ID
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "amount": 20000,  # Different amount
                "currency": "USD",  # Different currency
                "payer_id": "test_payer_conflict",
                "payee_id": "test_payee_conflict"
            }
            
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            # First request should succeed
            response1 = requests.post(f"{API_URL}/fea/generate", json=payload1, headers=headers, timeout=15)
            if response1.status_code != 200:
                self.log_test("FEA Idempotency (Different Payload)", False, f"First request failed: {response1.status_code}")
                return False
            
            # Second request should fail with 409 Conflict
            response2 = requests.post(f"{API_URL}/fea/generate", json=payload2, headers=headers, timeout=15)
            if response2.status_code == 409:
                self.log_test("FEA Idempotency (Different Payload)", True, "Conflict detected correctly")
                return True
            else:
                self.log_test("FEA Idempotency (Different Payload)", False, f"Expected 409, got {response2.status_code}")
                return False
        except Exception as e:
            self.log_test("FEA Idempotency (Different Payload)", False, str(e))
            return False
    
    def test_fea_verification_valid(self, fea_data: Dict[str, Any]) -> bool:
        """Test FEA verification with valid payload and signature"""
        if not self.api_key or not fea_data:
            self.log_test("FEA Verification (Valid)", False, "Prerequisites not met")
            return False
        
        try:
            payload = {
                "fea_payload": fea_data["fea_payload"],
                "signature": fea_data["signature"]
            }
            
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(f"{API_URL}/fea/verify", json=payload, headers=headers, timeout=15)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                if data.get("valid") is True:
                    self.log_test("FEA Verification (Valid)", True, "Signature verified")
                    return True
                else:
                    self.log_test("FEA Verification (Valid)", False, f"Verification failed: {data.get('reason')}")
                    return False
            else:
                self.log_test("FEA Verification (Valid)", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("FEA Verification (Valid)", False, str(e))
            return False
    
    def test_fea_verification_invalid(self, fea_data: Dict[str, Any]) -> bool:
        """Test FEA verification with invalid signature"""
        if not self.api_key or not fea_data:
            self.log_test("FEA Verification (Invalid)", False, "Prerequisites not met")
            return False
        
        try:
            # Tamper with signature
            invalid_signature = "invalid_signature_base64_data"
            
            payload = {
                "fea_payload": fea_data["fea_payload"],
                "signature": invalid_signature
            }
            
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(f"{API_URL}/fea/verify", json=payload, headers=headers, timeout=15)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                if data.get("valid") is False:
                    self.log_test("FEA Verification (Invalid)", True, "Invalid signature detected")
                    return True
                else:
                    self.log_test("FEA Verification (Invalid)", False, "Should have failed verification")
                    return False
            else:
                self.log_test("FEA Verification (Invalid)", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("FEA Verification (Invalid)", False, str(e))
            return False
    
    def test_public_verification_valid(self, fea_data: Dict[str, Any]) -> bool:
        """Test public verification by FEA ID"""
        if not fea_data:
            self.log_test("Public Verification (Valid)", False, "No FEA data available")
            return False
        
        try:
            fea_id = fea_data["fea_id"]
            response = requests.get(f"{API_URL}/public/verify/{fea_id}", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                required_fields = ["fea_hash", "signature_valid", "timestamp", "issuer_id"]
                if all(field in data for field in required_fields):
                    self.log_test("Public Verification (Valid)", True, f"Signature valid: {data['signature_valid']}")
                    return True
                else:
                    missing = [f for f in required_fields if f not in data]
                    self.log_test("Public Verification (Valid)", False, f"Missing fields: {missing}")
                    return False
            else:
                self.log_test("Public Verification (Valid)", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Public Verification (Valid)", False, str(e))
            return False
    
    def test_public_verification_not_found(self) -> bool:
        """Test public verification for non-existent FEA returns 404"""
        try:
            fake_fea_id = "non-existent-fea-id-12345"
            response = requests.get(f"{API_URL}/public/verify/{fake_fea_id}", timeout=10)
            
            if response.status_code == 404:
                self.log_test("Public Verification (Not Found)", True, "404 returned correctly")
                return True
            else:
                self.log_test("Public Verification (Not Found)", False, f"Expected 404, got {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Public Verification (Not Found)", False, str(e))
            return False
    
    def test_api_key_authentication(self) -> bool:
        """Test API key authentication - missing key returns 401"""
        try:
            payload = {
                "idempotency_key": "test_auth",
                "transaction_id": "test_auth_txn",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "amount": 1000,
                "currency": "INR",
                "payer_id": "test_payer",
                "payee_id": "test_payee"
            }
            
            # Request without API key
            response = requests.post(f"{API_URL}/fea/generate", json=payload, timeout=10)
            
            if response.status_code == 401:
                self.log_test("API Key Authentication", True, "401 returned for missing key")
                return True
            else:
                self.log_test("API Key Authentication", False, f"Expected 401, got {response.status_code}")
                return False
        except Exception as e:
            self.log_test("API Key Authentication", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting PFP API Tests...")
        print(f"📍 Testing against: {BASE_URL}")
        print("=" * 60)
        
        # Basic connectivity tests
        if not self.test_api_health():
            print("❌ API health check failed. Stopping tests.")
            return False
        
        if not self.test_get_config():
            print("❌ Config endpoint failed. Stopping tests.")
            return False
        
        # Public endpoints
        self.test_public_keys()
        
        # Authentication test
        self.test_api_key_authentication()
        
        # FEA generation and verification
        fea_data = self.test_fea_generation()
        
        if fea_data:
            # Idempotency tests
            self.test_fea_idempotency_same_payload(fea_data)
            self.test_fea_idempotency_different_payload()
            
            # Verification tests
            self.test_fea_verification_valid(fea_data)
            self.test_fea_verification_invalid(fea_data)
            self.test_public_verification_valid(fea_data)
        
        # Public verification edge case
        self.test_public_verification_not_found()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print("⚠️  Some tests failed. Check details above.")
            return False

def main():
    """Main test runner"""
    tester = PFPAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "total_tests": tester.tests_run,
        "passed_tests": tester.tests_passed,
        "success_rate": f"{(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "0%",
        "test_details": tester.test_results
    }
    
    with open("/app/backend_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())