"""Key management service with persistent storage.

KEY REGISTRY RULES:
- Keys stored in MongoDB (persistent)
- Keys are NEVER deleted (immutability)
- Status can change: active → retired
- Old FEAs remain verifiable with old keys
"""
import base64
from datetime import datetime, timezone
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.key_registry import PublicKeyInfo
from crypto.signing import get_public_key_id, get_public_key_b64


# In-memory cache (populated from DB on startup)
_key_cache: dict = {}
_db: Optional[AsyncIOMotorDatabase] = None


async def initialize_key_registry(db: AsyncIOMotorDatabase):
    """
    Initialize key registry with database connection.
    - Creates unique index on public_key_id
    - Loads existing keys into cache
    - Registers current key if not present
    """
    global _db, _key_cache
    _db = db
    
    # Create unique index on public_key_id
    await db.key_registry.create_index("public_key_id", unique=True)
    
    # Load all keys into cache
    async for key_doc in db.key_registry.find({}, {"_id": 0}):
        _key_cache[key_doc["public_key_id"]] = PublicKeyInfo(**key_doc)
    
    # Register current key if not already present
    try:
        current_key_id = get_public_key_id()
        current_public_key = get_public_key_b64()
        
        if current_key_id not in _key_cache:
            await register_key(current_key_id, current_public_key)
    except Exception as e:
        # Key not configured yet - that's OK
        pass


async def register_key(public_key_id: str, public_key: str, status: str = "active") -> PublicKeyInfo:
    """
    Register a new key in the persistent registry.
    Keys are immutable once created.
    """
    global _db, _key_cache
    
    key_info = PublicKeyInfo(
        public_key_id=public_key_id,
        public_key=public_key,
        algorithm="Ed25519",
        created_at=datetime.now(timezone.utc).isoformat(),
        status=status
    )
    
    # Store in database (upsert to handle race conditions)
    await _db.key_registry.update_one(
        {"public_key_id": public_key_id},
        {"$setOnInsert": key_info.model_dump()},
        upsert=True
    )
    
    # Update cache
    _key_cache[public_key_id] = key_info
    
    return key_info


async def get_key_by_id(public_key_id: str) -> Optional[PublicKeyInfo]:
    """
    Get a key by ID from persistent storage.
    Falls back to database if not in cache.
    """
    global _db, _key_cache
    
    # Check cache first
    if public_key_id in _key_cache:
        return _key_cache[public_key_id]
    
    # Fall back to database
    if _db is not None:
        key_doc = await _db.key_registry.find_one(
            {"public_key_id": public_key_id},
            {"_id": 0}
        )
        if key_doc:
            key_info = PublicKeyInfo(**key_doc)
            _key_cache[public_key_id] = key_info
            return key_info
    
    return None


async def get_public_key_bytes_by_id(public_key_id: str) -> Optional[bytes]:
    """Get public key bytes by ID for verification."""
    key_info = await get_key_by_id(public_key_id)
    if key_info:
        return base64.b64decode(key_info.public_key)
    return None


async def retire_key(public_key_id: str) -> bool:
    """
    Retire a key (mark as inactive).
    Key remains in registry for verification of old FEAs.
    NEVER deletes the key.
    """
    global _db, _key_cache
    
    if _db is None:
        return False
    
    result = await _db.key_registry.update_one(
        {"public_key_id": public_key_id},
        {"$set": {"status": "retired"}}
    )
    
    # Update cache
    if public_key_id in _key_cache:
        _key_cache[public_key_id].status = "retired"
    
    return result.modified_count > 0


async def rotate_key(new_public_key_id: str, new_public_key: str) -> PublicKeyInfo:
    """
    Rotate to a new key:
    1. Retire all currently active keys
    2. Register the new key as active
    """
    global _db, _key_cache
    
    # Retire all active keys
    await _db.key_registry.update_many(
        {"status": "active"},
        {"$set": {"status": "retired"}}
    )
    
    # Update cache
    for key_id, key_info in _key_cache.items():
        if key_info.status == "active":
            key_info.status = "retired"
    
    # Register new key
    return await register_key(new_public_key_id, new_public_key, status="active")


async def get_all_keys() -> List[PublicKeyInfo]:
    """
    Get all keys from persistent storage.
    Returns both active and retired keys (for verification).
    """
    global _db, _key_cache
    
    if _db is not None:
        # Refresh cache from database
        _key_cache.clear()
        async for key_doc in _db.key_registry.find({}, {"_id": 0}):
            _key_cache[key_doc["public_key_id"]] = PublicKeyInfo(**key_doc)
    
    return list(_key_cache.values())


def get_all_public_keys() -> List[PublicKeyInfo]:
    """
    Synchronous version for compatibility.
    Returns cached keys.
    """
    return list(_key_cache.values())


# Backward compatibility functions
def get_public_key_by_id(key_id: str) -> Optional[PublicKeyInfo]:
    """Synchronous version - uses cache only."""
    return _key_cache.get(key_id)


def add_key_to_registry(key_info: PublicKeyInfo):
    """Synchronous version - updates cache only (use register_key for persistence)."""
    _key_cache[key_info.public_key_id] = key_info


def deactivate_key(key_id: str):
    """Synchronous version - updates cache only (use retire_key for persistence)."""
    if key_id in _key_cache:
        _key_cache[key_id].status = "retired"
