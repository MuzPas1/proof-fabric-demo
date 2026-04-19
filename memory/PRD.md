# Proof Fabric Protocol (PFP) - PRD

## Original Problem Statement
Build a production-grade API for "Proof Fabric Protocol (PFP)" - Transform financial transactions into deterministic, cryptographically verifiable Financial Evidence Artifacts (FEAs) that can be independently verified without accessing internal systems.

## User Personas
- **Developers**: Testing cryptographic proof APIs via dev console
- **Backend Systems**: Integrating FEA generation/verification into financial workflows
- **Auditors**: Publicly verifying FEA authenticity without credentials

## Core Requirements
1. Deterministic canonicalization (lexicographic JSON sorting, null removal, timestamp normalization)
2. SHA-256 hashing on canonical FEA structure
3. Ed25519 signing/verification with domain separation (PFP_V2::)
4. Idempotency enforcement
5. Strict replay protection via unique (transaction_id, timestamp) constraint
6. Persistent, immutable key registry in MongoDB
7. API key authentication for private endpoints
8. Public verification without auth
9. Rate limiting (100 req/min)
10. MongoDB storage with atomic constraints

## What's Been Implemented

### Phase 1: Core Protocol (Complete)
- [x] Backend modular architecture (models/, crypto/, services/, routes/)
- [x] Canonicalization module with deterministic JSON output
- [x] SHA-256 hashing and Ed25519 signing/verification
- [x] POST /api/fea/generate - FEA generation with idempotency
- [x] POST /api/fea/verify - FEA verification with API key auth
- [x] GET /api/public/verify/{fea_id} - Public verification (no auth)
- [x] GET /api/public/keys - Public key registry
- [x] GET /api/config - Test API key retrieval
- [x] API key authentication middleware
- [x] Rate limiting (100/min)
- [x] Dark-themed developer console UI (3 tabs: Generate, Verify, Public Verify)

### Phase 2: Protocol Hardening (Complete)
- [x] Corrected signing model: sign(message) not sign(hash) for Ed25519
- [x] Domain separation (PFP_V2:: prefix) for cross-protocol attack prevention
- [x] Constant-time hash comparison (hmac.compare_digest) for timing attack prevention
- [x] Timestamp boundary validation (5 min future, 1 year past)
- [x] Protocol version (fea_version) enforcement
- [x] Backward compatibility for v1 (hash-signed), legacy v2 (prefix), and current v2 formats
- [x] Structural separation of signed fea_payload from signature metadata
- [x] Metadata hashing included in signed payload

### Phase 3: Replay Protection & Key Registry (Complete - March 25, 2026)
- [x] Strict replay protection: unique compound index on (transaction_id, timestamp)
- [x] Dual-layer protection: idempotency key (Layer 1) + transaction uniqueness (Layer 2)
- [x] transaction_payload_hash stored separately for replay comparison (excludes idempotency_key)
- [x] Persistent key registry in MongoDB (key_registry collection)
- [x] Key immutability: keys never deleted, only status changes (active → retired)
- [x] DB-backed key resolution for verification (verify_fea_with_registry)
- [x] Key rotation support (retire_key, rotate_key functions)
- [x] All endpoints use async DB-backed verification
- [x] 19/19 backend tests passed

### Phase 6: Compliance-Aware Transaction Flow + Auditor Verification (Complete - Feb 10, 2026)
- [x] New backend endpoint `POST /api/demo/issue` — embeds compliance state (KYC/AML/Limits/Status) in canonical payload, hashes it, persists to `db.demo_proofs`
- [x] New backend endpoint `GET /api/demo/verify/{proof_id}` — lookup + re-canonicalize + re-hash integrity check; returns valid/invalid + compliance breakdown + transaction_id + issued_at
- [x] Crypto primitives (canonicalize_to_json, compute_sha256) unchanged
- [x] Frontend flow reordered: Transaction → Compliance (with "Simulate Compliance Failure" toggle) → Evidence (auto-issued) → Auditor Verification → Consistency → Exception
- [x] Compliant messaging: "Transaction is COMPLIANT" / "Proof Verified — Data Untampered" / "Valid Proof — Data Untampered"
- [x] Non-compliant messaging: "KYC Fail — Transaction is NON-COMPLIANT" / "Proof Verified — Transaction flagged as NON-COMPLIANT" / "Valid Proof — Transaction flagged as NON-COMPLIANT"
- [x] Invalid proof messaging: "Invalid Proof — Verification Failed"
- [x] Evidence tamper-evident copy + "Share Proof" button (navigator.share → clipboard fallback)
- [x] Auditor section displays extracted KYC/AML/Limits/Transaction ID from cryptographic proof (no re-entry of raw data)
- [x] Consistency: Party A (Client · ABCPay) vs Party B (Bank · HDFC), Simulate Mismatch toggle, Exception reveal on mismatch
- [x] Edit-after-process / compliance-toggle-after-process invalidates Evidence section
- [x] 16/16 backend + all 15 frontend e2e flows passed (iteration_4.json)

### Phase 7: Independent Verification (Signed Downloadable Artifact) (Complete - Feb 10, 2026)
- [x] New endpoint `POST /api/demo/artifact` — builds a standalone Ed25519-signed proof artifact (schema v1), returns canonical JSON with `Content-Type: application/pfp-proof+json;v=1` + attachment filename
- [x] New endpoint `POST /api/demo/artifact/verify` — independent verification: strict schema + no-extra-fields, canonical ordering, normalization, timestamp skew (≤5 min future), constant-time `proof_id` compare (hmac.compare_digest), `kid` lookup with revocation check, Ed25519 signature verify with `PFP_ARTIFACT_V1::` domain separator
- [x] Key registry supports `active` / `retired` / `revoked` status (extended `PublicKeyInfo.status` Literal); artifact service reads key status live from DB (cache-bypass) so revocation takes effect without restart
- [x] Existing `/api/demo/issue` and `/api/demo/verify/{proof_id}` untouched
- [x] Frontend: new `/verify` route (`PublicVerifyPage.jsx`) with drag-drop, file upload, clipboard paste, textarea, and three result states (Valid compliant / Valid non-compliant flagged / Invalid with reason) + extracted KYC/AML/Limits/Timestamp/Key ID
- [x] Dashboard Evidence section gained `Download Proof` button (triggers browser download of signed JSON) and a link to `/verify`
- [x] React Router (v7) wired in App.js: `/` → TransactionFlow, `/verify` → PublicVerifyPage
- [x] Tamper coverage verified: amount/txid/compliance/timestamp/signature/kid modifications all rejected; missing + extra fields rejected; unsupported version/algorithm rejected; revoked key rejected; retired key still verifies
- [x] 20/20 backend tests passing after revoked-key bug fix; all frontend flows passed (iteration_5.json)

## Prioritized Backlog

### P1 (Important)
- Full key rotation workflow with admin endpoint
- Batch FEA generation endpoint

### P2 (Nice to have)
- Webhook notifications for FEA generation events
- Production deployment configuration
- FEA export (PDF certificates)
- Analytics dashboard
- Multi-tenant support

## Key API Endpoints
- POST /api/fea/generate - Generate FEA (requires X-API-Key)
- POST /api/fea/verify - Verify FEA (requires X-API-Key)
- GET /api/public/verify/{fea_id} - Public verify (no auth)
- GET /api/public/keys - Key registry (no auth)
- POST /api/demo/proof - Stateless normalize + SHA-256 hash (no auth)
- POST /api/demo/issue - Issue compliance-aware proof + persist (no auth)
- GET  /api/demo/verify/{proof_id} - Auditor lookup + integrity re-verify (no auth)
- POST /api/demo/artifact - Build+sign downloadable Ed25519 artifact (no auth)
- POST /api/demo/artifact/verify - Independent artifact verification (no auth)
- GET /api/config - Test API key (no auth)
- GET /api/health - Health check

## DB Schema
- **feas**: fea_id (unique), idempotency_key, canonical_payload_hash, transaction_payload_hash, fea_payload, signature, signature_version, public_key_id, created_at
  - Indexes: fea_id (unique), idempotency_key, (transaction_id + timestamp) compound unique
- **key_registry**: public_key_id (unique), public_key, algorithm, created_at, status
- **api_keys**: key_id, key_hash, created_at
