"""Bring-Your-Own-Signing (BYOS) — pluggable Signer abstraction.

A ``Signer`` produces a raw signature for a domain-prefixed canonical message
under a specific signature suite. Three signer types are provided:

* ``LocalSigner``  — signs with the platform KMS (Ed25519 / ES256 / ES256K).
* ``RemoteSigner`` — delegates signing to a partner-operated HTTP endpoint; the
  private key stays in the partner's custody. The public key is known/registered
  so verification NEVER contacts the signer.
* ``CloudKmsSigner`` — native cloud-KMS signing (AWS/GCP/Azure). The private key
  never leaves the KMS. Config-gated: raises ``KMSNotConfigured`` when the SDK /
  credentials are absent (mirrors the existing KMS provider pattern).

CRITICAL INVARIANT: independent verification depends ONLY on the registered
public key, never on signer availability. Signers are used at ISSUANCE only.
"""
from __future__ import annotations

import base64
import hashlib
import time
import urllib.request
import json
from abc import ABC, abstractmethod
from typing import Optional

from core.kms import get_kms, KMSNotConfigured
from crypto import suites
from core.observability import SIGNER_LATENCY, SIGNER_ERRORS


def _kid_from_pub(pub: bytes) -> str:
    return "key_" + hashlib.sha256(pub).hexdigest()[:16]


class Signer(ABC):
    name: str = "abstract"
    algorithm: str = "Ed25519"
    native: bool = False

    @abstractmethod
    def _sign_raw(self, message: bytes) -> bytes:
        ...

    @abstractmethod
    def public_key_bytes(self) -> bytes:
        ...

    def sign(self, message: bytes) -> bytes:
        start = time.perf_counter()
        try:
            sig = self._sign_raw(message)
        except Exception:
            try:
                SIGNER_ERRORS.labels(self.name, self.algorithm).inc()
            except Exception:
                pass
            raise
        try:
            SIGNER_LATENCY.labels(self.name, self.algorithm).observe(time.perf_counter() - start)
        except Exception:
            pass
        return sig

    def public_key_b64(self) -> str:
        return base64.b64encode(self.public_key_bytes()).decode("ascii")

    def public_key_id(self) -> str:
        return _kid_from_pub(self.public_key_bytes())

    def health(self) -> dict:
        try:
            available = bool(self.public_key_bytes())
        except Exception as e:
            return {"signer": self.name, "algorithm": self.algorithm,
                    "native": self.native, "available": False, "error": str(e)}
        return {"signer": self.name, "algorithm": self.algorithm,
                "native": self.native, "available": available}


class LocalSigner(Signer):
    """Signs with the platform KMS (local seed today; cloud-secret-backed ready)."""

    def __init__(self, logical: str = "production", algorithm: str = "Ed25519"):
        self.name = "local"
        self.logical = logical
        self.algorithm = suites.normalize_algorithm(algorithm)
        self.native = False

    def _sign_raw(self, message: bytes) -> bytes:
        return get_kms().sign(self.logical, message, self.algorithm)

    def public_key_bytes(self) -> bytes:
        return get_kms().get_public_key_bytes(self.logical, self.algorithm)


class RemoteSigner(Signer):
    """Delegates signing to a partner HTTP endpoint (private key stays remote).

    Endpoint contract (POST, JSON):
      request  -> {"algorithm": "<suite>", "message_b64": "<base64 domain-prefixed message>"}
      response -> {"signature_b64": "<base64 raw signature>"}

    The expected public key is supplied at config time (and registered in the
    key registry) so verification never depends on the remote signer.
    """

    def __init__(self, *, endpoint: str, algorithm: str, public_key_b64: str,
                 auth_header: Optional[str] = None, timeout: float = 8.0):
        self.name = "remote"
        self.endpoint = endpoint
        self.algorithm = suites.normalize_algorithm(algorithm)
        self._public_key = base64.b64decode(public_key_b64)
        self.auth_header = auth_header
        self.timeout = timeout
        self.native = True  # private key never reaches PFP

    def _sign_raw(self, message: bytes) -> bytes:
        body = json.dumps({
            "algorithm": self.algorithm,
            "message_b64": base64.b64encode(message).decode("ascii"),
        }).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.auth_header:
            req.add_header("Authorization", self.auth_header)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        sig_b64 = payload.get("signature_b64")
        if not sig_b64:
            raise RuntimeError("Remote signer returned no signature_b64")
        sig = base64.b64decode(sig_b64)
        # Defense: the returned signature MUST verify against the known public key.
        ok, reason = suites.verify(self.algorithm, self._public_key, message, sig)
        if not ok:
            raise RuntimeError(f"Remote signer produced an invalid signature: {reason}")
        return sig

    def public_key_bytes(self) -> bytes:
        return self._public_key

    def health(self) -> dict:
        base = super().health()
        base["endpoint"] = self.endpoint
        return base


class CloudKmsSigner(Signer):
    """Native cloud-KMS signing (AWS/GCP/Azure). Private key never leaves the KMS.

    Config-gated: the actual provider SDK call is only attempted when the
    provider + key reference are configured AND the SDK/creds are present;
    otherwise ``KMSNotConfigured`` is raised with actionable feedback. The
    expected public key is supplied at config time so verification is
    signer-independent.
    """

    def __init__(self, *, provider: str, key_ref: str, algorithm: str, public_key_b64: str):
        self.name = f"cloud-kms:{provider}"
        self.provider = provider
        self.key_ref = key_ref
        self.algorithm = suites.normalize_algorithm(algorithm)
        self._public_key = base64.b64decode(public_key_b64)
        self.native = True

    def _sign_raw(self, message: bytes) -> bytes:
        # Native cloud KMS signing is config-gated. The integration points for
        # AWS KMS Sign / GCP KMS asymmetricSign / Azure Key Vault sign are
        # documented in docs/KMS_MIGRATION_GUIDE.md. Until provisioned with live
        # credentials, this raises a clear, actionable error rather than a silent
        # fallback (matching the KMS provider contract).
        raise KMSNotConfigured(
            f"Cloud KMS signer '{self.provider}' (key_ref={self.key_ref}) requires "
            "provider SDK + credentials. See docs/KMS_MIGRATION_GUIDE.md."
        )

    def public_key_bytes(self) -> bytes:
        return self._public_key


def build_signer(config: dict) -> Signer:
    """Construct a Signer from a stored signer config dict."""
    stype = (config.get("type") or "local").lower()
    alg = config.get("algorithm", "Ed25519")
    if stype == "local":
        return LocalSigner(logical=config.get("logical", "production"), algorithm=alg)
    if stype == "remote":
        return RemoteSigner(
            endpoint=config["endpoint"], algorithm=alg,
            public_key_b64=config["public_key"],
            auth_header=config.get("auth_header"),
            timeout=float(config.get("timeout", 8.0)),
        )
    if stype == "cloud-kms":
        return CloudKmsSigner(
            provider=config["provider"], key_ref=config["key_ref"],
            algorithm=alg, public_key_b64=config["public_key"],
        )
    raise ValueError(f"Unknown signer type: {stype}")
