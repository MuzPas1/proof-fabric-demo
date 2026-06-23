"""Enterprise Evaluation Center — lead capture + approval lifecycle.

Flow:
  1. Public visitor submits a request (name, company, business email, industry,
     use case) -> stored `pending`.
  2. Admin reviews and approves -> a time-boxed `evaluator` account is created
     (read-only ENTERPRISE doc access; NO control-plane permissions). A one-time
     temporary password is returned to the admin to relay to the lead.
  3. Or admin rejects with a reason.

Evaluator accounts auto-expire via User.expires_at (enforced in get_current_user).
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.rbac import Role
from models.auth_models import EvaluationRequest, EvaluationRequestCreate
from services import user_service

DEFAULT_EVAL_DAYS = 30


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.evaluation_requests.create_index("request_id", unique=True)
    await db.evaluation_requests.create_index("status")
    await db.evaluation_requests.create_index("created_at")


async def create_request(db: AsyncIOMotorDatabase, payload: EvaluationRequestCreate) -> EvaluationRequest:
    record = EvaluationRequest(
        request_id=str(uuid.uuid4()),
        name=payload.name.strip(),
        company=payload.company.strip(),
        business_email=str(payload.business_email).lower(),
        industry=payload.industry.strip(),
        use_case=payload.use_case.strip(),
        status="pending",
    )
    await db.evaluation_requests.insert_one(record.model_dump())
    return record


async def list_requests(db: AsyncIOMotorDatabase, status: Optional[str] = None) -> List[EvaluationRequest]:
    query = {"status": status} if status else {}
    out = []
    async for doc in db.evaluation_requests.find(query, {"_id": 0}).sort("created_at", -1):
        out.append(EvaluationRequest(**doc))
    return out


async def approve_request(
    db: AsyncIOMotorDatabase, request_id: str, admin_email: str, tenant_id: str, days: int = DEFAULT_EVAL_DAYS
) -> dict:
    """Approve a request, provision a time-boxed evaluator account.

    Returns {evaluator_email, temporary_password, expires_at} — the temporary
    password is shown ONCE so the admin can relay it to the lead.
    """
    doc = await db.evaluation_requests.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise ValueError("Request not found")
    if doc["status"] == "approved":
        raise ValueError("Request already approved")

    email = doc["business_email"].lower()
    temp_password = secrets.token_urlsafe(12)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    existing = await db.users.find_one({"email": email})
    if existing is None:
        user = await user_service.create_user(db, email, temp_password, Role.EVALUATOR.value, tenant_id)
        await db.users.update_one({"user_id": user.user_id}, {"$set": {"expires_at": expires_at}})
    else:
        from auth.passwords import hash_password
        await db.users.update_one(
            {"email": email},
            {"$set": {"password_hash": hash_password(temp_password), "role": Role.EVALUATOR.value,
                      "status": "active", "expires_at": expires_at}},
        )

    await db.evaluation_requests.update_one(
        {"request_id": request_id},
        {"$set": {"status": "approved", "reviewed_at": datetime.now(timezone.utc).isoformat(),
                  "reviewed_by": admin_email, "evaluator_email": email, "expires_at": expires_at}},
    )
    return {"evaluator_email": email, "temporary_password": temp_password, "expires_at": expires_at}


async def reject_request(db: AsyncIOMotorDatabase, request_id: str, admin_email: str, reason: Optional[str]) -> bool:
    res = await db.evaluation_requests.update_one(
        {"request_id": request_id, "status": "pending"},
        {"$set": {"status": "rejected", "reviewed_at": datetime.now(timezone.utc).isoformat(),
                  "reviewed_by": admin_email, "notes": reason}},
    )
    return res.modified_count > 0
