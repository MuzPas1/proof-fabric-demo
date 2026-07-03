"""Independent Time Attestation — provider abstraction (Trust Layer 2, Phase 1).

A *time anchor* is DETACHED evidence that a proof's ``fea_hash`` existed at or
before an attested time. It is produced AFTER signing and stored beside the
proof, so it NEVER changes the signed payload, ``fea_hash``, ``fea_id`` or the
signature. Verification of an anchor is independent of (and additive to) the
existing signature-verification flow.

Providers (selected by ``TIME_ANCHOR_PROVIDER``):
    local    -> PFP Local Time Authority. Deterministic, offline, self-verifying
                (Ed25519 over the digest). DEV/TEST/sandbox only — NOT an
                independent third party, so it is honestly labelled as such.
    rfc3161  -> Real RFC-3161 Timestamp Authority over HTTP (e.g. FreeTSA,
                DigiCert, an eIDAS QTSP). Independent third-party attestation.

All providers expose the same surface:
    anchor(digest_hex) -> anchor dict
    verify(anchor, digest_hex) -> {valid, gen_time, tsa, chain_verified, error}
"""
from __future__ import annotations

import base64
import hashlib
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Optional

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

from core.config import settings

TSA_DOMAIN_PREFIX = "PFP_TSA_V1::"
ENVELOPE_VERSION = "1"


def _load_pinned_tsa_roots():
    """Load pinned RFC-3161 TSA trust anchors from ``settings.TSA_ROOT_BUNDLE``.

    Accepts an inline PEM string or a filesystem path. Returns a list of
    ``cryptography`` x509 Certificate objects (empty when unconfigured/invalid).
    """
    bundle = getattr(settings, "TSA_ROOT_BUNDLE", "") or ""
    if not bundle:
        return []
    try:
        if "-----BEGIN" in bundle:
            data = bundle.encode("utf-8")
        elif os.path.exists(bundle):
            with open(bundle, "rb") as fh:
                data = fh.read()
        else:
            return []
        from cryptography import x509
        return x509.load_pem_x509_certificates(data)
    except Exception:  # noqa: BLE001
        return []


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class TimeAnchorError(RuntimeError):
    pass


class TimeAnchorProvider(ABC):
    name: str = "abstract"
    independent: bool = False  # True only for genuine third-party time sources

    @abstractmethod
    def anchor(self, digest_hex: str) -> Dict:
        ...

    @abstractmethod
    def verify(self, anchor: Dict, digest_hex: str) -> Dict:
        ...

    def profile(self) -> Dict:
        return {"provider": self.name, "independent": self.independent}


class LocalTimeAnchorProvider(TimeAnchorProvider):
    """PFP Local Time Authority — DEV/TEST only, offline & deterministic.

    Signs ``PFP_TSA_V1::<alg>:<digest>@<gen_time>`` with an Ed25519 key derived
    from ``TIME_ANCHOR_LOCAL_SEED``. The TSA public key is embedded in the anchor
    so it is fully self-verifying offline (mirrors shipping a TSA certificate).
    NOT an independent third party — clearly labelled so trust tiers stay honest.
    """

    name = "local"
    independent = False
    _TSA_NAME = "PFP Local Time Authority (DEV/TEST — not an independent RFC-3161 TSA)"

    def __init__(self) -> None:
        seed_b64 = settings.TIME_ANCHOR_LOCAL_SEED
        if not seed_b64:
            raise TimeAnchorError("TIME_ANCHOR_LOCAL_SEED not set")
        seed = base64.b64decode(seed_b64)
        if len(seed) != 32:
            raise TimeAnchorError("TIME_ANCHOR_LOCAL_SEED must be 32 bytes (base64)")
        self._sk = SigningKey(seed)
        pub = bytes(self._sk.verify_key)
        self._pub_b64 = base64.b64encode(pub).decode("ascii")
        self._tsa_key_id = "tsa_" + hashlib.sha256(pub).hexdigest()[:16]

    @staticmethod
    def _message(hash_alg: str, digest_hex: str, gen_time: str) -> bytes:
        return f"{TSA_DOMAIN_PREFIX}{hash_alg}:{digest_hex}@{gen_time}".encode("utf-8")

    def anchor(self, digest_hex: str) -> Dict:
        gen_time = _now_iso()
        sig = self._sk.sign(self._message("sha256", digest_hex, gen_time)).signature
        return {
            "type": "local",
            "hash_alg": "sha256",
            "digest": digest_hex,
            "gen_time": gen_time,
            "token": base64.b64encode(sig).decode("ascii"),
            "tsa_key_id": self._tsa_key_id,
            "tsa_public_key": self._pub_b64,
            "tsa_name": self._TSA_NAME,
        }

    def verify(self, anchor: Dict, digest_hex: str) -> Dict:
        out = {"valid": False, "gen_time": anchor.get("gen_time"),
               "tsa": anchor.get("tsa_name"), "chain_verified": True, "error": None}
        try:
            if anchor.get("digest") != digest_hex:
                out["error"] = "digest mismatch: anchor does not bind this proof's fea_hash"
                return out
            vk = VerifyKey(base64.b64decode(anchor["tsa_public_key"]))
            msg = self._message(anchor.get("hash_alg", "sha256"), digest_hex, anchor["gen_time"])
            vk.verify(msg, base64.b64decode(anchor["token"]))
            out["valid"] = True
        except (BadSignatureError, KeyError, ValueError, Exception) as e:  # noqa: BLE001
            out["error"] = f"local anchor verification failed: {e}"
        return out


class Rfc3161Provider(TimeAnchorProvider):
    """Real RFC-3161 Timestamp Authority over HTTP. Independent third party.

    Sends the proof's ``fea_hash`` (as data) to the TSA; the library computes the
    messageImprint = SHA-256(fea_hash). Stores the full TimeStampResponse (DER).
    Verification reconstructs the imprint and confirms it binds the proof; full
    certificate-chain trust is established when a TSA root/cert is configured.
    """

    name = "rfc3161"
    independent = True

    def __init__(self) -> None:
        self._url = settings.TSA_URL
        if not self._url:
            raise TimeAnchorError("TSA_URL not set for rfc3161 provider")

    def anchor(self, digest_hex: str) -> Dict:
        import requests
        from rfc3161_client import TimestampRequestBuilder, decode_timestamp_response

        data = digest_hex.encode("utf-8")
        req = TimestampRequestBuilder().data(data).cert_req(True).build()
        resp = requests.post(
            self._url, data=req.as_bytes(),
            headers={"Content-Type": "application/timestamp-query"}, timeout=20,
        )
        resp.raise_for_status()
        decoded = decode_timestamp_response(resp.content)
        tst_info = decoded.tst_info
        gen_time = tst_info.gen_time
        if isinstance(gen_time, datetime):
            gen_time = gen_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        return {
            "type": "rfc3161",
            "hash_alg": "sha256",
            "digest": digest_hex,
            "gen_time": str(gen_time),
            "token": base64.b64encode(decoded.as_bytes()).decode("ascii"),
            "tsa_url": self._url,
            "tsa_name": self._url,
        }

    def verify(self, anchor: Dict, digest_hex: str) -> Dict:
        out = {"valid": False, "gen_time": anchor.get("gen_time"),
               "tsa": anchor.get("tsa_name"), "chain_verified": False, "error": None}
        try:
            from rfc3161_client import decode_timestamp_response
            if anchor.get("digest") != digest_hex:
                out["error"] = "digest mismatch: anchor does not bind this proof's fea_hash"
                return out
            decoded = decode_timestamp_response(base64.b64decode(anchor["token"]))
            tst_info = decoded.tst_info
            # Bind check: messageImprint must equal SHA-256(fea_hash bytes).
            expected = hashlib.sha256(digest_hex.encode("utf-8")).digest()
            imprint = tst_info.message_imprint
            got = getattr(imprint, "message", None) or getattr(imprint, "digest", None) or bytes(imprint)
            if not isinstance(got, (bytes, bytearray)):
                got = bytes(got)
            if got != expected:
                out["error"] = "messageImprint does not match fea_hash"
                return out
            out["valid"] = True  # imprint + structure valid; chain trust below

            # Full certificate-chain verification against pinned TSA roots.
            # When TSA_ROOT_BUNDLE is configured, confirm the TST signing
            # certificate chains to a pinned root -> chain_verified=True.
            roots = _load_pinned_tsa_roots()
            if roots:
                try:
                    from cryptography.hazmat.primitives.serialization import Encoding
                    from rfc3161_client import VerifierBuilder

                    builder = VerifierBuilder()
                    for cert in roots:
                        pem = cert.public_bytes(Encoding.PEM)
                        if cert.issuer == cert.subject:
                            builder = builder.add_root_certificate(pem)
                        else:
                            builder = builder.add_intermediate_certificate(pem)
                    verifier = builder.build()
                    verifier.verify(decoded, digest_hex.encode("utf-8"))
                    out["chain_verified"] = True
                except Exception as ce:  # noqa: BLE001
                    out["chain_note"] = f"chain not verified against pinned roots: {ce}"
        except Exception as e:  # noqa: BLE001
            out["error"] = f"rfc3161 anchor verification failed: {e}"
        return out


_PROVIDERS: Dict[str, TimeAnchorProvider] = {}


def get_time_anchor_provider(provider_name: Optional[str] = None) -> TimeAnchorProvider:
    name = (provider_name or settings.TIME_ANCHOR_PROVIDER or "local").lower()
    if name not in _PROVIDERS:
        if name == "local":
            _PROVIDERS[name] = LocalTimeAnchorProvider()
        elif name == "rfc3161":
            _PROVIDERS[name] = Rfc3161Provider()
        else:
            raise TimeAnchorError(f"Unknown TIME_ANCHOR_PROVIDER: {name}")
    return _PROVIDERS[name]


def provider_for_anchor(anchor: Dict) -> TimeAnchorProvider:
    """Resolve the verifier provider by the anchor's own type (anchors are
    self-describing, so verification works regardless of the active issuer
    provider)."""
    atype = (anchor.get("type") or "local").lower()
    return get_time_anchor_provider(atype)
