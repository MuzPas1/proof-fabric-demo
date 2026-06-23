"""AI Provenance & Accountability service — attach & verify detached envelopes.

DETACHED by design: attaching reads the proof's existing ``fea_hash`` and writes
an ``ai_provenance`` envelope onto the ``feas`` document WITHOUT touching the
signed payload, signature, or fea_id. Verification is additive to signature
checks and independently confirms which AI system / workflow participated and
whether human review / approval / escalation occurred — WITHOUT exposing any
confidential content (hashes only).
"""
from __future__ import annotations

from typing import Dict, Optional

from core.config import settings
from core.ai_provenance import sign_envelope, content_hash_of, verify_binding_signature
from models.ai_provenance import AttachProvenanceRequest


def _fea_hash_of(fea_doc: Dict) -> Optional[str]:
    payload = fea_doc.get("fea_payload") or {}
    return payload.get("fea_hash")


def _build_content(request: AttachProvenanceRequest) -> Dict:
    """Assemble the minimal, deterministic provenance content (drop empties)."""
    content: Dict = {}

    if request.ai_identity:
        ident = {k: v for k, v in request.ai_identity.model_dump().items() if v is not None}
        if ident:
            content["ai_identity"] = ident

    if request.provenance:
        prov = {k: v for k, v in request.provenance.model_dump().items() if v is not None}
        if prov:
            content["provenance"] = prov

    if request.oversight_events:
        events = [
            {k: v for k, v in e.model_dump().items() if v is not None}
            for e in request.oversight_events
        ]
        if events:
            content["oversight_events"] = events

    if request.agent_chain:
        steps = sorted(
            ({k: v for k, v in s.model_dump().items() if v is not None} for s in request.agent_chain),
            key=lambda s: s.get("sequence", 0),
        )
        if steps:
            content["agent_chain"] = steps

    return content


async def attach_provenance(
    db, fea_id: str, request: AttachProvenanceRequest, tenant_id: Optional[str] = None
) -> Dict:
    """Produce and persist a detached, signed provenance envelope for a proof.

    Write-once / idempotent: returns the existing envelope if already attached.
    """
    if not settings.ENABLE_AI_PROVENANCE:
        raise PermissionError("AI provenance is not enabled")

    query = {"fea_id": fea_id}
    if tenant_id is not None:
        query["tenant_id"] = tenant_id
    fea_doc = await db.feas.find_one(query, {"_id": 0})
    if not fea_doc:
        raise LookupError(f"Proof not found: {fea_id}")

    if fea_doc.get("ai_provenance"):
        return fea_doc["ai_provenance"]

    digest = _fea_hash_of(fea_doc)
    if not digest:
        raise ValueError("Proof has no fea_hash to bind provenance to")

    content = _build_content(request)
    if not content:
        raise ValueError(
            "Empty provenance: provide at least one of ai_identity, provenance, "
            "oversight_events, agent_chain"
        )

    envelope = sign_envelope(digest, content)
    await db.feas.update_one({"fea_id": fea_id}, {"$set": {"ai_provenance": envelope}})
    return envelope


def _summarize(content: Dict) -> Dict:
    """Derive the independently-verifiable accountability facts (no raw content)."""
    ident = content.get("ai_identity") or {}
    prov = content.get("provenance") or {}
    events = content.get("oversight_events") or []
    chain = content.get("agent_chain") or []

    etypes = [e.get("event_type") for e in events]
    approval_chain = [
        {"actor_role": e.get("actor_role"), "event_type": e.get("event_type"), "actor_id": e.get("actor_id")}
        for e in events
    ]
    agents = [
        {
            "sequence": s.get("sequence"),
            "agent_identifier": s.get("agent_identifier"),
            "agent_role": s.get("agent_role"),
            "outcome": s.get("outcome"),
            "handoff_to": s.get("handoff_to"),
        }
        for s in chain
    ]

    return {
        "ai_identity_present": bool(ident),
        "ai_identity": ident,
        "workflow_id": prov.get("workflow_id"),
        "session_id": prov.get("session_id"),
        "correlation_id": prov.get("correlation_id"),
        "provenance_hashes": {
            k: prov.get(k)
            for k in ("prompt_hash", "system_prompt_hash", "input_hash", "output_hash", "context_hash")
            if prov.get(k)
        },
        "human_oversight": bool(events),
        "human_reviewed": "review" in etypes,
        "human_approved": "approval" in etypes,
        "human_rejected": "rejection" in etypes,
        "human_escalated": "escalation" in etypes,
        "human_overridden": "override" in etypes,
        "approval_chain": approval_chain,
        "agent_chain_length": len(chain),
        "multi_agent": len(chain) > 1,
        "agents": agents,
    }


async def verify_ai_provenance(fea_doc: Dict) -> Optional[Dict]:
    """Additive verification of any provenance envelope on the proof.

    Returns None when no envelope is present (backward-compatible). Never raises
    into the signature path.
    """
    envelope = fea_doc.get("ai_provenance")
    if not envelope:
        return None

    digest = _fea_hash_of(fea_doc)
    content = envelope.get("content") or {}

    content_integrity = content_hash_of(content) == envelope.get("content_hash")
    bound_to_proof = envelope.get("fea_hash") == digest

    signature_valid = False
    kid = (envelope.get("binding") or {}).get("public_key_id")
    if kid:
        try:
            from services.key_service import get_public_key_bytes_by_id
            pub = await get_public_key_bytes_by_id(kid)
            if pub:
                signature_valid = verify_binding_signature(envelope, pub)
        except Exception:  # noqa: BLE001
            signature_valid = False

    valid = content_integrity and bound_to_proof and signature_valid

    return {
        "present": True,
        "valid": valid,
        "content_integrity": content_integrity,
        "bound_to_proof": bound_to_proof,
        "signature_valid": signature_valid,
        "attested_by": kid,
        "recorded_at": envelope.get("recorded_at"),
        **_summarize(content),
    }
