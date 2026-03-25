"""API key authentication middleware."""
import os
import hashlib
import secrets
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

# API Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Store hashed API keys (in production, use database)
# Format: {hashed_key: {"name": "...", "created_at": "..."}}
_api_keys: dict = {}
_test_key: str | None = None


def hash_api_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_test_api_key() -> str:
    """Generate a test API key on startup."""
    global _test_key
    if _test_key is None:
        _test_key = f"pfp_test_{secrets.token_hex(24)}"
        _api_keys[hash_api_key(_test_key)] = {
            "name": "test_key",
            "created_at": "startup"
        }
    return _test_key


def get_test_api_key() -> str:
    """Get the current test API key."""
    if _test_key is None:
        generate_test_api_key()
    return _test_key


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify the API key from request header."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header."
        )
    
    hashed = hash_api_key(api_key)
    if hashed not in _api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return api_key


def add_api_key(key: str, name: str):
    """Add a new API key."""
    _api_keys[hash_api_key(key)] = {
        "name": name,
        "created_at": "manual"
    }
