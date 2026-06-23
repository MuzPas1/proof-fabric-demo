"""AI Provenance & Accountability input models (Trust Layer 2, Phase 2).

Privacy-preserving by design: every content field is a HASH only — raw prompts,
inputs, outputs and business content are rejected. Identity fields are free-form
strings (vendor-neutral — no provider is special-cased).
"""
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

# A hash is hex, length covering sha1..sha512 (40,56,64,96,128) — accept 32..128.
_HASH_RE = re.compile(r"^[0-9a-fA-F]{32,128}$")
_ALLOWED_EVENTS = {"review", "approval", "rejection", "escalation", "override"}
_EVENT_SYNONYMS = {
    "approve": "approval", "approved": "approval",
    "reject": "rejection", "rejected": "rejection",
    "reviewed": "review",
    "escalate": "escalation", "escalated": "escalation",
    "overridden": "override", "overrode": "override", "overriding": "override",
}


def _validate_hash(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if not _HASH_RE.match(v):
        raise ValueError(
            "must be a hex hash (32-128 hex chars); raw content is NOT permitted — "
            "submit a hash of the content only"
        )
    return v.lower()


class AIIdentity(BaseModel):
    """Optional vendor-neutral AI/agent identity metadata (no provider hard-coded)."""
    provider: Optional[str] = Field(None, max_length=128)
    model_name: Optional[str] = Field(None, max_length=128)
    model_version: Optional[str] = Field(None, max_length=64)
    model_family: Optional[str] = Field(None, max_length=64)
    agent_identifier: Optional[str] = Field(None, max_length=128)
    agent_role: Optional[str] = Field(None, max_length=128)
    execution_environment: Optional[str] = Field(None, max_length=128)


class AIProvenanceMeta(BaseModel):
    """Optional provenance metadata — HASHES + opaque correlation identifiers only."""
    prompt_hash: Optional[str] = None
    system_prompt_hash: Optional[str] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    context_hash: Optional[str] = None
    workflow_id: Optional[str] = Field(None, max_length=128)
    session_id: Optional[str] = Field(None, max_length=128)
    correlation_id: Optional[str] = Field(None, max_length=128)

    @field_validator("prompt_hash", "system_prompt_hash", "input_hash", "output_hash", "context_hash")
    @classmethod
    def _validate_hashes(cls, v):
        return _validate_hash(v)


class OversightEvent(BaseModel):
    """A single human-governance event. Notes are stored as a hash only."""
    event_type: str = Field(..., description="review | approval | rejection | escalation | override")
    actor_id: Optional[str] = Field(None, max_length=128, description="Opaque/hashed reviewer identifier")
    actor_role: Optional[str] = Field(None, max_length=128)
    decision: Optional[str] = Field(None, max_length=256)
    timestamp: Optional[str] = Field(None, max_length=64)
    note_hash: Optional[str] = None

    @field_validator("event_type")
    @classmethod
    def _normalize_event(cls, v: str) -> str:
        n = re.sub(r"[\s\-]+", "_", v.strip().lower())
        if n.startswith("human_"):
            n = n[len("human_"):]
        n = _EVENT_SYNONYMS.get(n, n)
        if n not in _ALLOWED_EVENTS:
            raise ValueError(f"event_type must be one of {sorted(_ALLOWED_EVENTS)} (got '{v}')")
        return n

    @field_validator("note_hash")
    @classmethod
    def _validate_note(cls, v):
        return _validate_hash(v)


class AgentStep(BaseModel):
    """A single step in a multi-agent accountability chain."""
    agent_identifier: str = Field(..., max_length=128)
    agent_role: Optional[str] = Field(None, max_length=128)
    sequence: int = Field(..., ge=0)
    outcome: Optional[str] = Field(None, max_length=128)
    handoff_to: Optional[str] = Field(None, max_length=128)


class AttachProvenanceRequest(BaseModel):
    """Attach a detached AI provenance & accountability envelope to a proof.

    All sections are optional, but at least one must be present.
    """
    ai_identity: Optional[AIIdentity] = None
    provenance: Optional[AIProvenanceMeta] = None
    oversight_events: Optional[List[OversightEvent]] = None
    agent_chain: Optional[List[AgentStep]] = None
