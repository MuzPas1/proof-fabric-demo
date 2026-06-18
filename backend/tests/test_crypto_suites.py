"""Crypto-agility (signature suite) unit tests + known-answer test vectors.

Covers Ed25519 / ES256 (secp256r1) / ES256K (secp256k1):
  - sign/verify round-trip
  - low-S enforcement (anti-malleability)
  - wrong-key / tampered-message rejection
  - algorithm-confusion rejection at the FEA layer
  - end-to-end FEA build → sign → independent verify for each suite
"""
import base64
import hashlib
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "pfp_ci")
os.environ.setdefault("PRIVATE_KEY", "8vU9cBlfDyl7lnuubAUtxAPlZQ5uAuGtHShS6OhwZ9Y=")
os.environ.setdefault("DEMO_PRIVATE_KEY", "QcFX/GCV2fy9sOFXsoBSla9JD/SbEZMw9HSmmESCQhM=")
os.environ.setdefault("KMS_PROVIDER", "local")
os.environ["ENABLE_CRYPTO_SUITES"] = "true"

# Provision EC signing keys for the local KMS so end-to-end suite tests run.
import base64 as _b64  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec as _ec  # noqa: E402
from cryptography.hazmat.primitives import serialization as _ser  # noqa: E402
for _alg, _curve in (("ES256", _ec.SECP256R1()), ("ES256K", _ec.SECP256K1())):
    if not os.environ.get(f"EC_PRIVATE_KEY_{_alg}"):
        _p = _ec.generate_private_key(_curve)
        _der = _p.private_bytes(_ser.Encoding.DER, _ser.PrivateFormat.PKCS8, _ser.NoEncryption())
        os.environ[f"EC_PRIVATE_KEY_{_alg}"] = _b64.b64encode(_der).decode()


from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from nacl.signing import SigningKey  # noqa: E402

from crypto import suites  # noqa: E402


def _ed25519_keypair():
    sk = SigningKey.generate()
    return sk, bytes(sk.verify_key)


def _ec_keypair(alg):
    curve = ec.SECP256R1() if alg == suites.ALG_ES256 else ec.SECP256K1()
    priv = ec.generate_private_key(curve)
    pub = suites.public_key_bytes(alg, priv)
    return priv, pub


@pytest.mark.parametrize("alg", list(suites.SUPPORTED_ALGORITHMS))
def test_sign_verify_roundtrip(alg):
    msg = b"PFP_V2::{\"a\":1}"
    if alg == suites.ALG_ED25519:
        priv, pub = _ed25519_keypair()
    else:
        priv, pub = _ec_keypair(alg)
    sig = suites.sign(alg, priv, msg)
    assert len(sig) == 64  # Ed25519 and ECDSA r||s are both 64 bytes
    ok, reason = suites.verify(alg, pub, msg, sig)
    assert ok is True, reason


@pytest.mark.parametrize("alg", list(suites.SUPPORTED_ALGORITHMS))
def test_tampered_message_fails(alg):
    if alg == suites.ALG_ED25519:
        priv, pub = _ed25519_keypair()
    else:
        priv, pub = _ec_keypair(alg)
    sig = suites.sign(alg, priv, b"PFP_V2::message-A")
    ok, _ = suites.verify(alg, pub, b"PFP_V2::message-B", sig)
    assert ok is False


@pytest.mark.parametrize("alg", list(suites.SUPPORTED_ALGORITHMS))
def test_wrong_key_fails(alg):
    if alg == suites.ALG_ED25519:
        priv, _ = _ed25519_keypair()
        _, other_pub = _ed25519_keypair()
    else:
        priv, _ = _ec_keypair(alg)
        _, other_pub = _ec_keypair(alg)
    sig = suites.sign(alg, priv, b"PFP_V2::x")
    ok, _ = suites.verify(alg, other_pub, b"PFP_V2::x", sig)
    assert ok is False


@pytest.mark.parametrize("alg", [suites.ALG_ES256, suites.ALG_ES256K])
def test_ecdsa_low_s_enforced_on_sign(alg):
    """Every signature we produce must already be in low-S canonical form."""
    priv, pub = _ec_keypair(alg)
    order = suites._EC_ORDER[alg]
    for i in range(25):
        sig = suites.sign(alg, priv, f"PFP_V2::msg-{i}".encode())
        s = int.from_bytes(sig[32:], "big")
        assert s <= order // 2, "signature is not low-S"


@pytest.mark.parametrize("alg", [suites.ALG_ES256, suites.ALG_ES256K])
def test_ecdsa_high_s_rejected_on_verify(alg):
    """A malleated high-S variant of a valid signature must be rejected."""
    priv, pub = _ec_keypair(alg)
    msg = b"PFP_V2::malleable"
    sig = suites.sign(alg, priv, msg)
    r = int.from_bytes(sig[:32], "big")
    s = int.from_bytes(sig[32:], "big")
    order = suites._EC_ORDER[alg]
    high_s = order - s  # the malleated counterpart
    malleated = r.to_bytes(32, "big") + high_s.to_bytes(32, "big")
    ok, reason = suites.verify(alg, pub, msg, malleated)
    assert ok is False
    assert "non-canonical" in (reason or "").lower() or "verification error" in (reason or "").lower()


def test_normalize_aliases():
    assert suites.normalize_algorithm("secp256r1") == suites.ALG_ES256
    assert suites.normalize_algorithm("secp256k1") == suites.ALG_ES256K
    assert suites.normalize_algorithm("ed25519") == suites.ALG_ED25519
    assert suites.normalize_algorithm(None) == suites.ALG_ED25519


# ---------------------------------------------------------------------------
# End-to-end FEA build → sign → verify per suite (uses local KMS EC keys)
# ---------------------------------------------------------------------------
from crypto.canonicalize import canonicalize_to_json  # noqa: E402
from crypto.signing import sign_message, get_public_key_b64_for  # noqa: E402
from services.fea_service import build_fea_payload, compute_fea_hash  # noqa: E402
from services.verification_service import verify_fea  # noqa: E402
from models.fea import GenerateFEARequest  # noqa: E402


@pytest.mark.parametrize("alg", list(suites.SUPPORTED_ALGORITHMS))
def test_fea_end_to_end_per_suite(alg):
    if alg != suites.ALG_ED25519:
        # Skip if the EC key isn't configured in this environment.
        from core.kms import get_kms
        if not get_kms().supports_algorithm("production", alg):
            pytest.skip(f"{alg} key not configured")
    req = GenerateFEARequest(
        idempotency_key="ik", transaction_id="TXN-AGILITY", timestamp="2026-06-10T12:00:00Z",
        amount=4200, currency="usd", payer_id="p", payee_id="q",
    )
    payload = build_fea_payload(req, tenant_id="acme", suite_alg=alg)
    assert payload["algorithm"] == alg
    payload["fea_hash"] = compute_fea_hash(payload)
    sig = sign_message(canonicalize_to_json(payload), suite_alg=alg)

    pub_b64 = get_public_key_b64_for(alg)
    registry = {payload["public_key_id"]: base64.b64decode(pub_b64)}
    valid, reason, ver = verify_fea(
        payload, sig, registry, skip_timestamp_validation=True, key_algorithm=alg, external_signature_version="v2"
    )
    assert valid is True, reason


@pytest.mark.parametrize("alg", [suites.ALG_ES256, suites.ALG_ES256K])
def test_fea_algorithm_confusion_rejected(alg):
    """Payload claims a different algorithm than the trusted key → reject."""
    from core.kms import get_kms
    if not get_kms().supports_algorithm("production", alg):
        pytest.skip(f"{alg} key not configured")
    req = GenerateFEARequest(
        idempotency_key="ik2", transaction_id="TXN-CONFUSE", timestamp="2026-06-10T12:00:00Z",
        amount=1, currency="usd", payer_id="p", payee_id="q",
    )
    payload = build_fea_payload(req, tenant_id="acme", suite_alg=alg)
    payload["fea_hash"] = compute_fea_hash(payload)
    sig = sign_message(canonicalize_to_json(payload), suite_alg=alg)
    pub_b64 = get_public_key_b64_for(alg)
    registry = {payload["public_key_id"]: base64.b64decode(pub_b64)}
    # Tell verify the trusted key is Ed25519 while payload says ES256/ES256K.
    valid, reason, _ = verify_fea(
        payload, sig, registry, skip_timestamp_validation=True, key_algorithm="Ed25519", external_signature_version="v2"
    )
    assert valid is False
    assert "algorithm" in (reason or "").lower()
