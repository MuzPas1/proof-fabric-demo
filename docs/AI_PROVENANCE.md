# Trust Layer 2 — Phase 2: AI Provenance & Accountability — Implementation Report

> Status: **IMPLEMENTED & TESTED in PREVIEW ONLY**. Feature-flag gated
> (`ENABLE_AI_PROVENANCE`, default OFF; ON in preview). NOT deployed to production.
> Fully backward compatible — no change to existing proof hashes, fea_ids,
> signatures, verification flows, APIs, SDKs, or customer integrations.

---

## 1. Implementation Summary

PFP is extended from *Proof of Signing + Independent Time Attestation* into a
vendor-neutral **AI Accountability** platform. A proof can now optionally carry a
**detached, signed AI Provenance & Accountability envelope** capturing AI
identity, hashed provenance, human-oversight events, and multi-agent
accountability chains — without storing any raw prompts, inputs, outputs, or
business content.

The envelope mirrors the Phase-1 time-anchor architecture exactly: it is produced
*after* signing and stored on a separate document field, so it is byte-invisible
to proofs that do not carry it. The envelope **binds to the proof's existing
`fea_hash`** and is **itself signed by the platform Ed25519 key** (domain-separated
`PFP_AIPROV_V1::`), making it tamper-evident and independently verifiable against
the public key registry.

New artifacts:
- `core/ai_provenance.py` — envelope canonicalization, content hashing, signing & binding-signature verification.
- `models/ai_provenance.py` — vendor-neutral input models with hash-only privacy enforcement.
- `services/ai_provenance_service.py` — attach (idempotent) + additive verification + accountability summary.
- `POST /api/fea/{fea_id}/provenance` (scope `fea:write`, gated).
- `GET /api/public/verify/{fea_id}` now surfaces an `ai_provenance` verification block.

---

## 2. Schema Design

Detached envelope stored at `feas.ai_provenance` (never inside the signed payload):

```json
{
  "envelope_version": "1",
  "recorded_at": "<ISO-8601 UTC>",
  "fea_hash": "<the proof's fea_hash this envelope binds to>",
  "content": {
    "ai_identity":   { "provider","model_name","model_version","model_family",
                       "agent_identifier","agent_role","execution_environment" },
    "provenance":    { "prompt_hash","system_prompt_hash","input_hash","output_hash",
                       "context_hash","workflow_id","session_id","correlation_id" },
    "oversight_events": [ { "event_type","actor_id","actor_role","decision","timestamp","note_hash" } ],
    "agent_chain":      [ { "agent_identifier","agent_role","sequence","outcome","handoff_to" } ]
  },
  "content_hash": "SHA-256(PFP-JCS(content))",
  "binding": { "alg":"Ed25519", "domain":"PFP_AIPROV_V1::",
               "public_key_id":"<platform kid>", "signature":"<base64>" }
}
```

- All sections optional; ≥1 required. `content` excludes nulls and orders
  `agent_chain` by `sequence` for determinism.
- `event_type` ∈ {review, approval, rejection, escalation, override} (synonyms /
  "human_*" / case / spacing normalized).
- Vendor-neutral: identity fields are free strings; no provider hard-coded.

---

## 3. Verification Design

`verify_ai_provenance(fea_doc)` is **additive** and returns `None` when no
envelope is present. When present it independently confirms three invariants and
derives the accountability facts:

1. **content_integrity** — recomputed `SHA-256(PFP-JCS(content))` equals the stored `content_hash`.
2. **bound_to_proof** — `envelope.fea_hash` equals the proof's `fea_hash` (cannot be lifted onto another proof).
3. **signature_valid** — the Ed25519 binding signature over
   `PFP_AIPROV_V1::<fea_hash>:<content_hash>@<recorded_at>` verifies against the
   public key resolved from the registry (`binding.public_key_id`).

`valid = content_integrity ∧ bound_to_proof ∧ signature_valid`. The block also
surfaces independently-checkable facts: which AI system participated
(`ai_identity`), which workflow (`workflow_id`/`session_id`/`correlation_id`),
whether human review/approval/rejection/escalation/override occurred, the ordered
`approval_chain`, and the `agent_chain` (`multi_agent`, `agent_chain_length`).

---

## 4. Privacy Review

- **Hash-only enforcement at the boundary:** every content hash field
  (`*_hash`, `note_hash`) is validated as hex (32–128 chars). Any raw/free-text
  value is **rejected** (`4xx`) — raw prompts/inputs/outputs/business content can
  never be stored.
- Identity fields are length-capped metadata (provider/model/role/etc.), not
  sensitive content; reviewer identities should be passed as opaque/hashed ids.
- Verification surfaces only booleans, identifiers, roles and hashes — confidential
  content is never exposed, satisfying controlled disclosure.

---

## 5. Security Review

- **Tamper-evidence:** content is hashed and the (fea_hash, content_hash,
  recorded_at) tuple is signed by the platform key. Mutating content breaks
  `content_integrity`; re-pointing the envelope breaks `bound_to_proof`; forging
  requires the platform signing key.
- **Anti-transplant:** binding to the proof's `fea_hash` prevents reusing a valid
  envelope on a different proof.
- **Domain separation:** dedicated `PFP_AIPROV_V1::` prefix — provenance signatures
  cannot be confused with proof (`PFP_V2::`), TSA (`PFP_TSA_V1::`) or PoP signatures.
- **Trust root reuse:** the envelope verifies against the same public key registry
  (supports retired keys / continuity); inherits the platform key lifecycle.
- **No core-path impact:** verification is isolated; an invalid/garbage envelope
  never affects `signature_valid`.

---

## 6. Multi-Agent Design

`agent_chain` captures `Agent A → Agent B → … → Human → Proof Issued` with per-step
`agent_identifier`, `agent_role`, `sequence`, `outcome`, and `handoff_to`. Steps are
ordered deterministically by `sequence`. Verification reports `agent_chain_length`,
`multi_agent`, and the ordered `agents` list — proving which agents participated and
how work was handed off, without storing business data.

---

## 7. Human Oversight Design

`oversight_events` is an ordered list supporting **multiple reviewers and approval
chains** (e.g. `AI Generated → Human Reviewed → Manager Approved → Proof Issued`).
Each event has a normalized `event_type` (review/approval/rejection/escalation/
override), `actor_role`, opaque `actor_id`, and an optional `note_hash`.
Verification exposes `human_reviewed/approved/rejected/escalated/overridden` flags
plus the ordered `approval_chain`.

---

## 8. Test Results

- **Unit** (`tests/test_ai_provenance.py`) — **8/8 PASS**: sign/verify roundtrip,
  content-tamper detection, anti-transplant binding, hash-only privacy enforcement,
  event-type normalization, multi-agent + approval-chain summary, no-envelope→None,
  empty-content rejection.
- **E2E** (`tests/test_ai_provenance_e2e.py`, live preview backend) — **5/5 PASS**:
  backward compatibility, detached attach (signature byte-identical), provenance
  surfaced & independently verified, idempotent/write-once attach, raw-content &
  empty-content rejection.
- **Regression** — Phase-1 time-attestation e2e (non-destructive) + crypto unit/suite
  suites green. No regressions.

---

## 9. Backward Compatibility Validation

- New fields are detached document fields + optional response fields → **byte-invisible**
  to proofs without them. Existing `fea_hash`, `fea_id`, `signature`, and the core
  verification flow are untouched (verified: signature byte-identical before/after attach).
- Proofs without provenance verify exactly as before (`ai_provenance` absent/null).
- Feature-flag gated (`ENABLE_AI_PROVENANCE`); endpoint 404s when disabled.
- No migration required; no removal of existing functionality.

---

## 10. Production Readiness Assessment

**Ready for production behind the feature flag.** The cryptographic design,
privacy enforcement, and verification semantics are complete and tested in preview.

Recommended before/at production enablement:
- Set `ENABLE_AI_PROVENANCE=true` in production env (additive; safe — existing
  proofs unaffected).
- (Optional, P1) Combine with Phase-1 independent time attestation so provenance
  timing is also independently attested.
- (Optional, P2) Developer-portal / docs surface documenting the provenance schema
  + SDK helpers for client-side hashing.
- Not deployed in this session per the preview-only constraint.
