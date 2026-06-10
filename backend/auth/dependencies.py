"""FastAPI dependencies for JWT auth, RBAC, and API-key auth."""
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from auth.jwt_tokens import decode_token
from auth.rbac import Permission, role_has_permission, is_super_admin
from models.auth_models import ApiKeyRecord, User
from services import api_key_service, user_service

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _db():
    from server import db
    return db


# --------------------------------------------------------------------------
# JWT / user auth (control plane)
# --------------------------------------------------------------------------
async def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    token = creds.credentials if creds else request.cookies.get("access_token")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(token, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    user = await user_service.get_user_by_id(_db(), payload["sub"])
    if not user or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require_permission(permission: Permission):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if not role_has_permission(user.role, permission):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role '{user.role}' lacks permission '{permission.value}'",
            )
        return user
    return _dep


def resolve_tenant_scope(user: User, requested_tenant: Optional[str]) -> str:
    """Super admins may target any tenant via X-Tenant-Id; others are locked
    to their own tenant."""
    if is_super_admin(user.role):
        return requested_tenant or user.tenant_id
    if requested_tenant and requested_tenant != user.tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")
    return user.tenant_id


# --------------------------------------------------------------------------
# API-key auth (data plane)
# --------------------------------------------------------------------------
async def require_api_key(api_key: Optional[str] = Depends(api_key_header)) -> ApiKeyRecord:
    if not api_key:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing API key. Provide X-API-Key header."
        )
    record = await api_key_service.resolve_api_key(_db(), api_key)
    if not record:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired API key")
    await api_key_service.touch_last_used(_db(), record.key_id)
    return record


def require_scope(scope: str):
    async def _dep(key: ApiKeyRecord = Depends(require_api_key)) -> ApiKeyRecord:
        if scope not in key.scopes:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"API key missing scope '{scope}'"
            )
        return key
    return _dep
