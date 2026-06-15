"""KMS abstraction layer for signing-key management.

Removes the hard dependency on a single plaintext key. The signing key
material is resolved through a pluggable provider selected by the
``KMS_PROVIDER`` environment variable:

    local   -> Ed25519 seed read from env (development / sandbox ONLY)
    aws     -> seed retrieved from AWS Secrets Manager (boto3)
    gcp     -> seed retrieved from GCP Secret Manager
    azure   -> seed retrieved from Azure Key Vault

Logical key names used by the platform:
    "production" -> signs production FEAs            (env: PRIVATE_KEY)
    "demo"       -> signs demo / sandbox artifacts   (env: DEMO_PRIVATE_KEY)

For the cloud providers, the key material is stored in the cloud secret
store and pulled at process start; signing happens locally with libsodium
(Ed25519 is not natively signable on every cloud HSM). This keeps the
cryptographic primitive identical across environments while removing
plaintext-on-disk in production. The cloud providers raise a clear
``KMSNotConfigured`` error when their SDK/credentials are absent so the
operator gets actionable feedback rather than a silent fallback.
"""
from __future__ import annotations

import base64
import hashlib
import os
from abc import ABC, abstractmethod
from typing import Dict, Optional

from nacl.signing import SigningKey

from core.config import settings


class KMSNotConfigured(RuntimeError):
    """Raised when a KMS provider is selected but not properly configured."""


def _public_key_id_from_seed(signing_key: SigningKey) -> str:
    pub = bytes(signing_key.verify_key)
    return "key_" + hashlib.sha256(pub).hexdigest()[:16]


class KMSProvider(ABC):
    """Abstract signing-key provider."""

    name: str = "abstract"
    # How key material is handled by this provider:
    #   "seed-env"    -> Ed25519 seed read from an environment variable (dev/sandbox)
    #   "seed-import" -> Ed25519 seed pulled from a cloud secret store, signed locally
    #   "native"      -> private key never leaves the HSM/KMS; signing is remote
    mode: str = "seed"
    algorithm: str = "Ed25519"
    # True only for providers whose private key never leaves the HSM/KMS.
    native_sign: bool = False

    # Logical key names the platform expects to resolve.
    LOGICAL_KEYS = ("production", "demo")

    @abstractmethod
    def get_signing_key(self, logical_name: str) -> SigningKey:
        ...

    def get_public_key_bytes(self, logical_name: str) -> bytes:
        return bytes(self.get_signing_key(logical_name).verify_key)

    def get_public_key_b64(self, logical_name: str) -> str:
        return base64.b64encode(self.get_public_key_bytes(logical_name)).decode("ascii")

    def get_public_key_id(self, logical_name: str) -> str:
        return _public_key_id_from_seed(self.get_signing_key(logical_name))

    def sign(self, logical_name: str, message: bytes) -> bytes:
        """Sign ``message`` for ``logical_name``.

        The default implementation materializes the seed and signs locally with
        libsodium. A future native-HSM provider overrides this so the private
        key never leaves the secure boundary, WITHOUT any caller changes — all
        signing in the platform flows through this method.
        """
        return self.get_signing_key(logical_name).sign(message).signature

    def status(self) -> Dict[str, object]:
        """Non-secret readiness summary for health/observability surfaces.

        NEVER returns key material — only which logical keys resolve and the
        provider's capability profile.
        """
        keys: Dict[str, bool] = {}
        for logical in self.LOGICAL_KEYS:
            try:
                self.get_signing_key(logical)
                keys[logical] = True
            except Exception:
                keys[logical] = False
        return {
            "provider": self.name,
            "mode": self.mode,
            "algorithm": self.algorithm,
            "native_sign": self.native_sign,
            "logical_keys": keys,
            "ready": all(keys.values()),
        }


class LocalKMSProvider(KMSProvider):
    """Reads Ed25519 seeds from environment variables. Development only."""

    name = "local"
    mode = "seed-env"
    _ENV_MAP = {"production": "PRIVATE_KEY", "demo": "DEMO_PRIVATE_KEY"}

    def __init__(self) -> None:
        self._cache: Dict[str, SigningKey] = {}

    def get_signing_key(self, logical_name: str) -> SigningKey:
        if logical_name in self._cache:
            return self._cache[logical_name]
        env_key = self._ENV_MAP.get(logical_name)
        if not env_key:
            raise KMSNotConfigured(f"Unknown logical key: {logical_name}")
        b64 = os.environ.get(env_key)
        if not b64:
            raise KMSNotConfigured(f"{env_key} environment variable not set")
        seed = base64.b64decode(b64)
        if len(seed) == 64:
            seed = seed[:32]
        key = SigningKey(seed)
        self._cache[logical_name] = key
        return key


class _SecretBackedProvider(KMSProvider):
    """Shared logic for cloud providers that fetch an Ed25519 seed (b64) from
    a cloud secret store and sign locally."""

    mode = "seed-import"

    def __init__(self) -> None:
        self._cache: Dict[str, SigningKey] = {}

    def _secret_ref(self, logical_name: str) -> Optional[str]:
        return os.environ.get(f"{self.name.upper()}_KEY_REF_{logical_name.upper()}")

    @abstractmethod
    def _fetch_secret(self, ref: str) -> str:
        ...

    def get_signing_key(self, logical_name: str) -> SigningKey:
        if logical_name in self._cache:
            return self._cache[logical_name]
        ref = self._secret_ref(logical_name)
        if not ref:
            raise KMSNotConfigured(
                f"{self.name.upper()}_KEY_REF_{logical_name.upper()} not set"
            )
        seed = base64.b64decode(self._fetch_secret(ref))
        if len(seed) == 64:
            seed = seed[:32]
        key = SigningKey(seed)
        self._cache[logical_name] = key
        return key


class AwsKmsProvider(_SecretBackedProvider):
    name = "aws"

    def _fetch_secret(self, ref: str) -> str:
        try:
            import boto3  # noqa
        except ImportError as e:  # pragma: no cover
            raise KMSNotConfigured("boto3 not installed for AWS provider") from e
        try:
            client = boto3.client("secretsmanager")
            resp = client.get_secret_value(SecretId=ref)
            return resp["SecretString"]
        except Exception as e:  # pragma: no cover
            raise KMSNotConfigured(f"AWS Secrets Manager fetch failed: {e}") from e


class GcpKmsProvider(_SecretBackedProvider):
    name = "gcp"

    def _fetch_secret(self, ref: str) -> str:  # pragma: no cover
        try:
            from google.cloud import secretmanager  # noqa
        except ImportError as e:
            raise KMSNotConfigured("google-cloud-secret-manager not installed") from e
        try:
            client = secretmanager.SecretManagerServiceClient()
            resp = client.access_secret_version(name=ref)
            return resp.payload.data.decode("utf-8")
        except Exception as e:
            raise KMSNotConfigured(f"GCP Secret Manager fetch failed: {e}") from e


class AzureKeyVaultProvider(_SecretBackedProvider):
    name = "azure"

    def _fetch_secret(self, ref: str) -> str:  # pragma: no cover
        try:
            from azure.identity import DefaultAzureCredential  # noqa
            from azure.keyvault.secrets import SecretClient  # noqa
        except ImportError as e:
            raise KMSNotConfigured("azure-keyvault-secrets not installed") from e
        try:
            vault_url, secret_name = ref.split("#", 1)
            client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
            return client.get_secret(secret_name).value
        except Exception as e:
            raise KMSNotConfigured(f"Azure Key Vault fetch failed: {e}") from e


_PROVIDERS = {
    "local": LocalKMSProvider,
    "aws": AwsKmsProvider,
    "gcp": GcpKmsProvider,
    "azure": AzureKeyVaultProvider,
}

_provider_instance: Optional[KMSProvider] = None


def get_kms() -> KMSProvider:
    global _provider_instance
    if _provider_instance is None:
        cls = _PROVIDERS.get(settings.KMS_PROVIDER)
        if cls is None:
            raise KMSNotConfigured(f"Unknown KMS_PROVIDER: {settings.KMS_PROVIDER}")
        _provider_instance = cls()
    return _provider_instance


# Capability matrix for evaluator/operator surfaces (no secrets).
SUPPORTED_PROVIDERS = sorted(_PROVIDERS.keys())


def kms_status() -> Dict[str, object]:
    """Non-secret KMS readiness summary for /api/health and the dev portal.

    Reports the active provider, its capability mode, which logical signing
    keys resolve, and the set of providers this build can switch to with no
    code changes (config-only migration).
    """
    try:
        st = get_kms().status()
    except Exception as e:  # provider misconfigured — surface, don't crash
        st = {
            "provider": settings.KMS_PROVIDER,
            "mode": "unknown",
            "algorithm": "Ed25519",
            "native_sign": False,
            "logical_keys": {},
            "ready": False,
            "error": str(e),
        }
    st["supported_providers"] = SUPPORTED_PROVIDERS
    return st
