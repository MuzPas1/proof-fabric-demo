"""Key management service."""
import base64
from datetime import datetime, timezone
from typing import List

from models.key_registry import PublicKeyInfo
from crypto.signing import get_public_key_id, get_public_key_b64


# In-memory key registry (in production, this would be persistent)
# Maps public_key_id -> PublicKeyInfo
_key_registry: dict = {}
_initialized = False


def initialize_key_registry():
    """Initialize the key registry with the current key."""
    global _initialized
    if _initialized:
        return
    
    try:
        key_id = get_public_key_id()
        public_key = get_public_key_b64()
        
        _key_registry[key_id] = PublicKeyInfo(
            public_key_id=key_id,
            public_key=public_key,
            algorithm="Ed25519",
            created_at=datetime.now(timezone.utc).isoformat(),
            is_active=True
        )
        _initialized = True
    except Exception:
        # Key not configured yet
        pass


def get_all_public_keys() -> List[PublicKeyInfo]:
    """Get all public keys in the registry."""
    initialize_key_registry()
    return list(_key_registry.values())


def get_public_key_by_id(key_id: str) -> PublicKeyInfo | None:
    """Get a specific public key by ID."""
    initialize_key_registry()
    return _key_registry.get(key_id)


def get_public_key_bytes_by_id(key_id: str) -> bytes | None:
    """Get public key bytes by ID for verification."""
    initialize_key_registry()
    key_info = _key_registry.get(key_id)
    if key_info:
        return base64.b64decode(key_info.public_key)
    return None


def add_key_to_registry(key_info: PublicKeyInfo):
    """Add a new key to the registry (for key rotation)."""
    _key_registry[key_info.public_key_id] = key_info


def deactivate_key(key_id: str):
    """Deactivate a key (mark as inactive but keep for verification)."""
    if key_id in _key_registry:
        _key_registry[key_id].is_active = False
