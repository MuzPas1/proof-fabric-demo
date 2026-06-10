"""User management and admin seeding."""
import uuid
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.passwords import hash_password, verify_password
from auth.rbac import Role
from models.auth_models import User


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[User]:
    doc = await db.users.find_one({"email": email.lower()}, {"_id": 0})
    return User(**doc) if doc else None


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[User]:
    doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return User(**doc) if doc else None


async def create_user(
    db: AsyncIOMotorDatabase,
    email: str,
    password: str,
    role: str,
    tenant_id: str,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        tenant_id=tenant_id,
    )
    await db.users.insert_one(user.model_dump())
    return user


async def authenticate(db: AsyncIOMotorDatabase, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user or user.status != "active":
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def seed_admin(
    db: AsyncIOMotorDatabase, email: str, password: str, tenant_id: str
) -> None:
    """Idempotent admin seeding; updates password hash if env password changed."""
    if not password:
        return
    existing = await db.users.find_one({"email": email.lower()})
    if existing is None:
        await create_user(db, email, password, Role.SUPER_ADMIN.value, tenant_id)
    elif not verify_password(password, existing.get("password_hash", "")):
        await db.users.update_one(
            {"email": email.lower()},
            {"$set": {"password_hash": hash_password(password)}},
        )
