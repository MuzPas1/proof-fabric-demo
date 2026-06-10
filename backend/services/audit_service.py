"""Immutable audit trail with a SHA-256 hash chain.

Each entry stores the hash of the previous entry, making silent tampering
or deletion detectable. Entries are append-only by convention and verified
via verify_audit_chain().
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from models.auth_models import AuditEntry
from core.observability import AUDIT_EVENTS


def _compute_entry_hash(entry: dict) -> str:
    payload = {
        "audit_id": entry["audit_id"],
        "action": entry["action"],
        "actor": entry["actor"],
        "tenant_id": entry["tenant_id"],
        "target": entry.get("target"),
        "metadata": entry.get("metadata", {}),
        "created_at": entry["created_at"],
        "prev_hash": entry.get("prev_hash", ""),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def record_audit(
    db: AsyncIOMotorDatabase,
    action: str,
    actor: str,
    tenant_id: str,
    target: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> AuditEntry:
    last = await db.audit_log.find_one(sort=[("created_at", -1)], projection={"_id": 0})
    prev_hash = last["entry_hash"] if last else ""

    entry = AuditEntry(
        audit_id=str(uuid.uuid4()),
        action=action,
        actor=actor,
        tenant_id=tenant_id,
        target=target,
        metadata=metadata or {},
        prev_hash=prev_hash,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    doc = entry.model_dump()
    doc["entry_hash"] = _compute_entry_hash(doc)
    entry.entry_hash = doc["entry_hash"]
    await db.audit_log.insert_one(doc)
    try:
        AUDIT_EVENTS.labels(action).inc()
    except Exception:
        pass
    return entry


async def list_audit(
    db: AsyncIOMotorDatabase,
    tenant_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
) -> List[dict]:
    query: dict = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    if action:
        query["action"] = action
    cursor = (
        db.audit_log.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(min(limit, 500))
    )
    return [doc async for doc in cursor]


async def verify_audit_chain(db: AsyncIOMotorDatabase) -> dict:
    """Walk the chain oldest→newest and confirm hashes are intact."""
    cursor = db.audit_log.find({}, {"_id": 0}).sort("created_at", 1)
    prev = ""
    count = 0
    async for doc in cursor:
        count += 1
        if doc.get("prev_hash", "") != prev:
            return {"intact": False, "broken_at": doc["audit_id"], "checked": count}
        recomputed = _compute_entry_hash(doc)
        if recomputed != doc.get("entry_hash"):
            return {"intact": False, "broken_at": doc["audit_id"], "checked": count}
        prev = doc["entry_hash"]
    return {"intact": True, "checked": count}
