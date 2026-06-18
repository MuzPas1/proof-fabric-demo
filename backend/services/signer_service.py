"""Per-tenant signer configuration (BYOS).

Stores one signer config per tenant in the ``signers`` collection. The default
tenant (and any tenant without a config) uses the platform LocalSigner —
preserving existing Ed25519 behaviour. When a remote / cloud-KMS signer is
configured, its PUBLIC key is registered in the key registry so verification
stays fully independent of signer availability.

Secrets (e.g. ``auth_header``) are stored but NEVER returned by list/get APIs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.signers import Signer, LocalSigner, build_signer
from core.config import settings
from crypto import suites
from services import key_service

_PUBLIC_FIELDS = ("tenant_id", "type", "algorithm", "endpoint", "provider",
                  "key_ref", "public_key_id", "created_at", "updated_at")


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.signers.create_index("tenant_id", unique=True)


def _sanitize(doc: dict) -> dict:
    return {k: doc.get(k) for k in _PUBLIC_FIELDS if doc.get(k) is not None}


async def configure_signer(db: AsyncIOMotorDatabase, tenant_id: str, config: dict) -> dict:
    """Validate + persist a tenant signer config; register its public key.

    Raises ValueError on invalid config.
    """
    stype = (config.get("type") or "local").lower()
    if stype not in ("local", "remote", "cloud-kms"):
        raise ValueError(f"Unknown signer type: {stype}")
    alg = suites.normalize_algorithm(config.get("algorithm", "Ed25519"))
    if not suites.is_supported(alg):
        raise ValueError(f"Unsupported algorithm: {alg}")

    record = {"tenant_id": tenant_id, "type": stype, "algorithm": alg,
              "updated_at": datetime.now(timezone.utc).isoformat()}

    if stype == "remote":
        if not config.get("endpoint") or not config.get("public_key"):
            raise ValueError("remote signer requires 'endpoint' and 'public_key'")
        record["endpoint"] = config["endpoint"]
        record["public_key"] = config["public_key"]
        if config.get("auth_header"):
            record["auth_header"] = config["auth_header"]
        record["timeout"] = float(config.get("timeout", 8.0))
    elif stype == "cloud-kms":
        if not config.get("provider") or not config.get("key_ref") or not config.get("public_key"):
            raise ValueError("cloud-kms signer requires 'provider', 'key_ref' and 'public_key'")
        record["provider"] = config["provider"]
        record["key_ref"] = config["key_ref"]
        record["public_key"] = config["public_key"]
    else:  # local
        record["logical"] = config.get("logical", "production")

    # Build the signer to derive + register its public key, and to validate it.
    signer = build_signer({**record})
    kid = signer.public_key_id()
    record["public_key_id"] = kid
    await key_service.register_key(kid, signer.public_key_b64(), status="active", algorithm=alg)

    existing = await db.signers.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not existing:
        record["created_at"] = record["updated_at"]
    await db.signers.update_one({"tenant_id": tenant_id}, {"$set": record}, upsert=True)
    return _sanitize(record)


async def get_signer_config(db: AsyncIOMotorDatabase, tenant_id: str) -> Optional[dict]:
    return await db.signers.find_one({"tenant_id": tenant_id}, {"_id": 0})


async def list_signers(db: AsyncIOMotorDatabase, tenant_id: Optional[str] = None) -> List[dict]:
    query = {"tenant_id": tenant_id} if tenant_id else {}
    out = []
    async for doc in db.signers.find(query, {"_id": 0}):
        out.append(_sanitize(doc))
    return out


async def delete_signer(db: AsyncIOMotorDatabase, tenant_id: str) -> bool:
    res = await db.signers.delete_one({"tenant_id": tenant_id})
    return res.deleted_count > 0


async def resolve_signer(db: AsyncIOMotorDatabase, tenant_id: str, default_suite: str = "Ed25519") -> Signer:
    """Resolve the active signer for a tenant.

    BYOS off → always the platform LocalSigner with the requested suite.
    BYOS on  → the tenant's configured signer, else LocalSigner(default_suite).
    """
    if settings.ENABLE_BYOS:
        cfg = await get_signer_config(db, tenant_id)
        if cfg:
            return build_signer(cfg)
    return LocalSigner(logical="production", algorithm=default_suite)


async def signers_health(db: AsyncIOMotorDatabase) -> dict:
    """Health summary of the default signer + all configured tenant signers."""
    default = LocalSigner().health()
    tenants = []
    async for doc in db.signers.find({}, {"_id": 0}):
        try:
            tenants.append({"tenant_id": doc["tenant_id"], **build_signer(doc).health()})
        except Exception as e:
            tenants.append({"tenant_id": doc.get("tenant_id"), "available": False, "error": str(e)})
    return {"byos_enabled": settings.ENABLE_BYOS, "default_signer": default, "tenant_signers": tenants}
