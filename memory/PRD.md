# Proof Fabric Protocol (PFP) - PRD

## Original Problem Statement
Production-grade API for "Proof Fabric Protocol (PFP)" — transform transactions
into deterministic, cryptographically verifiable Financial Evidence Artifacts
(FEAs), independently verifiable without internal-system access. A public
"Transaction Evidence Dashboard" demonstrates the flow across industries. In
June 2026 the user (acting as enterprise architect) commissioned a full
enterprise hardening + productionization sprint across 10 phases.

## User Personas
- Developers (dev console), Backend systems (FEA generate/verify), Auditors
  (independent public verification), Platform/Security operators (control plane).

## Core Requirements
Deterministic canonicalization (PFP-JCS), SHA-256 + Ed25519 with domain
separation, idempotency + replay protection, persistent key registry, API-key +
JWT/RBAC auth, multi-tenancy, public verification, rate limiting, MongoDB.

## Tech Stack
FastAPI + React + MongoDB; PyNaCl (Ed25519); PyJWT + bcrypt; slowapi;
prometheus-client. KMS abstraction (local/aws/gcp/azure).

## What's Been Implemented

### Phases 1–3 (Mar 2026) — Core protocol, hardening, replay/key registry
Canonicalization, SHA-256, Ed25519 v2 (domain prefix PFP_V2::), idempotency,
replay (compound unique index), persistent key registry (active/retired/revoked),
downloadable signed artifact, public verify, demo multi-industry portal.

### Enterprise Hardening Sprint (June 10, 2026) — Phases 1–10 COMPLETE
- **Security remediation (P1):** DB-backed API keys (create/revoke/rotate/scopes/
  expiry/customer+tenant); `/api/config` no longer leaks key in prod; demo
  isolated to separate DB + separate demo signing key + rate-limited; KMS
  abstraction (local/aws/gcp/azure); admin key lifecycle + audit.
- **Enterprise (P2):** JWT auth + RBAC (5 roles); multi-tenancy (`tenant_id`
  bound in signed payload); admin APIs (`/api/admin/*`); immutable hash-chained
  audit log + verify endpoint.
- **Crypto (P3):** FEA v1.1 (iat/jti/tenant_id/algorithm signed); legacy v1
  rejected by default; live revocation enforcement; PFP-JCS spec; time-anchor
  abstraction documented.
- **Integration (P4):** batch FEA, pagination, single fetch, webhooks (HMAC).
- **Observability (P5):** `/api/metrics` (Prometheus), structured JSON logging
  (redaction), deep `/api/health`.
- **Security (P6):** security headers, strict CORS, 1MiB body cap, rate limits.
- **SDKs (P7):** Python, JavaScript, Java, .NET — client + independent
  verification (Python/JS proven live; cross-lang canonicalization parity tested).
- **Docs (P8):** Architecture, Security, Crypto, Canonicalization spec, API ref,
  OpenAPI (34 paths, regenerated) + Postman, Integration, Runbook, DR, Key
  rotation, Threat model, Pilot deployment.
- **Deploy (P9):** Dockerfile, docker-compose, K8s, Helm, Terraform, CI/CD.
- **Audit (P10):** new readiness assessment — **8/10 Pilot Ready (D)**; 56/56
  tests pass.

## API Endpoints (34) — see docs/API_REFERENCE.md
System(4), Auth(4), Admin(12), FEA(5), Public(2), Webhooks(4), Demo(5).

## Credentials
Admin: admin@pfprotocol.com / PfpAdmin!2026 (super_admin). Sandbox X-API-Key:
pfp_sandbox_a5fb2bad1924d788c128edf6a31bf1aaa107a9a4 (dev only). See
/app/memory/test_credentials.md.

## Remaining backlog (to reach 10/10 Production)
- P1: HSM / native-KMS-sign provider behind existing KMS interface.
- P1: External time anchor (RFC-3161 TSA / transparency log) — wire the abstraction.
- P1: Third-party penetration test + crypto audit.
- P2: Cluster-wide rate limiting (Redis/gateway store).
- P2: SOC 2 / ISO 27001 evidence collection.
- P3: Strict RFC-8785 canonicalization as fea_version 2.0.
- UI: optional admin/tenant dashboard (key & webhook management) in the frontend.

## DB Schema
Prod DB: feas (tenant-scoped, v1.1 payload), key_registry, api_keys, users,
tenants, audit_log (hash chain), webhooks. Demo DB (isolated): demo_proofs,
key_registry (demo key).
