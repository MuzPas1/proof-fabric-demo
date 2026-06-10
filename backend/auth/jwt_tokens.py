"""JWT access/refresh token issuance and verification (PyJWT, HS256)."""
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt

from core.config import settings


def _secret() -> str:
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not configured")
    return settings.JWT_SECRET


def create_access_token(user_id: str, email: str, role: str, tenant_id: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "tenant_id": tenant_id,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MIN),
    }
    return jwt.encode(payload, _secret(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: Optional[str] = None) -> dict:
    """Decode + validate a JWT. Raises jwt exceptions on failure."""
    payload = jwt.decode(token, _secret(), algorithms=[settings.JWT_ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected token type {expected_type}")
    return payload
