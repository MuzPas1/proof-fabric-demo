"""Unit tests for the inbound event ingestion framework.

Focus: pure normalization/adapter logic, credential auth providers, and event
mapping onto the existing proof contract. No DB required.
"""
import hashlib
import hmac
import json

import pytest

from core.ingestion import auth_providers
from core.ingestion.adapters import GenericEventAdapter, AdapterError, get_adapter
from models.ingestion import CommonEvent, CreateIntegrationRequest
from services import ingestion_service


# --------------------------------------------------------------------------
# Adapter normalization
# --------------------------------------------------------------------------
def test_generic_adapter_basic_normalization():
    adapter = GenericEventAdapter()
    payload = {"type": "invoice.created", "id": "INV-1", "timestamp": "2026-06-10T12:00:00Z",
               "user": "u-1", "resource": "acct-9", "amount": 500, "currency": "eur", "note": "hi"}
    integration = {"slug": "acme", "default_currency": "USD", "field_map": {}}
    ev = adapter.normalize(payload, integration)
    assert ev.event_type == "invoice.created"
    assert ev.external_id == "INV-1"
    assert ev.amount == 500
    assert ev.currency == "EUR"
    assert ev.actor == "u-1" and ev.subject == "acct-9"
    assert ev.attributes.get("note") == "hi"  # unconsumed field preserved


def test_generic_adapter_field_map():
    adapter = GenericEventAdapter()
    payload = {"orderId": "O-99", "kind": "order.shipped", "when": "2026-06-10T12:00:00Z"}
    integration = {"slug": "shop", "default_currency": "USD",
                   "field_map": {"external_id": "orderId", "event_type": "kind", "occurred_at": "when"}}
    ev = adapter.normalize(payload, integration)
    assert ev.external_id == "O-99"
    assert ev.event_type == "order.shipped"


def test_generic_adapter_defaults_for_nonfinancial():
    adapter = GenericEventAdapter()
    payload = {"type": "user.access_granted", "id": "EVT-7"}
    ev = adapter.normalize(payload, {"slug": "hr", "default_currency": "USD", "field_map": {}})
    assert ev.amount == 0
    assert ev.currency == "USD"


def test_generic_adapter_requires_identifier():
    adapter = GenericEventAdapter()
    with pytest.raises(AdapterError):
        adapter.normalize({"type": "x"}, {"slug": "s", "field_map": {}})


def test_generic_adapter_rejects_negative_amount():
    adapter = GenericEventAdapter()
    with pytest.raises(AdapterError):
        adapter.normalize({"id": "1", "amount": -5}, {"slug": "s", "field_map": {}})


def test_get_adapter_unknown():
    with pytest.raises(AdapterError):
        get_adapter("does-not-exist")


# --------------------------------------------------------------------------
# Auth providers
# --------------------------------------------------------------------------
def test_hmac_auth_valid_and_invalid():
    secret = "whsec_test"
    body = b'{"id":"1"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    integration = {"auth_provider": "hmac", "hmac_secret": secret, "signature_header": "x-pfp-signature"}
    ok, _ = auth_providers.verify(integration, {"x-pfp-signature": sig}, body)
    assert ok
    ok2, _ = auth_providers.verify(integration, {"x-pfp-signature": "sha256=" + sig}, body)
    assert ok2
    bad, _ = auth_providers.verify(integration, {"x-pfp-signature": "deadbeef"}, body)
    assert not bad
    missing, _ = auth_providers.verify(integration, {}, body)
    assert not missing


def test_api_key_auth():
    token = "pfp_evt_abc"
    integration = {"auth_provider": "api_key", "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                   "token_header": "x-integration-key"}
    ok, _ = auth_providers.verify(integration, {"x-integration-key": token}, b"{}")
    assert ok
    bad, _ = auth_providers.verify(integration, {"x-integration-key": "wrong"}, b"{}")
    assert not bad


def test_bearer_auth():
    token = "pfp_evt_xyz"
    integration = {"auth_provider": "bearer", "token_hash": hashlib.sha256(token.encode()).hexdigest()}
    ok, _ = auth_providers.verify(integration, {"authorization": f"Bearer {token}"}, b"{}")
    assert ok
    bad, _ = auth_providers.verify(integration, {"authorization": "Bearer nope"}, b"{}")
    assert not bad


def test_none_auth_passes():
    ok, _ = auth_providers.verify({"auth_provider": "none"}, {}, b"{}")
    assert ok


# --------------------------------------------------------------------------
# Mapping to the existing proof contract
# --------------------------------------------------------------------------
def test_map_to_request_tokenizes_and_defaults():
    ev = CommonEvent(event_type="t", external_id="E-1", occurred_at="2026-06-10T12:00:00Z",
                     actor="alice", subject="acct", amount=0, currency="USD")
    req = ingestion_service.map_to_request(ev, {"slug": "acme"})
    assert req.transaction_id == "E-1"
    # actor/subject must be hashed (never raw) in the signed contract
    assert req.payer_id == hashlib.sha256(b"alice").hexdigest()
    assert req.payee_id == hashlib.sha256(b"acct").hexdigest()
    assert req.metadata["integration"] == "acme"
    assert req.idempotency_key.startswith("acme:E-1:")


def test_credential_issuance_shapes():
    raw, cred = ingestion_service._issue_credential("hmac")
    assert raw and cred["hmac_secret"] == raw and cred["token_hash"] is None
    raw2, cred2 = ingestion_service._issue_credential("api_key")
    assert raw2 and cred2["token_hash"] == hashlib.sha256(raw2.encode()).hexdigest()
    raw3, cred3 = ingestion_service._issue_credential("none")
    assert raw3 is None


def test_create_request_slug_validation():
    with pytest.raises(Exception):
        CreateIntegrationRequest(name="x", slug="Bad Slug!")
    ok = CreateIntegrationRequest(name="x", slug="acme-events")
    assert ok.slug == "acme-events"


def test_integration_public_redacts_secrets():
    from models.ingestion import IntegrationConfig
    cfg = IntegrationConfig(integration_id="i1", slug="s", name="n", hmac_secret="whsec_x", token_hash="abc")
    pub = cfg.public()
    assert "hmac_secret" not in pub and "token_hash" not in pub
    assert pub["auth_configured"] is True
