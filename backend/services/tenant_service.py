"""Tenant management for multi-tenant isolation."""
import re
import uuid
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from models.auth_models import Tenant


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or uuid.uuid4().hex[:8]


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.tenants.create_index("tenant_id", unique=True)


async def ensure_tenant(db: AsyncIOMotorDatabase, tenant_id: str, name: str) -> Tenant:
    existing = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if existing:
        return Tenant(**existing)
    tenant = Tenant(tenant_id=tenant_id, name=name)
    await db.tenants.insert_one(tenant.model_dump())
    return tenant


async def create_tenant(
    db: AsyncIOMotorDatabase, name: str, tenant_id: Optional[str] = None
) -> Tenant:
    tid = tenant_id or _slugify(name)
    if await db.tenants.find_one({"tenant_id": tid}):
        tid = f"{tid}-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(tenant_id=tid, name=name)
    await db.tenants.insert_one(tenant.model_dump())
    return tenant


async def list_tenants(db: AsyncIOMotorDatabase) -> List[dict]:
    cursor = db.tenants.find({}, {"_id": 0}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def get_tenant(db: AsyncIOMotorDatabase, tenant_id: str) -> Optional[Tenant]:
    doc = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    return Tenant(**doc) if doc else None
