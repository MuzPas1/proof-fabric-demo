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
Single managed DB (`DB_NAME`). Production collections: feas (tenant-scoped,
v1.1 payload), key_registry, api_keys, users, tenants, audit_log (hash chain),
webhooks. Demo collections (logically isolated, same DB): demo_proofs,
demo_key_registry (dedicated demo signing key — separate trust domain from
production key_registry).

## Changelog
### June 12, 2026 — Production demo 500 fix (single-DB consolidation)
- ROOT CAUSE: demo flow wrote to a separate physical DB (`pfp_demo`); managed
  production Mongo only authorizes `DB_NAME` → `OperationFailure: not authorized
  on pfp_demo` → 500 on `/api/demo/issue` (production only; preview's local
  Mongo allowed any DB so it passed).
- FIX: `demo_db = db` (single DB). Demo signing key moved to dedicated
  `demo_key_registry` collection (preserves demo↔prod trust-domain isolation
  without a second database). Removed all `DEMO_DB_NAME` / `pfp_demo` references
  (config.py + backend/.env).
- DEPLOY HYGIENE: rewrote corrupted `.gitignore` (had 8 duplicated blocks
  ignoring `.env`); `.env` files are now tracked so deploy injects prod values.
- Verified in preview: demo issue/verify/artifact/artifact-verify all 200,
  /api/health all-green, UI "Process Transaction" → proof generated.
- ACTION: user must REDEPLOY to push this fix to https://demo.pfprotocol.com.

### June 12, 2026 — Documentation refresh (production alignment)
- Canonical URLs standardized repo-wide: website `https://pfprotocol.com`,
  demo/sandbox `https://demo.pfprotocol.com`, production API
  `https://api.pfprotocol.com`. Removed all internal preview URLs
  (`transaction-sign-1.preview.emergentagent.com`) and placeholder
  `app.pfprotocol.com` from docs/deploy/SDK/OpenAPI/Postman.
- NEW: `docs/CANONICAL_ENDPOINTS.md` (authoritative endpoints + env status);
  rewrote root `README.md`.
- Updated all "separate demo DB" claims to the new single-DB + isolated
  collections model; removed `DEMO_DB_NAME` from deploy configs (k8s, helm,
  docker-compose) and ops/DR env lists.

### June 15, 2026 — Hosted API docs + api.pfprotocol.com readiness
- Enabled interactive API docs served by the backend on ANY attached domain:
  Swagger UI `/api/docs`, ReDoc `/api/redoc`, live OpenAPI `/api/openapi.json`.
  CSP relaxed ONLY for docs routes (allows jsDelivr CDN); strict elsewhere.
- NEW `GET /api/developer` resource index; static hosting of docs + SDKs under
  `/api/resources/docs/*` and `/api/resources/sdks/*` (OpenAPI YAML, Postman,
  guides, SDK sources).
- Added `https://api.pfprotocol.com` to production `CORS_ORIGINS` (k8s, helm,
  terraform) so the API domain works once linked. No app code differs per
  domain — same `/api` surface via ingress. Domain linking is a platform/DNS
  step (Entri); steps documented in `docs/CANONICAL_ENDPOINTS.md` §8.
- Verified: Swagger renders (36 ops), FEA generate/verify + public verify OK,
  CSP strict on non-docs routes.

### June 15, 2026 — Branded Developer Portal at /developers
- New canonical developer entry point: `https://demo.pfprotocol.com/developers`
  (in-app React route; no separate api.pfprotocol.com deployment needed).
- Sections: glass sticky header, hero, "First API Call in 15 Minutes" 5-step
  journey (credentials → generate → verify → integrate → review) with copyable
  dark code blocks, 9 resource cards (Swagger/ReDoc/OpenAPI/API ref/auth/
  quickstart/integration/architecture/dev-index), 4 SDK cards + Postman
  download, verification examples, and a live Platform Status section (6 pills,
  health-driven).
- Cross-portal nav added: Demo header `demo-nav-developers`, Admin sidebar
  `admin-nav-developers`.
- Design per design_guidelines.json (Swiss/high-contrast, blue-600, Space
  Grotesk, JetBrains Mono code). Files: frontend/src/developers/* (10 files),
  App.js route, TransactionFlow.jsx + admin/Layout.jsx nav links.
- Tested: testing_agent iteration_9 — 67/67 frontend checks pass, all 16
  backend resource endpoints 200, no regressions.

### June 15, 2026 — Developer Portal: interactive sandbox + industry-agnostic refresh
- NEW public endpoint `POST /api/demo/sandbox-key` (rate-limited 20/hr/IP):
  issues a REAL DB-backed, scoped (fea:write/read/verify), 1-day key bound to
  the isolated `sandbox` tenant. Reuses `api_key_service.create_api_key`.
- Interactive in-browser lifecycle on `/developers` (Try It Live / `dev-playground`):
  Step 1 Generate Sandbox Key → Step 2 Generate a Proof Artifact (live
  `POST /api/fea/generate`) → Step 3 Verify Proof (live `GET /api/public/verify/{id}`),
  each step auto-fills the next. Shows Proof ID, timestamp, fea_hash, signature,
  and PASS/FAIL signature/hash/timestamp checks. React context `SandboxContext`
  shares the key so Quick Start snippets + SDK examples pre-fill with the live key.
- New sections: `WhyPfp` (value prop + Event→Proof→Artifact→Verification→Trust
  lifecycle), `Onboarding` (5-step journey), `UseCases` (8 industries + 6
  capabilities for non-developer evaluators), tabbed SDK quick examples
  (Python/JS/Java/.NET), and `PlatformStatus` rebuilt to 5 live checks
  (API/Docs/SDK/Verification/Demo, health + openapi driven).
- TERMINOLOGY: industry-agnostic refresh across the portal — "Financial
  Evidence Artifact (FEA)" → "Proof Artifact" in all visible copy (API field
  names `fea_id`/`/api/fea/*` unchanged). PFP positioned as general-purpose
  proof infrastructure.
- Docs updated: README.md, docs/QUICKSTART.md, docs/CANONICAL_ENDPOINTS.md
  (added sandbox-key endpoint + Developer Portal, Admin → /admin/login,
  Proof Artifact terminology, USD examples).
- New files: SandboxContext.jsx, SandboxKey.jsx, FirstProof.jsx, VerifyProof.jsx,
  Playground.jsx, WhyPfp.jsx, UseCases.jsx, Onboarding.jsx (+ CopyInline in
  CodeBlock.jsx). Backend test: tests/test_sandbox_portal.py (4 pass).
- Tested: testing_agent iteration_10 — 12/12 frontend spec items pass (100%),
  full live lifecycle verified; backend pytest 4/4 pass. No regressions.
