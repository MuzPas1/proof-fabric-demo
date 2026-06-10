"""DB-backed API key management.

Keys are stored as SHA-256 hashes only. The raw key is returned once at
creation. Supports tenant/customer assignment, scopes, expiration, and
revocation. Replaces the previous in-memory dict so the backend can scale
horizontally (multiple workers / replicas share the same key store).
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from models.auth_models import ApiKeyRecord

DEFAULT_SCOPES = ["fea:write", "fea:read", "fea:verify", "webhooks:manage"]


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _generate_raw_key() -> str:
    return f"pfp_live_{secrets.token_hex(24)}"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.api_keys.create_index("key_id", unique=True)
    await db.api_keys.create_index("key_hash", unique=True)
    await db.api_keys.create_index("tenant_id")


async def create_api_key(
    db: AsyncIOMotorDatabase,
    name: str,
    tenant_id: str,
    customer_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    expires_in_days: Optional[int] = None,
    created_by: Optional[str] = None,
    raw_key: Optional[str] = None,
) -> tuple[ApiKeyRecord, str]:
    raw = raw_key or _generate_raw_key()
    expires_at = None
    if expires_in_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()

    record = ApiKeyRecord(
        key_id=str(uuid.uuid4()),
        key_hash=hash_api_key(raw),
        name=name,
        tenant_id=tenant_id,
        customer_id=customer_id,
        scopes=scopes or DEFAULT_SCOPES,
        prefix=raw[:16],
        created_by=created_by,
        expires_at=expires_at,
    )
    await db.api_keys.insert_one(record.model_dump())
    return record, raw


async def resolve_api_key(db: AsyncIOMotorDatabase, raw_key: str) -> Optional[ApiKeyRecord]:
    """Return the active, non-expired key record for a raw key, or None."""
    doc = await db.api_keys.find_one({"key_hash": hash_api_key(raw_key)}, {"_id": 0})
    if not doc:
        return None
    record = ApiKeyRecord(**doc)
    if record.status != "active":
        return None
    if record.expires_at:
        try:
            if datetime.fromisoformat(record.expires_at) < datetime.now(timezone.utc):
                return None
        except ValueError:
            pass
    return record


async def touch_last_used(db: AsyncIOMotorDatabase, key_id: str) -> None:
    await db.api_keys.update_one(
        {"key_id": key_id},
        {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}},
    )


async def revoke_api_key(db: AsyncIOMotorDatabase, key_id: str) -> bool:
    result = await db.api_keys.update_one(
        {"key_id": key_id}, {"$set": {"status": "revoked"}}
    )
    return result.modified_count > 0


async def list_api_keys(
    db: AsyncIOMotorDatabase, tenant_id: Optional[str] = None
) -> List[dict]:
    query = {"tenant_id": tenant_id} if tenant_id else {}
    cursor = db.api_keys.find(query, {"_id": 0, "key_hash": 0}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def ensure_sandbox_key(db: AsyncIOMotorDatabase, raw_key: str, tenant_id: str) -> None:
    """Idempotently seed the sandbox key (dev only) into the DB store."""
    await ensure_static_key(db, raw_key, "sandbox", tenant_id, DEFAULT_SCOPES, "system")


async def ensure_static_key(
    db: AsyncIOMotorDatabase,
    raw_key: str,
    name: str,
    tenant_id: str,
    scopes: List[str],
    created_by: str = "system",
) -> None:
    """Idempotently seed a deterministic key (from config) with explicit scopes."""
    if not raw_key:
        return
    existing = await db.api_keys.find_one({"key_hash": hash_api_key(raw_key)})
    if existing is None:
        await create_api_key(
            db, name=name, tenant_id=tenant_id, scopes=scopes,
            created_by=created_by, raw_key=raw_key,
        )
