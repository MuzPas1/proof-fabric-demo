"""E2E backend tests for Trust Layer 2 Phase 1 — Independent Time Attestation.

Validates:
 - Backward compatibility of /api/fea/generate and /api/public/verify
 - Detached anchoring (POST /api/fea/{fea_id}/anchor) — signature byte-identical
 - Time attestation surfaced on public verify
 - Idempotent anchoring
 - Backdating cutoff defense WITH continuity (signature_valid stays true)
 - Feature flag ENABLE_TIME_ANCHOR active
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pfp-trust-statement.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASS = "PfpAdmin!6WJb8Y0_8IV3ci2jIPG23DsT"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def api_key(session) -> str:
    r = session.post(f"{BASE_URL}/api/demo/sandbox-key", json={})
    assert r.status_code == 200, f"sandbox-key failed: {r.status_code} {r.text}"
    data = r.json()
    key = data.get("api_key")
    assert key, f"no api_key in response: {data}"
    return key


@pytest.fixture(scope="module")
def admin_jwt(session) -> str:
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in: {r.json()}"
    return tok


def _make_fea(session, api_key) -> dict:
    body = {
        "idempotency_key": f"TEST_ta_{uuid.uuid4().hex}",
        "transaction_id": f"TEST_tx_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "amount": 12345,
        "currency": "USD",
        "payer_id": "TEST_payer",
        "payee_id": "TEST_payee",
    }
    r = session.post(
        f"{BASE_URL}/api/fea/generate",
        json=body,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )
    assert r.status_code == 200, f"generate failed: {r.status_code} {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestBackwardCompatibility:
    """Existing flow unaffected when proof is not anchored."""

    def test_generate_and_public_verify_unanchored(self, session, api_key):
        fea = _make_fea(session, api_key)
        fea_id = fea["fea_id"]
        assert isinstance(fea["signature"], str) and len(fea["signature"]) > 0

        r = session.get(f"{BASE_URL}/api/public/verify/{fea_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["fea_id"] == fea_id
        assert data["signature_valid"] is True
        # time_attestation must be absent/null for non-anchored proof
        assert data.get("time_attestation") in (None, {}), f"unexpected: {data.get('time_attestation')}"


class TestAnchoring:
    """Detached anchoring — signature byte-identical, idempotent, surfaced on verify."""

    def test_anchor_preserves_signature_and_id(self, session, api_key):
        fea = _make_fea(session, api_key)
        fea_id = fea["fea_id"]
        sig_before = fea["signature"]

        r = session.post(
            f"{BASE_URL}/api/fea/{fea_id}/anchor",
            headers={"X-API-Key": api_key},
        )
        assert r.status_code == 200, f"anchor failed: {r.status_code} {r.text}"
        body = r.json()
        assert body["fea_id"] == fea_id
        env = body["time_anchor"]
        assert env["anchors"][0]["type"] == "local"
        assert env["anchors"][0]["digest"]  # binds fea_hash

        # Re-fetch the proof — signature MUST be byte-identical and id unchanged.
        r2 = session.get(f"{BASE_URL}/api/public/verify/{fea_id}")
        assert r2.status_code == 200
        v = r2.json()
        assert v["fea_id"] == fea_id
        assert v["signature"] == sig_before, "signature CHANGED after anchoring (must be byte-identical)"
        assert v["signature_valid"] is True

        ta = v["time_attestation"]
        assert ta is not None and ta["present"] is True
        assert ta["valid"] is True
        assert ta["tier"] == "signed+timestamped(local)"
        assert ta["attested_time"]
        assert ta["key_cutoff_ok"] is True
        assert ta["anchors"][0]["valid"] is True

    def test_idempotent_anchor(self, session, api_key):
        fea = _make_fea(session, api_key)
        fea_id = fea["fea_id"]
        r1 = session.post(f"{BASE_URL}/api/fea/{fea_id}/anchor", headers={"X-API-Key": api_key})
        r2 = session.post(f"{BASE_URL}/api/fea/{fea_id}/anchor", headers={"X-API-Key": api_key})
        assert r1.status_code == 200 and r2.status_code == 200
        env1 = r1.json()["time_anchor"]
        env2 = r2.json()["time_anchor"]
        # gen_time on the underlying anchor must be identical
        assert env1["anchors"][0]["gen_time"] == env2["anchors"][0]["gen_time"]
        assert env1["anchors"][0]["token"] == env2["anchors"][0]["token"]


class TestBackdatingCutoffWithContinuity:
    """Setting a past not_after must NOT break signature_valid (retire-not-revoke
    + continuity preserved); only time_attestation.key_cutoff_ok flips to False."""

    def test_cutoff_does_not_break_signature(self, session, api_key, admin_jwt):
        # Use a dedicated proof so we don't break shared state.
        fea = _make_fea(session, api_key)
        fea_id = fea["fea_id"]
        kid = fea["public_key_id"]

        # Anchor it
        r = session.post(f"{BASE_URL}/api/fea/{fea_id}/anchor", headers={"X-API-Key": api_key})
        assert r.status_code == 200, r.text

        # Pre-condition: verify works
        v0 = session.get(f"{BASE_URL}/api/public/verify/{fea_id}").json()
        assert v0["signature_valid"] is True
        assert v0["time_attestation"]["valid"] is True

        # Retire the key with not_after = 1 day in the past
        past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r_ret = session.post(
            f"{BASE_URL}/api/admin/keys/retire",
            params={"public_key_id": kid, "not_after": past},
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        assert r_ret.status_code == 200, f"retire failed: {r_ret.status_code} {r_ret.text}"
        assert r_ret.json().get("time_anchor_cutoff") == past

        # After retiring with past cutoff: signature_valid must still be true
        v = session.get(f"{BASE_URL}/api/public/verify/{fea_id}").json()
        assert v["signature_valid"] is True, (
            f"CONTINUITY BROKEN: signature_valid flipped to False after key retire+cutoff. "
            f"reason={v.get('reason')}"
        )
        ta = v["time_attestation"]
        assert ta is not None
        assert ta["key_cutoff_ok"] is False
        assert ta["valid"] is False
        assert ta["tier"] == "signed"
        assert "backdat" in (ta.get("cutoff_reason") or "").lower()


class TestFeatureFlagAndProvider:
    def test_anchor_endpoint_enabled_in_preview(self, session, api_key):
        # If the flag were off, the anchor route would 404. Use a fresh fea.
        fea = _make_fea(session, api_key)
        r = session.post(
            f"{BASE_URL}/api/fea/{fea['fea_id']}/anchor",
            headers={"X-API-Key": api_key},
        )
        assert r.status_code == 200
        env = r.json()["time_anchor"]
        tsa_name = env["anchors"][0].get("tsa_name", "")
        # Honestly-labelled local provider in preview
        assert "DEV/TEST" in tsa_name or "Local" in tsa_name


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
