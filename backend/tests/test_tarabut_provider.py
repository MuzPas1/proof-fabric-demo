"""Unit tests for the additive Tarabut Gateway (Open Banking) provider.

Covers: registry/preset registration, RS256 inbound webhook verification
(valid / tamper / no-key / accept-and-flag / JWKS), and the Tarabut event
adapter across its three input shapes with PII hash-only guarantees. No DB or
network dependency (JWKS is exercised via a local monkeypatched fetch).
"""
import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from core.ingestion import auth_providers, presets, registry
from core.ingestion.adapters import AdapterError, get_adapter

INTEG = {"slug": "tarabut", "adapter": "tarabut", "default_currency": "BHD",
         "auth_config": {"tarabut_region": "bahrain"}}


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return key, pem


def _sign(key, body: bytes) -> str:
    return base64.b64encode(key.sign(body, padding.PKCS1v15(), hashes.SHA256())).decode()


# --- registration ---------------------------------------------------------
def test_registry_and_preset_registered():
    assert registry.get_provider("tarabut").category == "Open Banking"
    assert "rsa_sha256" in registry.INBOUND_AUTH_METHODS
    assert registry.auth_method_label("rsa_sha256") == "RSA Digital Signature (RS256)"
    p = presets.get_preset("tarabut")
    assert p and p.adapter == "tarabut" and p.auth_provider == "rsa_sha256"


# --- RS256 inbound verification -------------------------------------------
def test_rsa_verify_valid_and_tamper():
    key, pem = _keypair()
    body = json.dumps({"paymentId": "p1", "status": "COMPLETED"}).encode()
    sig = _sign(key, body)
    integ = {"auth_provider": "rsa_sha256",
             "auth_config": {"public_key": pem, "signature_header": "x-signature"}}
    assert auth_providers.authenticate(integ, {"x-signature": sig}, body).ok
    assert not auth_providers.authenticate(integ, {"x-signature": sig}, body + b"x").ok


def test_rsa_no_key_fails_closed_unless_flagged():
    body = b'{"paymentId":"p1"}'
    integ = {"auth_provider": "rsa_sha256", "auth_config": {}}
    assert not auth_providers.authenticate(integ, {"x-signature": "abc"}, body).ok
    integ_flag = {"auth_provider": "rsa_sha256", "auth_config": {"accept_unverified": "true"}}
    r = auth_providers.authenticate(integ_flag, {"x-signature": "abc"}, body)
    assert r.ok and "unverified" in r.reason


def test_rsa_kid_map_and_missing_signature():
    key, pem = _keypair()
    body = b'{"paymentId":"p2"}'
    sig = _sign(key, body)
    integ = {"auth_provider": "rsa_sha256",
             "auth_config": {"rsa_public_keys": {"kid-1": pem}}}
    assert auth_providers.authenticate(integ, {"x-signature": sig, "x-signature-keyid": "kid-1"}, body).ok
    # missing signature header -> reject
    assert not auth_providers.authenticate(integ, {"x-signature-keyid": "kid-1"}, body).ok


def test_rsa_jwks(monkeypatch):
    key, pem = _keypair()
    body = b'{"paymentId":"p3"}'
    sig = _sign(key, body)
    pub = serialization.load_pem_public_key(pem.encode())
    nums = pub.public_numbers()

    def b64u(i):
        raw = i.to_bytes((i.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    jwks = {"keys": [{"kty": "RSA", "alg": "RS256", "kid": "k9",
                      "n": b64u(nums.n), "e": b64u(nums.e)}]}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return jwks

    monkeypatch.setattr(auth_providers.httpx if hasattr(auth_providers, "httpx") else __import__("httpx"),
                        "get", lambda *a, **k: _Resp())
    integ = {"auth_provider": "rsa_sha256",
             "auth_config": {"jwks_url": "https://example.test/jwks"}}
    assert auth_providers.authenticate(integ, {"x-signature": sig, "x-signature-keyid": "k9"}, body).ok


# --- adapter: three shapes + PII hashing ----------------------------------
def test_adapter_payment_webhook_hashes_pii():
    ev = get_adapter("tarabut").normalize(
        {"type": "PAYMENT_STATUS_CHANGE", "paymentId": "pay1", "status": "COMPLETED",
         "amount": 10.95, "currency": "BHD", "payerToken": "tok_secret",
         "destinationAccount": "BHD1", "bankName": "ILA"}, INTEG)
    assert ev.event_type == "payment_completed" and ev.amount == 1095 and ev.currency == "BHD"
    assert ev.provider == "Tarabut" and ev.event_source == "Webhook"
    blob = json.dumps(ev.attributes)
    assert "payerToken_hash" in ev.attributes and "tok_secret" not in blob


def test_adapter_consent_and_envelope():
    consent = get_adapter("tarabut").normalize(
        {"id": "c1", "status": "REVOKED", "providerId": "BLUE",
         "connectedAccounts": [{"id": "a1", "identifiers": [{"type": "IBAN", "value": "BH00SECRET"}]}]}, INTEG)
    assert consent.event_type == "consent_revoked"
    assert "BH00SECRET" not in json.dumps(consent.attributes)

    env = get_adapter("tarabut").normalize(
        {"tarabutEventType": "account_linked", "externalId": "acc9", "status": "ACTIVE",
         "providerId": "BLUE", "attributes": {"Account Product Type": "CurrentAccount"},
         "sensitive": {"iban": "BH11SECRET", "accountHolderName": "John Snow"}}, INTEG)
    assert env.event_type == "account_linked" and env.event_source == "API"
    assert "iban_hash" in env.attributes and "John Snow" not in json.dumps(env.attributes)


def test_adapter_requires_identifier():
    with pytest.raises(AdapterError):
        get_adapter("tarabut").normalize({"foo": "bar"}, INTEG)
