"""Control-plane authentication routes (/api/auth)."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

import jwt as pyjwt

from auth.jwt_tokens import create_access_token, create_refresh_token, decode_token
from auth.dependencies import get_current_user
from models.auth_models import LoginRequest, TokenResponse, User
from services import user_service

router = APIRouter(prefix="/auth", tags=["Auth"])


def _db():
    from server import db
    return db


def _set_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie("access_token", access, httponly=True, secure=False,
                        samesite="lax", max_age=1800, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=False,
                        samesite="lax", max_age=604800, path="/")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response):
    user = await user_service.authenticate(_db(), body.email, body.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    access = create_access_token(user.user_id, user.email, user.role, user.tenant_id)
    refresh = create_refresh_token(user.user_id)
    _set_cookies(response, access, refresh)
    return TokenResponse(
        access_token=access, refresh_token=refresh, role=user.role,
        tenant_id=user.tenant_id, email=user.email,
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "user_id": user.user_id, "email": user.email,
        "role": user.role, "tenant_id": user.tenant_id, "status": user.status,
    }


@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")
    try:
        payload = decode_token(token, expected_type="refresh")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = await user_service.get_user_by_id(_db(), payload["sub"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    access = create_access_token(user.user_id, user.email, user.role, user.tenant_id)
    response.set_cookie("access_token", access, httponly=True, secure=False,
                        samesite="lax", max_age=1800, path="/")
    return {"access_token": access, "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response, user: User = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"status": "logged_out"}
