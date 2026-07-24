"""Auth0 Universal Login (OAuth 2.0 / OIDC) routes.

PFP delegates ALL authentication to Auth0 and never manages passwords or
credentials. The backend owns login/callback/logout and keeps a minimal,
HTTP-only session cookie (Starlette SessionMiddleware). On a successful login
PFP additionally issues an independently verifiable "Identity Authenticated"
Proof Artifact via the shared provider pipeline.
"""
from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from core.config import settings

logger = logging.getLogger("pfp.auth0")
router = APIRouter(prefix="/auth0", tags=["Auth0 Identity"])

oauth = OAuth()
if settings.ENABLE_AUTH0:
    oauth.register(
        name="auth0",
        client_id=settings.AUTH0_CLIENT_ID,
        client_secret=settings.AUTH0_CLIENT_SECRET,
        server_metadata_url=f"https://{settings.AUTH0_DOMAIN}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email"},
    )


def _callback_url() -> str:
    return f"{settings.APP_BASE_URL.rstrip('/')}/api/auth0/callback"


@router.get("/config")
async def auth0_config():
    """Public: lets the frontend show/hide the Auth0 login affordance."""
    return {"enabled": settings.ENABLE_AUTH0}


@router.get("/login")
async def auth0_login(request: Request, returnTo: Optional[str] = None):
    if not settings.ENABLE_AUTH0:
        raise HTTPException(status_code=404, detail="Auth0 is not configured")
    request.session["auth0_return_to"] = returnTo or settings.APP_BASE_URL
    return await oauth.auth0.authorize_redirect(request, _callback_url())


@router.get("/callback")
async def auth0_callback(request: Request):
    if not settings.ENABLE_AUTH0:
        raise HTTPException(status_code=404, detail="Auth0 is not configured")
    base = settings.APP_BASE_URL.rstrip("/")
    try:
        token = await oauth.auth0.authorize_access_token(request)
    except Exception as e:  # noqa: BLE001
        logger.warning("auth0 callback error: %s", e)
        return RedirectResponse(url=f"{base}/?auth0_error=1")

    userinfo = dict(token.get("userinfo") or {})
    request.session["user"] = {
        "sub": userinfo.get("sub"),
        "name": userinfo.get("name"),
        "email": userinfo.get("email"),
        "picture": userinfo.get("picture"),
        "identity_provider": (userinfo.get("sub") or "auth0").split("|")[0],
    }

    fea_id = None
    try:
        from server import db
        from services.auth0_service import generate_identity_proof
        fea_id = await generate_identity_proof(db, userinfo, token)
        request.session["identity_fea_id"] = fea_id
    except Exception as e:  # noqa: BLE001 — proof issuance must never block login
        logger.warning("auth0 identity proof error: %s", e)

    return_to = request.session.pop("auth0_return_to", base) or base
    if fea_id:
        # Land on the dedicated, independent verification page for the freshly
        # issued "Identity Authenticated" proof.
        return RedirectResponse(url=f"{base}/verify?fea_id={fea_id}&auth0=success")
    sep = "&" if "?" in return_to else "?"
    return RedirectResponse(url=f"{return_to}{sep}auth0=success")


@router.get("/me")
async def auth0_me(request: Request):
    user = request.session.get("user")
    if not user:
        return JSONResponse(status_code=401, content={"authenticated": False})
    return {
        "authenticated": True,
        "user": user,
        "identity_fea_id": request.session.get("identity_fea_id"),
    }


@router.get("/logout")
async def auth0_logout(request: Request):
    request.session.clear()
    base = settings.APP_BASE_URL.rstrip("/") or "/"
    if not settings.ENABLE_AUTH0:
        return RedirectResponse(url=base)
    params = urlencode({"client_id": settings.AUTH0_CLIENT_ID, "returnTo": base})
    return RedirectResponse(url=f"https://{settings.AUTH0_DOMAIN}/v2/logout?{params}")
