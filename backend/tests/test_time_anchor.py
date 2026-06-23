"""Unit tests for Trust Layer 2 — Independent Time Attestation (local provider).

Server-independent: exercises the provider + service verification logic directly,
including the detached-binding and backdating-cutoff defenses.
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

# Ensure required env for the local provider before importing settings.
os.environ.setdefault("ENABLE_TIME_ANCHOR", "true")
os.environ.setdefault("TIME_ANCHOR_PROVIDER", "local")
os.environ.setdefault("TIME_ANCHOR_LOCAL_SEED", base64.b64encode(b"\x01" * 32).decode())

import asyncio
import pytest

from core.time_anchor import get_time_anchor_provider, provider_for_anchor


DIGEST = "a" * 64


def test_local_anchor_and_verify_roundtrip():
    p = get_time_anchor_provider("local")
    anchor = p.anchor(DIGEST)
    assert anchor["type"] == "local"
    assert anchor["digest"] == DIGEST
    res = provider_for_anchor(anchor).verify(anchor, DIGEST)
    assert res["valid"] is True
    assert res["gen_time"]
    assert res["independent"] is False if "independent" in res else True


def test_local_anchor_binding_rejects_wrong_digest():
    p = get_time_anchor_provider("local")
    anchor = p.anchor(DIGEST)
    res = provider_for_anchor(anchor).verify(anchor, "b" * 64)
    assert res["valid"] is False
    assert "digest mismatch" in (res["error"] or "").lower()


def test_local_anchor_detects_token_tamper():
    p = get_time_anchor_provider("local")
    anchor = p.anchor(DIGEST)
    bad = dict(anchor)
    # flip the signature
    sig = bytearray(base64.b64decode(bad["token"]))
    sig[0] ^= 0xFF
    bad["token"] = base64.b64encode(bytes(sig)).decode()
    res = provider_for_anchor(bad).verify(bad, DIGEST)
    assert res["valid"] is False


def test_service_verify_tier_and_cutoff(monkeypatch):
    from services import time_anchor_service as svc

    p = get_time_anchor_provider("local")
    anchor = p.anchor(DIGEST)
    fea_doc = {
        "fea_payload": {"fea_hash": DIGEST, "public_key_id": "key_test"},
        "time_anchor": {"envelope_version": "1", "anchors": [anchor]},
    }

    # No cutoff on key -> valid time uplift.
    class _Key:
        time_anchor_cutoff = None

    async def _get_key(_id):
        return _Key()

    monkeypatch.setattr("services.key_service.get_key_by_id", _get_key)
    res = asyncio.get_event_loop().run_until_complete(svc.verify_time_attestation(fea_doc))
    assert res["present"] is True and res["valid"] is True
    assert res["tier"].startswith("signed+timestamped")
    assert res["key_cutoff_ok"] is True

    # Cutoff in the PAST -> backdating defense trips, valid False, tier downgraded.
    class _KeyCut:
        time_anchor_cutoff = "2000-01-01T00:00:00.000Z"

    async def _get_key_cut(_id):
        return _KeyCut()

    monkeypatch.setattr("services.key_service.get_key_by_id", _get_key_cut)
    res2 = asyncio.get_event_loop().run_until_complete(svc.verify_time_attestation(fea_doc))
    assert res2["key_cutoff_ok"] is False
    assert res2["valid"] is False
    assert res2["tier"] == "signed"
    assert "backdated" in (res2["cutoff_reason"] or "").lower()


def test_no_anchor_returns_none():
    from services import time_anchor_service as svc
    res = asyncio.get_event_loop().run_until_complete(
        svc.verify_time_attestation({"fea_payload": {"fea_hash": DIGEST}})
    )
    assert res is None
