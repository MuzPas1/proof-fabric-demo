"""Enterprise Evaluation Center routes — public lead capture + admin lifecycle."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth.dependencies import get_current_user, require_permission, resolve_tenant_scope
from auth.rbac import Permission
from core.ratelimit import limiter
from models.auth_models import User, EvaluationRequest, EvaluationRequestCreate
from services import evaluation_service, audit_service

router = APIRouter(tags=["evaluation"])


def _db():
    from server import db
    return db


# -------- Public: lead capture --------
@router.post("/evaluation/request")
@limiter.limit("10/hour")
async def submit_evaluation_request(request: Request, body: EvaluationRequestCreate):
    """Public Enterprise Evaluation request. Creates a pending lead."""
    record = await evaluation_service.create_request(_db(), body)
    await audit_service.record_audit(
        _db(), "evaluation.requested", actor=record.business_email, tenant_id="public",
        target=record.request_id, metadata={"company": record.company, "industry": record.industry},
    )
    return {
        "status": "received",
        "request_id": record.request_id,
        "message": "Thank you. Our team will review your request and follow up by email.",
    }


# -------- Admin: review & approve --------
class ApproveRequest(BaseModel):
    days: Optional[int] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = None


@router.get("/admin/evaluation/requests")
async def list_evaluation_requests(
    status_filter: Optional[str] = None,
    user: User = Depends(require_permission(Permission.TENANTS_READ)),
):
    items = await evaluation_service.list_requests(_db(), status_filter)
    return {"requests": [i.model_dump() for i in items], "total": len(items)}


@router.post("/admin/evaluation/requests/{request_id}/approve")
async def approve_evaluation_request(
    request_id: str,
    body: ApproveRequest,
    user: User = Depends(require_permission(Permission.APIKEYS_MANAGE)),
):
    scope = resolve_tenant_scope(user, None)
    try:
        result = await evaluation_service.approve_request(
            _db(), request_id, user.email, scope, days=body.days or evaluation_service.DEFAULT_EVAL_DAYS
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await audit_service.record_audit(
        _db(), "evaluation.approved", actor=user.email, tenant_id=scope,
        target=request_id, metadata={"evaluator_email": result["evaluator_email"], "expires_at": result["expires_at"]},
    )
    return {"status": "approved", **result}


@router.post("/admin/evaluation/requests/{request_id}/reject")
async def reject_evaluation_request(
    request_id: str,
    body: RejectRequest,
    user: User = Depends(require_permission(Permission.APIKEYS_MANAGE)),
):
    ok = await evaluation_service.reject_request(_db(), request_id, user.email, body.reason)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pending request not found")
    await audit_service.record_audit(
        _db(), "evaluation.rejected", actor=user.email, tenant_id="public", target=request_id,
    )
    return {"status": "rejected", "request_id": request_id}
