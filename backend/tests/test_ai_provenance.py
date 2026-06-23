"""Unit tests for Trust Layer 2 — AI Provenance & Accountability (Phase 2).

Server-independent: exercises the envelope signing/verification + service logic
directly, including detached binding, tamper detection, privacy (hash-only)
enforcement, oversight/agent-chain summarization and backward compatibility.
"""
import base64
import os

# Load backend/.env so core.config (which requires MONGO_URL/DB_NAME) imports.
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(_env_path):
    for _line in open(_env_path):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v.strip().strip('"'))

os.environ.setdefault("ENABLE_AI_PROVENANCE", "true")

import asyncio

import pytest

from core.ai_provenance import sign_envelope, content_hash_of, verify_binding_signature
from models.ai_provenance import (
    AttachProvenanceRequest, AIIdentity, AIProvenanceMeta, OversightEvent, AgentStep,
)
from services import ai_provenance_service as svc

DIGEST = "a" * 64
H = "b" * 64


def _prod_pubkey():
    from core.kms import get_kms
    return get_kms().get_public_key_bytes("production", "Ed25519")


def test_sign_and_verify_binding_roundtrip():
    content = {"ai_identity": {"provider": "acme-ai", "model_name": "x1"}}
    env = sign_envelope(DIGEST, content)
    assert env["fea_hash"] == DIGEST
    assert env["content_hash"] == content_hash_of(content)
    assert env["binding"]["alg"] == "Ed25519"
    assert verify_binding_signature(env, _prod_pubkey()) is True


def test_tampered_content_breaks_content_integrity():
    content = {"provenance": {"output_hash": H}}
    env = sign_envelope(DIGEST, content)
    # Tamper the content after signing
    env["content"]["provenance"]["output_hash"] = "c" * 64
    fea_doc = {"fea_payload": {"fea_hash": DIGEST}, "ai_provenance": env}

    async def _pub(_kid):
        return _prod_pubkey()

    import services.key_service as ks
    orig = ks.get_public_key_bytes_by_id
    ks.get_public_key_bytes_by_id = _pub
    try:
        res = asyncio.get_event_loop().run_until_complete(svc.verify_ai_provenance(fea_doc))
    finally:
        ks.get_public_key_bytes_by_id = orig
    assert res["present"] is True
    assert res["content_integrity"] is False
    assert res["valid"] is False


def test_envelope_not_bound_to_other_proof():
    content = {"ai_identity": {"provider": "acme"}}
    env = sign_envelope(DIGEST, content)
    # Different proof fea_hash -> bound_to_proof must be False
    fea_doc = {"fea_payload": {"fea_hash": "d" * 64}, "ai_provenance": env}

    async def _pub(_kid):
        return _prod_pubkey()

    import services.key_service as ks
    orig = ks.get_public_key_bytes_by_id
    ks.get_public_key_bytes_by_id = _pub
    try:
        res = asyncio.get_event_loop().run_until_complete(svc.verify_ai_provenance(fea_doc))
    finally:
        ks.get_public_key_bytes_by_id = orig
    assert res["bound_to_proof"] is False
    assert res["valid"] is False


def test_hash_only_privacy_enforced():
    # raw (non-hex) content must be rejected at the model boundary
    with pytest.raises(Exception):
        AIProvenanceMeta(prompt_hash="this is a raw prompt, not a hash")
    with pytest.raises(Exception):
        OversightEvent(event_type="approval", note_hash="literal note text")
    # valid hash accepted + lowercased
    m = AIProvenanceMeta(prompt_hash="AB" * 32)
    assert m.prompt_hash == "ab" * 32


def test_event_type_normalization():
    assert OversightEvent(event_type="Human Review").event_type == "review"
    assert OversightEvent(event_type="approved").event_type == "approval"
    assert OversightEvent(event_type="ESCALATED").event_type == "escalation"
    with pytest.raises(Exception):
        OversightEvent(event_type="banana")


def test_summary_human_chain_and_multi_agent():
    req = AttachProvenanceRequest(
        ai_identity=AIIdentity(provider="acme-ai", model_name="m", agent_role="drafter"),
        provenance=AIProvenanceMeta(workflow_id="wf-1", output_hash=H, session_id="s1"),
        oversight_events=[
            OversightEvent(event_type="review", actor_role="analyst"),
            OversightEvent(event_type="approval", actor_role="manager"),
        ],
        agent_chain=[
            AgentStep(agent_identifier="agent-b", sequence=2, outcome="handoff", handoff_to="human"),
            AgentStep(agent_identifier="agent-a", sequence=1, outcome="drafted", handoff_to="agent-b"),
        ],
    )
    content = svc._build_content(req)
    # agent_chain sorted by sequence deterministically
    assert [a["sequence"] for a in content["agent_chain"]] == [1, 2]
    summary = svc._summarize(content)
    assert summary["ai_identity_present"] is True
    assert summary["workflow_id"] == "wf-1"
    assert summary["human_reviewed"] is True
    assert summary["human_approved"] is True
    assert summary["human_rejected"] is False
    assert summary["multi_agent"] is True
    assert summary["agent_chain_length"] == 2
    assert [a["event_type"] for a in summary["approval_chain"]] == ["review", "approval"]


def test_no_envelope_returns_none():
    res = asyncio.get_event_loop().run_until_complete(
        svc.verify_ai_provenance({"fea_payload": {"fea_hash": DIGEST}})
    )
    assert res is None


def test_build_content_empty_when_all_blank():
    req = AttachProvenanceRequest()
    assert svc._build_content(req) == {}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
