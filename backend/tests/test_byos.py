"""BYOS (Bring-Your-Own-Signing) tests — local, remote (live HTTP), cloud-kms.

Validates that:
  - LocalSigner is byte-identical to the existing sign path.
  - RemoteSigner signs via an external HTTP endpoint (private key stays remote)
    and the resulting FEA verifies independently of signer availability.
  - A remote signer outage fails ISSUANCE but NOT verification of prior proofs.
  - CloudKmsSigner is config-gated (raises KMSNotConfigured).
"""
import asyncio
import base64
import json
import os
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ["DB_NAME"] = "pfp_byos_test"
os.environ.setdefault("PRIVATE_KEY", "8vU9cBlfDyl7lnuubAUtxAPlZQ5uAuGtHShS6OhwZ9Y=")
os.environ.setdefault("DEMO_PRIVATE_KEY", "QcFX/GCV2fy9sOFXsoBSla9JD/SbEZMw9HSmmESCQhM=")
os.environ.setdefault("KMS_PROVIDER", "local")
os.environ["ENABLE_CRYPTO_SUITES"] = "true"
os.environ["ENABLE_BYOS"] = "true"

from nacl.signing import SigningKey  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402

from crypto import suites  # noqa: E402
from crypto.signing import sign_message, DOMAIN_PREFIX_V2  # noqa: E402
from crypto.canonicalize import canonicalize_to_json  # noqa: E402
from core.signers import LocalSigner, RemoteSigner, CloudKmsSigner  # noqa: E402
from core.kms import KMSNotConfigured  # noqa: E402
from services.fea_service import build_fea_payload, compute_fea_hash, generate_fea  # noqa: E402
from services.verification_service import verify_fea  # noqa: E402
from models.fea import GenerateFEARequest  # noqa: E402


# --- A live external "partner" HTTP signer backed by a fixed Ed25519 key ----
_PARTNER_SK = SigningKey.generate()
_PARTNER_PUB_B64 = base64.b64encode(bytes(_PARTNER_SK.verify_key)).decode()


class _SignerHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode())
        message = base64.b64decode(body["message_b64"])
        sig = _PARTNER_SK.sign(message).signature
        resp = json.dumps({"signature_b64": base64.b64encode(sig).decode()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(resp)


@pytest.fixture(scope="module")
def remote_endpoint():
    server = HTTPServer(("127.0.0.1", 0), _SignerHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}/sign"
    server.shutdown()


def test_local_signer_byte_identical():
    msg = canonicalize_to_json({"a": 1, "b": 2})
    via_signer = LocalSigner("production", "Ed25519").sign((DOMAIN_PREFIX_V2 + msg).encode())
    via_signer_b64 = base64.b64encode(via_signer).decode()
    assert via_signer_b64 == sign_message(msg, suite_alg="Ed25519")


def test_remote_signer_sign_and_verify(remote_endpoint):
    signer = RemoteSigner(endpoint=remote_endpoint, algorithm="Ed25519", public_key_b64=_PARTNER_PUB_B64)
    assert signer.public_key_b64() == _PARTNER_PUB_B64
    assert signer.native is True
    msg = b"PFP_V2::remote-test"
    sig = signer.sign(msg)
    ok, _ = suites.verify("Ed25519", base64.b64decode(_PARTNER_PUB_B64), msg, sig)
    assert ok is True


def test_remote_signer_fea_end_to_end_and_independence(remote_endpoint):
    signer = RemoteSigner(endpoint=remote_endpoint, algorithm="Ed25519", public_key_b64=_PARTNER_PUB_B64)
    req = GenerateFEARequest(
        idempotency_key="byos1", transaction_id="TXN-BYOS", timestamp="2026-06-10T12:00:00Z",
        amount=10, currency="usd", payer_id="p", payee_id="q",
    )
    resp, _doc = generate_fea(req, skip_timestamp_validation=True, tenant_id="acme", signer=signer)
    assert resp.fea_payload["algorithm"] == "Ed25519"
    assert resp.public_key_id == signer.public_key_id()

    # Independent verification uses ONLY the public key — signer not contacted.
    registry = {resp.public_key_id: base64.b64decode(_PARTNER_PUB_B64)}
    valid, reason, _ = verify_fea(
        resp.fea_payload, resp.signature, registry,
        skip_timestamp_validation=True, key_algorithm="Ed25519",
        external_signature_version="v2",
    )
    assert valid is True, reason


def test_remote_signer_outage_fails_issuance_not_verification(remote_endpoint):
    # Pre-issue a proof while the signer is up.
    signer = RemoteSigner(endpoint=remote_endpoint, algorithm="Ed25519", public_key_b64=_PARTNER_PUB_B64)
    req = GenerateFEARequest(
        idempotency_key="byos2", transaction_id="TXN-BYOS-2", timestamp="2026-06-10T12:00:00Z",
        amount=10, currency="usd", payer_id="p", payee_id="q",
    )
    resp, _ = generate_fea(req, skip_timestamp_validation=True, tenant_id="acme", signer=signer)

    # Now point the signer at a dead endpoint → issuance must fail.
    dead = RemoteSigner(endpoint="http://127.0.0.1:1/sign", algorithm="Ed25519", public_key_b64=_PARTNER_PUB_B64, timeout=1.0)
    with pytest.raises(Exception):
        generate_fea(req, skip_timestamp_validation=True, tenant_id="acme", signer=dead)

    # But verification of the previously issued proof STILL works (independence).
    registry = {resp.public_key_id: base64.b64decode(_PARTNER_PUB_B64)}
    valid, reason, _ = verify_fea(
        resp.fea_payload, resp.signature, registry,
        skip_timestamp_validation=True, key_algorithm="Ed25519",
        external_signature_version="v2",
    )
    assert valid is True, reason


def test_cloud_kms_signer_config_gated():
    pub = base64.b64encode(bytes(SigningKey.generate().verify_key)).decode()
    signer = CloudKmsSigner(provider="aws", key_ref="arn:...:key/abc", algorithm="Ed25519", public_key_b64=pub)
    assert signer.native is True
    with pytest.raises(KMSNotConfigured):
        signer.sign(b"PFP_V2::x")


def test_signer_service_configure_and_resolve(remote_endpoint):
    from motor.motor_asyncio import AsyncIOMotorClient
    from services import signer_service

    async def run():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client["pfp_byos_" + uuid.uuid4().hex[:8]]
        try:
            from services import key_service
            await key_service.initialize_key_registry(db)
            await signer_service.ensure_indexes(db)
            cfg = await signer_service.configure_signer(db, "acme", {
                "type": "remote", "algorithm": "Ed25519",
                "endpoint": remote_endpoint, "public_key": _PARTNER_PUB_B64,
                "auth_header": "Bearer secret-xyz",
            })
            # Secret must NOT be returned.
            assert "auth_header" not in cfg
            assert cfg["type"] == "remote"
            signer = await signer_service.resolve_signer(db, "acme")
            assert signer.name == "remote"
            assert signer.public_key_b64() == _PARTNER_PUB_B64
            # Default tenant → LocalSigner.
            default = await signer_service.resolve_signer(db, "default")
            assert default.name == "local"
        finally:
            await client.drop_database(db.name)
            client.close()

    asyncio.run(run())
