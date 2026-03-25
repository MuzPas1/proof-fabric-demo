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
3. Ed25519 signing/verification
4. Idempotency enforcement
5. API key authentication for private endpoints
6. Public verification without auth
7. Rate limiting (100 req/min)
8. MongoDB storage (minimal schema)

## What's Been Implemented (March 25, 2026)
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
- [x] JSON viewer with syntax highlighting
- [x] All tests passing (100% backend, 100% frontend)

## Prioritized Backlog
### P0 (Critical)
- None - MVP complete

### P1 (Important)
- Key rotation implementation (basic structure exists)
- Webhook notifications for FEA generation
- Batch FEA generation endpoint

### P2 (Nice to have)
- FEA export (PDF certificates)
- Analytics dashboard
- Multi-tenant support

## Next Tasks
1. Production deployment configuration
2. Key rotation workflow
3. Batch generation endpoint
