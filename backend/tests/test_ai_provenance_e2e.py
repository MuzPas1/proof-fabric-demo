"""E2E backend tests for Trust Layer 2 Phase 2 — AI Provenance & Accountability.

Validates against the live preview backend:
 - Backward compatibility (proof without provenance verifies; ai_provenance absent)
 - Detached attach (POST /api/fea/{id}/provenance) — signature byte-identical, fea_id unchanged
 - Provenance surfaced & independently verified on /api/public/verify
 - Human oversight + multi-agent chain summarized correctly
 - Privacy: raw (non-hash) content rejected with 4xx
 - Idempotent / write-once attach
 - Feature flag ENABLE_AI_PROVENANCE active
"""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://fea-gateway.preview.emergentagent.com"
).rstrip("/")


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture(scope="module")
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def api_key(session) -> str:
    r = session.post(f"{BASE_URL}/api/demo/sandbox-key", json={})
    assert r.status_code == 200, f"sandbox-key failed: {r.status_code} {r.text}"
    key = r.json().get("api_key")
    assert key
    return key


def _make_fea(session, api_key) -> dict:
    body = {
        "idempotency_key": f"TEST_prov_{uuid.uuid4().hex}",
        "transaction_id": f"TEST_tx_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "amount": 5000,
        "currency": "USD",
        "payer_id": "TEST_payer",
        "payee_id": "TEST_payee",
    }
    r = session.post(
        f"{BASE_URL}/api/fea/generate", json=body,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )
    assert r.status_code == 200, f"generate failed: {r.status_code} {r.text}"
    return r.json()


def _full_provenance_body() -> dict:
    return {
        "ai_identity": {
            "provider": "acme-ai",
            "model_name": "atlas",
            "model_version": "3.1",
            "model_family": "atlas",
            "agent_identifier": "agent-drafter-01",
            "agent_role": "drafter",
            "execution_environment": "prod-eu",
        },
        "provenance": {
            "prompt_hash": _h("the prompt"),
            "system_prompt_hash": _h("system prompt"),
            "input_hash": _h("input"),
            "output_hash": _h("output"),
            "context_hash": _h("context"),
            "workflow_id": "wf-invoice-approval",
            "session_id": "sess-123",
            "correlation_id": "corr-999",
        },
        "oversight_events": [
            {"event_type": "review", "actor_role": "analyst", "actor_id": _h("alice")},
            {"event_type": "approval", "actor_role": "manager", "actor_id": _h("bob")},
        ],
        "agent_chain": [
            {"agent_identifier": "agent-a", "agent_role": "drafter", "sequence": 1, "outcome": "drafted", "handoff_to": "agent-b"},
            {"agent_identifier": "agent-b", "agent_role": "checker", "sequence": 2, "outcome": "validated", "handoff_to": "human"},
        ],
    }


class TestBackwardCompatibility:
    def test_unprovenanced_proof_verifies(self, session, api_key):
        fea = _make_fea(session, api_key)
        r = session.get(f"{BASE_URL}/api/public/verify/{fea['fea_id']}")
        assert r.status_code == 200
        data = r.json()
        assert data["signature_valid"] is True
        assert data.get("ai_provenance") in (None, {}), data.get("ai_provenance")


class TestAttachAndVerify:
    def test_attach_preserves_signature_and_surfaces_provenance(self, session, api_key):
        fea = _make_fea(session, api_key)
        fea_id = fea["fea_id"]
        sig_before = fea["signature"]

        r = session.post(
            f"{BASE_URL}/api/fea/{fea_id}/provenance",
            json=_full_provenance_body(),
            headers={"X-API-Key": api_key},
        )
        assert r.status_code == 200, f"attach failed: {r.status_code} {r.text}"
        env = r.json()["ai_provenance"]
        assert env["binding"]["alg"] == "Ed25519"
        assert env["fea_hash"]

        v = session.get(f"{BASE_URL}/api/public/verify/{fea_id}").json()
        assert v["fea_id"] == fea_id
        assert v["signature"] == sig_before, "signature CHANGED after provenance attach"
        assert v["signature_valid"] is True

        ap = v["ai_provenance"]
        assert ap is not None and ap["present"] is True
        assert ap["valid"] is True
        assert ap["content_integrity"] is True
        assert ap["bound_to_proof"] is True
        assert ap["signature_valid"] is True
        # accountability facts independently confirmed
        assert ap["ai_identity"]["provider"] == "acme-ai"
        assert ap["workflow_id"] == "wf-invoice-approval"
        assert ap["human_reviewed"] is True
        assert ap["human_approved"] is True
        assert ap["human_rejected"] is False
        assert ap["multi_agent"] is True
        assert ap["agent_chain_length"] == 2
        # privacy: no raw content present, only hashes
        assert set(ap["provenance_hashes"].keys()) <= {
            "prompt_hash", "system_prompt_hash", "input_hash", "output_hash", "context_hash"
        }

    def test_idempotent_attach(self, session, api_key):
        fea = _make_fea(session, api_key)
        fea_id = fea["fea_id"]
        b = {"ai_identity": {"provider": "acme-ai", "model_name": "atlas"}}
        r1 = session.post(f"{BASE_URL}/api/fea/{fea_id}/provenance", json=b, headers={"X-API-Key": api_key})
        r2 = session.post(f"{BASE_URL}/api/fea/{fea_id}/provenance", json={"ai_identity": {"provider": "other"}}, headers={"X-API-Key": api_key})
        assert r1.status_code == 200 and r2.status_code == 200
        # write-once: second call returns the original envelope (signature identical)
        assert r1.json()["ai_provenance"]["binding"]["signature"] == r2.json()["ai_provenance"]["binding"]["signature"]


class TestPrivacy:
    def test_raw_content_rejected(self, session, api_key):
        fea = _make_fea(session, api_key)
        r = session.post(
            f"{BASE_URL}/api/fea/{fea['fea_id']}/provenance",
            json={"provenance": {"prompt_hash": "this is a raw prompt not a hash"}},
            headers={"X-API-Key": api_key},
        )
        assert r.status_code in (400, 422), f"raw content should be rejected, got {r.status_code} {r.text}"

    def test_empty_provenance_rejected(self, session, api_key):
        fea = _make_fea(session, api_key)
        r = session.post(
            f"{BASE_URL}/api/fea/{fea['fea_id']}/provenance",
            json={},
            headers={"X-API-Key": api_key},
        )
        assert r.status_code == 400, f"empty provenance should be 400, got {r.status_code} {r.text}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
