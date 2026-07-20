"""Provider-preset registry tests (configuration-only; no core change).

Validates that every preset is a well-formed bundle of the SAME config keys the
generic framework already understands, contains NO secrets, and that a preset's
recommended config actually authenticates a matching inbound webhook via the
existing (unchanged) auth provider.
"""
import base64
import hashlib
import hmac
import json
import time

from core.ingestion import auth_providers, presets
from models.ingestion import ALLOWED_AUTH_CONFIG_KEYS, AUTH_PROVIDERS


def _sign_hex(secret: str, msg: bytes, algo=hashlib.sha256) -> str:
    return hmac.new(secret.encode(), msg, algo).hexdigest()


def _sign_b64(secret: str, msg: bytes, algo=hashlib.sha256) -> str:
    return base64.b64encode(hmac.new(secret.encode(), msg, algo).digest()).decode()


def test_presets_are_wellformed_and_secret_free():
    items = presets.list_presets()
    assert {p["id"] for p in items} >= {
        "generic", "cashfree", "stripe", "razorpay", "github", "slack", "shopify"
    }
    for p in items:
        assert p["auth_provider"] in AUTH_PROVIDERS
        # auth_config only uses allow-listed (public, non-secret) keys
        for k in (p.get("auth_config") or {}):
            assert k in ALLOWED_AUTH_CONFIG_KEYS, f"{p['id']} leaks config key {k}"
        # no secret material or secret-bearing fields are ever embedded
        assert set(p.keys()).isdisjoint(
            {"hmac_secret", "token_hash", "external_secret", "basic_password_hash", "secret"}
        )
        if p["requires_secret"]:
            assert p["secret_label"]


def test_generic_preset_uses_pfp_minted_hmac():
    p = presets.get_preset("generic")
    assert p.auth_provider == "hmac_sha256"
    assert not p.requires_secret
    assert p.auth_config == {}


def test_cashfree_preset_config_authenticates():
    p = presets.get_preset("cashfree")
    secret = "cfsk_test_key"
    body = json.dumps({"id": "ord_1"}).encode()
    ts = str(int(time.time() * 1000))
    sig = _sign_b64(secret, f"{ts}".encode() + body)
    integ = {"auth_provider": p.auth_provider, "external_secret": secret, "auth_config": p.auth_config}
    r = auth_providers.authenticate(integ, {"x-webhook-signature": sig, "x-webhook-timestamp": ts}, body)
    assert r.ok, r.reason
    bad = auth_providers.authenticate(integ, {"x-webhook-signature": "nope", "x-webhook-timestamp": ts}, body)
    assert not bad.ok


def test_razorpay_preset_config_authenticates():
    p = presets.get_preset("razorpay")
    secret = "rzp_whsec"
    body = b'{"event":"payment.captured"}'
    sig = _sign_hex(secret, body)
    integ = {"auth_provider": p.auth_provider, "external_secret": secret, "auth_config": p.auth_config}
    r = auth_providers.authenticate(integ, {"x-razorpay-signature": sig}, body)
    assert r.ok, r.reason
    assert not auth_providers.authenticate(integ, {"x-razorpay-signature": "bad"}, body).ok


def test_github_preset_prefix_and_hex():
    p = presets.get_preset("github")
    secret = "ghsecret"
    body = b'{"zen":"Keep it simple"}'
    sig = "sha256=" + _sign_hex(secret, body)
    integ = {"auth_provider": p.auth_provider, "external_secret": secret, "auth_config": p.auth_config}
    r = auth_providers.authenticate(integ, {"x-hub-signature-256": sig}, body)
    assert r.ok, r.reason


def test_shopify_preset_base64_plain():
    p = presets.get_preset("shopify")
    secret = "shpss_key"
    body = b'{"order_id":123}'
    sig = _sign_b64(secret, body)
    integ = {"auth_provider": p.auth_provider, "external_secret": secret, "auth_config": p.auth_config}
    r = auth_providers.authenticate(integ, {"x-shopify-hmac-sha256": sig}, body)
    assert r.ok, r.reason


def test_slack_preset_config_authenticates():
    p = presets.get_preset("slack")
    secret = "slack_signing"
    body = b"token=abc&team_id=T1"
    ts = str(int(time.time()))
    sig = "v0=" + _sign_hex(secret, f"v0:{ts}:".encode() + body)
    integ = {"auth_provider": p.auth_provider, "external_secret": secret, "auth_config": p.auth_config}
    r = auth_providers.authenticate(
        integ, {"x-slack-signature": sig, "x-slack-request-timestamp": ts}, body
    )
    assert r.ok, r.reason


def test_stripe_preset_config_authenticates():
    p = presets.get_preset("stripe")
    secret = "whsec_test"
    body = b'{"id":"evt_1"}'
    t = str(int(time.time()))
    v1 = _sign_hex(secret, f"{t}.".encode() + body)
    integ = {"auth_provider": p.auth_provider, "external_secret": secret, "auth_config": p.auth_config}
    r = auth_providers.authenticate(integ, {"stripe-signature": f"t={t},v1={v1}"}, body)
    assert r.ok, r.reason
