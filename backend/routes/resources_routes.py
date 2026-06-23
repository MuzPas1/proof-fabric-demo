"""Tiered serving of developer assets (docs + SDKs) with server-side enforcement.

Replaces the previous open StaticFiles mounts. Visibility is enforced by
core.doc_classification, NOT by navigation:
  * PUBLIC docs      -> served to anyone
  * ENTERPRISE docs  -> served only to staff / approved evaluators
  * INTERNAL docs    -> 404 (never served externally)
  * ALL SDK assets   -> ENTERPRISE

Path traversal is prevented by resolving against the docs/sdks roots.
"""
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse

from auth.dependencies import get_optional_user, has_enterprise_access
from core.doc_classification import classify_doc, classify_sdk, PUBLIC, ENTERPRISE, INTERNAL
from models.auth_models import User

router = APIRouter(tags=["resources"])

_DOCS_ROOT = Path(__file__).resolve().parents[1].parent / "docs"
_SDKS_ROOT = Path(__file__).resolve().parents[1].parent / "sdks"

_GATE_BODY = {
    "error": "enterprise_access_required",
    "message": "This material is available through the PFP Enterprise Evaluation Center.",
    "request_access": "/evaluation",
}


def _safe_resolve(root: Path, rel: str) -> Optional[Path]:
    try:
        target = (root / rel).resolve()
        target.relative_to(root.resolve())
    except (ValueError, RuntimeError):
        return None
    if not target.is_file():
        return None
    return target


@router.get("/resources/docs/{file_path:path}")
async def serve_doc(file_path: str, user: Optional[User] = Depends(get_optional_user)):
    target = _safe_resolve(_DOCS_ROOT, file_path)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    tier = classify_doc(file_path)
    if tier == INTERNAL:
        # Internal docs are not externally serveable — indistinguishable from missing.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if tier == ENTERPRISE and not has_enterprise_access(user):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=_GATE_BODY)
    return FileResponse(str(target))


@router.get("/resources/sdks/{file_path:path}")
async def serve_sdk(file_path: str, user: Optional[User] = Depends(get_optional_user)):
    target = _safe_resolve(_SDKS_ROOT, file_path)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if classify_sdk(file_path) == ENTERPRISE and not has_enterprise_access(user):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=_GATE_BODY)
    return FileResponse(str(target))
