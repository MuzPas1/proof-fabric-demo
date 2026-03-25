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
- GET /api/config - Test API key (no auth)
- GET /api/health - Health check

## DB Schema
- **feas**: fea_id (unique), idempotency_key, canonical_payload_hash, transaction_payload_hash, fea_payload, signature, signature_version, public_key_id, created_at
  - Indexes: fea_id (unique), idempotency_key, (transaction_id + timestamp) compound unique
- **key_registry**: public_key_id (unique), public_key, algorithm, created_at, status
- **api_keys**: key_id, key_hash, created_at
