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


def test_integration_public_allowlist_redaction():
    from models.ingestion import IntegrationConfig
    cfg = IntegrationConfig(integration_id="i1", slug="s", name="n", hmac_secret="whsec_x", token_hash="abc",
                            basic_password_hash="def", external_secret="ghi",
                            auth_config={"jwks_url": "https://x/jwks", "issuer": "acme", "client_secret": "shh",
                                         "some_future_secret": "leak?"})
    pub = cfg.public()
    # secret fields are never present (allow-list omits them)
    for s in ("hmac_secret", "token_hash", "basic_password_hash", "external_secret"):
        assert s not in pub
    assert pub["auth_configured"] is True
    # only approved auth_config keys are exposed; everything else omitted entirely
    assert pub["auth_config"]["jwks_url"] == "https://x/jwks"
    assert pub["auth_config"]["issuer"] == "acme"
    assert "client_secret" not in pub["auth_config"]
    assert "some_future_secret" not in pub["auth_config"]


def test_circuit_breaker_opens_and_resets():
    from core.ingestion.auth_providers import _CircuitBreaker
    cb = _CircuitBreaker(threshold=2, cooldown=60)
    assert cb.allow("u")
    cb.record_failure("u")
    assert cb.allow("u")            # 1 failure, still closed
    cb.record_failure("u")
    assert not cb.allow("u")        # threshold reached -> open (fail-fast)
    cb.record_success("u")          # reachable IdP resets
    assert cb.allow("u")


def test_oauth2_introspection_fails_closed_when_unconfigured():
    integ = {"auth_provider": "oauth2", "auth_config": {"oauth_mode": "introspection"}}
    r = auth_providers.authenticate(integ, {"authorization": "Bearer x"}, b"{}")
    assert not r.ok


# --------------------------------------------------------------------------
# Generalized providers
# --------------------------------------------------------------------------
def test_hmac_sha1_provider():
    secret = "whsec_1"
    body = b'{"id":"1"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    integ = {"auth_provider": "hmac_sha1", "hmac_secret": secret, "auth_config": {"signature_header": "x-sig"}}
    r = auth_providers.authenticate(integ, {"x-sig": sig}, body)
    assert r.ok
    assert not auth_providers.authenticate(integ, {"x-sig": "bad"}, body).ok


def test_hmac_stripe_scheme_extracts_timestamp():
    import time
    secret = "whsec_stripe"
    body = b'{"id":"evt_1"}'
    ts = str(int(time.time()))
    signed = f"{ts}.{body.decode()}".encode()
    v1 = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    integ = {"auth_provider": "hmac_sha256", "hmac_secret": secret,
             "auth_config": {"signature_scheme": "stripe"}}
    r = auth_providers.authenticate(integ, {"stripe-signature": f"t={ts},v1={v1}"}, body)
    assert r.ok and r.timestamp is not None
    assert r.replay_key == v1


def test_basic_provider():
    import base64
    integ = {"auth_provider": "basic", "basic_password_hash": hashlib.sha256(b"pw123").hexdigest(),
             "auth_config": {"basic_username": "acme"}}
    tok = base64.b64encode(b"acme:pw123").decode()
    assert auth_providers.authenticate(integ, {"authorization": f"Basic {tok}"}, b"{}").ok
    bad = base64.b64encode(b"acme:wrong").decode()
    assert not auth_providers.authenticate(integ, {"authorization": f"Basic {bad}"}, b"{}").ok


def test_jwt_provider_hs256():
    import jwt as pyjwt
    import time
    secret = "jwt-shared-secret-at-least-32-bytes-long!!"
    token = pyjwt.encode({"sub": "svc-1", "iss": "acme", "aud": "pfp",
                          "exp": int(time.time()) + 300}, secret, algorithm="HS256")
    integ = {"auth_provider": "jwt", "external_secret": secret,
             "auth_config": {"jwt_algorithms": ["HS256"], "issuer": "acme", "audience": "pfp"}}
    r = auth_providers.authenticate(integ, {"authorization": f"Bearer {token}"}, b"{}")
    assert r.ok and r.principal == "svc-1"
    # expired token rejected
    expired = pyjwt.encode({"sub": "x", "iss": "acme", "aud": "pfp", "exp": int(time.time()) - 3600},
                           secret, algorithm="HS256")
    assert not auth_providers.authenticate(integ, {"authorization": f"Bearer {expired}"}, b"{}").ok
    # wrong secret rejected
    bad = pyjwt.encode({"sub": "x", "iss": "acme", "aud": "pfp", "exp": int(time.time()) + 300},
                       "other", algorithm="HS256")
    assert not auth_providers.authenticate(integ, {"authorization": f"Bearer {bad}"}, b"{}").ok


def test_jwt_never_trusts_alg_none():
    import jwt as pyjwt
    import time
    unsigned = pyjwt.encode({"sub": "x", "exp": int(time.time()) + 300}, key=None, algorithm="none")
    integ = {"auth_provider": "jwt", "external_secret": "s", "auth_config": {"jwt_algorithms": ["HS256"]}}
    assert not auth_providers.authenticate(integ, {"authorization": f"Bearer {unsigned}"}, b"{}").ok


def test_mtls_header_provider():
    integ = {"auth_provider": "mtls", "auth_config": {"allowed_fingerprints": ["AA:BB"]}}
    ok = auth_providers.authenticate(integ, {"x-client-verify": "SUCCESS", "x-client-cert-fingerprint": "AA:BB"}, b"{}")
    assert ok.ok
    assert not auth_providers.authenticate(integ, {"x-client-verify": "NONE"}, b"{}").ok
    assert not auth_providers.authenticate(integ, {"x-client-verify": "SUCCESS", "x-client-cert-fingerprint": "ZZ"}, b"{}").ok


def test_custom_provider_registry():
    from core.ingestion.auth_providers import register_custom_provider, AuthResult
    register_custom_provider("always_ok", lambda i, h, b: AuthResult(True))
    integ = {"auth_provider": "custom", "auth_config": {"custom_handler": "always_ok"}}
    assert auth_providers.authenticate(integ, {}, b"{}").ok
    integ2 = {"auth_provider": "custom", "auth_config": {"custom_handler": "missing"}}
    assert not auth_providers.authenticate(integ2, {}, b"{}").ok


def test_credential_providers_set():
    from models.ingestion import CREDENTIAL_PROVIDERS
    assert "basic" in CREDENTIAL_PROVIDERS
    assert "jwt" not in CREDENTIAL_PROVIDERS
    raw, cred = ingestion_service._issue_credential("basic")
    assert raw and cred["basic_password_hash"] == hashlib.sha256(raw.encode()).hexdigest()
    raw2, _ = ingestion_service._issue_credential("jwt")
    assert raw2 is None


def test_backward_compat_verify_wrapper():
    secret = "whsec_bc"
    body = b'{"id":"1"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    integ = {"auth_provider": "hmac", "hmac_secret": secret, "signature_header": "x-pfp-signature"}
    ok, reason = auth_providers.verify(integ, {"x-pfp-signature": sig}, body)
    assert ok and reason == "ok"
