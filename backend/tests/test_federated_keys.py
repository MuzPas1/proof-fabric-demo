"""Federated key registry tests — PoP, JWK, validity windows, tenant isolation."""
import asyncio
import base64
import os
import sys
import uuid
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ["DB_NAME"] = "pfp_fed_test"
os.environ.setdefault("PRIVATE_KEY", "8vU9cBlfDyl7lnuubAUtxAPlZQ5uAuGtHShS6OhwZ9Y=")
os.environ.setdefault("DEMO_PRIVATE_KEY", "QcFX/GCV2fy9sOFXsoBSla9JD/SbEZMw9HSmmESCQhM=")
os.environ.setdefault("KMS_PROVIDER", "local")
os.environ["ENABLE_CRYPTO_SUITES"] = "true"
os.environ["ENABLE_FEDERATED_KEYS"] = "true"

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from nacl.signing import SigningKey  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402

from crypto import suites  # noqa: E402
from services import federated_key_service as fed  # noqa: E402
from services.verification_service import _check_key_constraints  # noqa: E402
from models.key_registry import PublicKeyInfo  # noqa: E402

POP = fed.POP_DOMAIN_PREFIX


def _fresh_db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"] + "_" + uuid.uuid4().hex[:8]]
    return client, db


def _sign_pop(alg, priv, challenge):
    msg = (POP + challenge).encode()
    return base64.b64encode(suites.sign(alg, priv, msg)).decode()


def test_federated_register_confirm_ed25519():
    async def run():
        client, db = _fresh_db()
        try:
            await fed.ensure_indexes(db)
            sk = SigningKey.generate()
            pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode()
            info, challenge, _ = await fed.register_federated_key(
                db, "acme", algorithm="Ed25519", key_format="raw",
                public_key=pub_b64, jwk=None, owner="partner", label="Acme",
                not_before=None, not_after=None,
            )
            assert info.status == "pending"
            sig = _sign_pop("Ed25519", sk, challenge)
            confirmed = await fed.confirm_federated_key(db, "acme", info.public_key_id, sig)
            assert confirmed.status == "active"
            assert confirmed.pop_verified is True
            assert confirmed.tenant_id == "acme"
        finally:
            await client.drop_database(db.name)
            client.close()
    asyncio.run(run())


def test_federated_pop_wrong_signature_rejected():
    async def run():
        client, db = _fresh_db()
        try:
            await fed.ensure_indexes(db)
            sk = SigningKey.generate()
            other = SigningKey.generate()
            pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode()
            info, challenge, _ = await fed.register_federated_key(
                db, "acme", algorithm="Ed25519", key_format="raw",
                public_key=pub_b64, jwk=None, owner="partner", label=None,
                not_before=None, not_after=None,
            )
            bad = _sign_pop("Ed25519", other, challenge)  # wrong key
            with pytest.raises(ValueError, match="possession"):
                await fed.confirm_federated_key(db, "acme", info.public_key_id, bad)
        finally:
            await client.drop_database(db.name)
            client.close()
    asyncio.run(run())


def test_federated_register_confirm_jwk_es256():
    async def run():
        client, db = _fresh_db()
        try:
            await fed.ensure_indexes(db)
            priv = ec.generate_private_key(ec.SECP256R1())
            raw = suites.public_key_bytes("ES256", priv)
            jwk = suites.public_key_bytes_to_jwk("ES256", raw)
            info, challenge, _ = await fed.register_federated_key(
                db, "acme", algorithm="ES256", key_format="jwk",
                public_key=None, jwk=jwk, owner="customer", label=None,
                not_before=None, not_after=None,
            )
            assert info.algorithm == "ES256"
            assert info.jwk == jwk
            sig = _sign_pop("ES256", priv, challenge)
            confirmed = await fed.confirm_federated_key(db, "acme", info.public_key_id, sig)
            assert confirmed.status == "active"
        finally:
            await client.drop_database(db.name)
            client.close()
    asyncio.run(run())


def test_tenant_isolation_constraint():
    key = PublicKeyInfo(
        public_key_id="fed_key_x", public_key="AA==", algorithm="Ed25519",
        created_at="2026-01-01T00:00:00Z", status="active",
        tenant_id="acme", owner="partner",
    )
    ok, reason = _check_key_constraints(key, {"tenant_id": "other"})
    assert ok is False and "isolation" in reason.lower()
    ok2, _ = _check_key_constraints(key, {"tenant_id": "acme"})
    assert ok2 is True


def test_validity_window_constraint():
    key = PublicKeyInfo(
        public_key_id="fed_key_y", public_key="AA==", algorithm="Ed25519",
        created_at="2026-01-01T00:00:00Z", status="active",
        tenant_id="acme", owner="partner",
        not_before="2026-06-01T00:00:00Z", not_after="2026-12-31T00:00:00Z",
    )
    # before window
    ok, reason = _check_key_constraints(key, {"tenant_id": "acme", "iat": "2026-05-01T00:00:00Z"})
    assert ok is False and "not yet valid" in reason.lower()
    # after window
    ok2, reason2 = _check_key_constraints(key, {"tenant_id": "acme", "iat": "2027-01-01T00:00:00Z"})
    assert ok2 is False and "expired" in reason2.lower()
    # within window
    ok3, _ = _check_key_constraints(key, {"tenant_id": "acme", "iat": "2026-07-01T00:00:00Z"})
    assert ok3 is True


def test_legacy_platform_key_no_constraints():
    key = PublicKeyInfo(
        public_key_id="key_legacy", public_key="AA==", algorithm="Ed25519",
        created_at="2026-01-01T00:00:00Z", status="active",
    )
    ok, _ = _check_key_constraints(key, {"tenant_id": "anything"})
    assert ok is True
