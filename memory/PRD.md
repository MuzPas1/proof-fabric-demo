# Proof Fabric Protocol (PFP) - PRD

## Original Problem Statement
Production-grade API for "Proof Fabric Protocol (PFP)" — transform transactions
into deterministic, cryptographically verifiable Financial Evidence Artifacts
(FEAs), independently verifiable without internal-system access. A public
"Transaction Evidence Dashboard" demonstrates the flow across industries. In
June 2026 the user (acting as enterprise architect) commissioned a full
enterprise hardening + productionization sprint across 10 phases.

## ✅ v2.2.0 — Crypto Agility + Federated Keys + BYOS (June 18, 2026)
Implemented & validated; **awaiting deployment approval** (do NOT commit/deploy yet).
- **Crypto Agility:** signature suites Ed25519 (default), ES256 (secp256r1), ES256K
  (secp256k1). ECDSA raw r‖s 64B base64, low-S enforced. Verifier binds suite to
  registry key algorithm (anti-confusion/downgrade). `signature_suite` param on
  `/api/fea/generate`. Backend: `crypto/suites.py`, suite-aware `core/kms.py`,
  `crypto/signing.py`, `services/{fea_service,verification_service}.py`.
- **Federated Key Registry:** customer/partner keys (raw/JWK/SPKI-PEM) with
  proof-of-possession, validity windows, tenant ownership, revoke/retire.
  `POST /api/admin/keys/federated/register|confirm`. `services/federated_key_service.py`,
  extended `models/key_registry.py`, new `pop_challenges` collection.
- **BYOS:** per-tenant signer (local/remote-HTTP/cloud-kms config-gated).
  `/api/admin/signers[/health]`. `core/signers.py`, `services/signer_service.py`,
  new `signers` collection. Verification is signer-independent.
- **SDKs:** Python+JS suite-aware (parity via `sdks/test_vectors.json`); Java/.NET updated.
- **Flags (default OFF; enabled in preview):** `ENABLE_CRYPTO_SUITES`,
  `ENABLE_FEDERATED_KEYS`, `ENABLE_BYOS`, `DEFAULT_SIGNATURE_SUITE`.
- **Docs:** `docs/CRYPTO_AGILITY.md` (+ /docs portal), RELEASE_NOTES v2.2.0, dev-portal Trust section.
- **Tests:** 146 pytest pass; testing_agent iteration_17 = 9/9 e2e + frontend, 0 issues.
- Fully backward compatible: existing Ed25519 proofs/IDs/APIs/SDKs/demo/auditor unchanged;
  key rotation now algorithm-scoped; no data migration required.


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

### June 15, 2026 — Production hardening: KMS/HSM readiness, trust positioning, data cleanup
- **KMS/HSM (#1):** All signing now routes through `core.kms.get_kms().sign(logical, msg)`
  (signing.py `sign_message`/`sign_hash`), so a future native-HSM provider (key never
  leaves the HSM) drops in by config with ZERO API/payload/caller changes. Added provider
  capability profile (`mode`, `algorithm`, `native_sign`, per-logical-key resolution) +
  module `kms_status()`. Non-secret signing posture exposed at `GET /api/health` (`signing`)
  and `GET /api/developer` (`signing` capability profile). Signatures byte-identical (crypto
  tests pass). Local provider active today; aws/gcp/azure ready (config-only).
- **Portal positioning (#6):** New `TrustArchitecture.jsx` "Trust & Security" section +
  "Security" nav (`dev-nav-trust`): 5 capability badges + 3 honest columns (Current /
  Readiness / Planned), live-driven from `/api/developer.signing`. No overstating — Active
  vs Ready vs Planned clearly labeled. Added `kms-migration` resource card.
- **Docs (#5) + RFC-3161 readiness (#4):** Updated README, QUICKSTART, CANONICAL_ENDPOINTS,
  ARCHITECTURE (§8 signing & key-mgmt, §9 future readiness), DEVELOPER_GUIDE (§1 repositioned,
  §11.1 signing). NEW `docs/KMS_MIGRATION_GUIDE.md`: signing architecture, AWS/GCP/Azure
  migration steps + rollback, native-HSM path, security/trust model, RFC-3161 external
  time-anchoring readiness (detached unsigned `time_anchor` envelope, opt-in, backward
  compatible) — documentation only, no RFC-3161 code.
- **Verification (#3):** testing_agent iteration_11 (24/25; found tablet nav overflow) →
  fixed (section nav `hidden md:flex` → `hidden lg:flex`) → iteration_12 100% (4/4).
  Clean-session (no login/cookies) full lifecycle works desktop + mobile; first-time
  evaluator needs NO admin access; all portal links 200; no "Financial Evidence Artifact"
  in visible copy. Fixed pre-existing webhook test (invalid event `fea.created` →
  `fea.generated`). Backend: 106 pass.
- **Data cleanup (#2):** Deleted 28,846 stale `tenant_id: null` FEAs from the PREVIEW DB
  (pre-multi-tenancy load/test data, Mar–Jun 2026). Preserved all 94 tenant-scoped proofs,
  api_keys, webhooks, tenants, demo_proofs (operational), audit_log, key_registry, users,
  demo_key_registry. Post-cleanup lifecycle verified healthy. NOTE: production DB is separate/
  managed — production cleanup must be run after redeploy.

### June 15, 2026 — Pre-redeploy production review (branding + preview-ref sweep)
- **Canonical domains confirmed:** pfprotocol.com, demo.pfprotocol.com,
  /admin/login, /developers, /api/docs, /api/redoc, /api/openapi.json (all 200).
  Frontend uses REACT_APP_BACKEND_URL (prod injects demo.pfprotocol.com); copy-paste
  snippets use demo.pfprotocol.com. No per-domain code.
- **Preview-ref sweep:** ZERO emergent/preview/`fea-crypto` URLs remain in any
  shipped developer-facing surface (docs, SDKs, OpenAPI, Postman, frontend, portal,
  nav). Remaining occurrences are only non-shipped internals: test files (env-driven
  fallback default), test_reports/*.json (historical), memory/PRD.md (changelog), and
  the CANONICAL_ENDPOINTS "Deprecated/removed" mapping (intentional).
- **Branding refresh (OpenAPI/Swagger + code):** FastAPI title description, all `/api/fea/*`
  + public route docstrings, fea_service/models docstrings, admin ProofExplorer dialog,
  sdks/README, DEVELOPER_GUIDE → "Financial Evidence Artifact" replaced with "Proof Artifact".
  Regenerated docs/openapi.json + docs/openapi.yaml (36 paths, canonical servers preserved,
  0 finance phrases). amount description "paise"→"cents". CONTRACT NAMES PRESERVED: `fea_id`,
  `/api/fea/*`, schema names (FEAResponse/GenerateFEARequest/…), operationIds — no breaking change.
- **backend_test.py** made env-driven (removed hardcoded preview URL).
- **Verified:** signatures unchanged; Swagger/ReDoc/OpenAPI render; full lifecycle works;
  46 targeted tests pass; frontend build clean. Trust & Security messaging accurate
  (Current=Ed25519 signing/gen/verify; Readiness=Cloud KMS/HSM; Planned=RFC-3161).
  DEPLOYMENT: READY.

### June 15, 2026 — Documentation Portal at /docs (structured knowledge base)
- **New `/docs` route** (`frontend/src/docs/DocsPortal.jsx`, registered in App.js as `/docs/*`):
  a Stripe/Twilio-style documentation hub that complements — does NOT duplicate — the
  Developer Portal (`/developers`) and API reference (`/api/docs`).
- **Components created:** docsData.js (IA tree, SLUG_MAP, FILE_TO_SLUG, SEARCHABLE_DOCS,
  CANONICAL), MarkdownView.jsx (react-markdown + remark-gfm, heading anchors, in-doc link
  rewriting to internal slugs / served resources, styled tables/code), DocsSidebar.jsx,
  DocsHome.jsx, DocContent.jsx (fetch + on-page TOC + deep-link scroll), DocsSearch.jsx
  (lazy full-text index over all docs; title + content + heading-level results; category
  filter; ⌘K), Releases.jsx, TrustOverview.jsx (live `/api/developer` signing).
- **Categories:** Getting Started, Developer Documentation, Architecture, Security & Trust,
  SDKs & Tools, Deployment & Operations, Governance & Compliance, API Specifications,
  Release Notes — extensible by appending to DOC_TREE (version-ready).
- **Docs files:** copied README.md → docs/ (served), created docs/RELEASE_NOTES.md (v2.0.0
  entry). All markdown served at `/api/resources/docs/*.md` (verified 200).
- **Navigation cross-links added:** Developer Portal nav (`dev-nav-docs`) + footer
  (`footer-docs-portal`), Demo header (`demo-nav-docs`), Admin sidebar (`admin-nav-docs`),
  and docs top-nav to Website/Demo/Developers/Admin/API Docs.
- **Docs updated:** README.md + CANONICAL_ENDPOINTS.md now list the Documentation Portal.
- **Dependencies:** react-markdown, remark-gfm.
- **Tested:** testing_agent iteration_13 (12/13; tablet nav overflow) → fixed (header nav
  `hidden md:flex` → `hidden lg:flex`) → iteration_14 100% (6/6 viewport+route combos).
  Markdown rendering, deep links, search (doc + heading level, category filter), trust
  overview, release notes, cross-links and mobile drawer all verified. DEPLOYMENT: READY.

### June 15, 2026 — Generic Workflow Builder (primary mode) + template rename
- **Rename (display only):** industry `change_release` label → **"Release Readiness
  Evaluation"** (key, proof engine, verification, existing artifacts UNCHANGED).
  "Change & Release Management" removed from all visible UI.
- **NEW Generic Workflow Builder** (`generic_builder`) — now the DEFAULT/primary
  demo mode. Configurable, zero-code proof for ANY workflow (HR, ITSM, Asset,
  Procurement, Sales, AI Governance, Healthcare, etc.):
  - Editable **Workflow Name** (not hardcoded), dynamic **custom fields**
    (label/value, add/remove/edit, start 3), dynamic **checks** (add/remove/
    rename, start 3), **Simulate Failure** toggle (fails ALL checks).
  - **Starter template** auto-loaded (Workflow Name=Release; fields REL-2026-001/
    Production/CAB-APPROVED-2026; checks Test Execution/UAT Completion/CAB Approval)
    — screen never empty.
  - **LocalStorage persistence** (`pfp_generic_workflow_v1`): Save / Load Last /
    Reset. **Share Template** → URL `/demo?config=<b64>` (no backend); navigating
    to it restores the config. New `/demo` route added (also serves `/`).
  - **Validation** blocks proof when Workflow Name empty OR no valid field OR no
    checks (inline message + disabled button). Empty fields (blank label OR value)
    excluded from the canonical payload.
  - **Proof output** is industry-agnostic: Workflow Name, Custom Fields, Checks
    Passed, Proof ID, Timestamp, Ed25519 Signature, Verification Status.
- **Backend (additive, backward-compatible):** `IndustryCheck.desc` now optional;
  new `CustomField` model; `IndustryContext.custom_fields` = **ordered list**
  embedded in the canonical payload (preserves visible field order → field
  reordering changes the proof_id). Curated industries (desc + context) unchanged.
- **Proof engine / signing / artifact / proof-id / auditor verification UNCHANGED** —
  the builder only feeds custom data into the existing architecture.
- **New files:** `frontend/src/components/WorkflowBuilder.jsx`,
  `frontend/src/lib/workflowConfig.js`, `backend/tests/test_generic_workflow.py`.
  Modified: `TransactionFlow.jsx`, `industries.js`, `App.js`, `demo_routes.py`.
- **Tested:** backend pytest 20/20 (generic_workflow + demo_issue_verify);
  testing_agent iteration_16 — 100% (13/13 frontend scenarios + Financial &
  Release Readiness Evaluation regressions). No issues.

### June 15, 2026 — Industry template: Change & Release Management
- **New industry template `change_release`** in the Demo Portal Industry selector
  (frontend/src/lib/industries.js). Reuses the existing proof engine, artifact
  structure, Proof ID generation, signing and auditor verification flows — NOT a
  separate app.
- **10 readiness checks** (Test Execution → Production Monitoring Readiness).
- **Release-aware input form** (Release Name, Release ID, Environment select
  Dev/UAT/Production, Application, CAB Reference, Release Window) with enterprise
  sample data; mapped onto the canonical {transaction_id,user_id,amount} contract.
- **CRM proof output:** Workflow Type, Release Name, Environment, Status
  (Ready/Not Ready), Checks Passed (n/10), Release ID, Proof ID, timestamp.
- **Release Readiness Certificate** view: Release Name, Environment, Readiness
  Score, Proof ID, Ed25519 signature (via /demo/artifact), Verification Status,
  Generated timestamp.
- **Positioning** ("Today's release readiness is report-focused. PFP makes it
  evidence-proof oriented.") + Traditional (Emails→Checklists→Screenshots→
  Approvals→Trust) vs PFP (Evidence→Validation→Cryptographic Proof→Verification).
- **Backend (additive, backward-compatible):** `IndustryContext` gained optional
  `context` dict, embedded in the signed canonical payload → release metadata is
  cryptographically proven and returned on verify (no raw data needed).
- **Auditor verification** surfaces embedded release context for release proofs.
- **Docs:** new `USE_CASE_CHANGE_RELEASE.md` under a new "Industry Use Cases"
  category in /docs; RELEASE_NOTES.md v2.1.0 entry.
- Consistency/Exception sections hidden for CRM (kept for other industries).
- **Tested:** testing_agent iteration_15 — 100% (10/10 CRM criteria + Financial
  regression + docs portal). One CRITICAL React crash (React.Fragment without
  default React import) found & fixed (use named Fragment). Backend pytest 47 pass.
