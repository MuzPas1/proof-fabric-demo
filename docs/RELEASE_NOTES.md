# PFP Release Notes

Chronological record of platform releases. Newest first. Future releases are
published by appending a new section to this document.

---

## v2.1.0 — Change & Release Management use case
**Release date:** 2026-06-15

### Features added
- **New industry template: Change & Release Management** in the Demo Portal's
  Industry selector. Turns release approvals and control checks into an
  independently verifiable **Release Readiness Proof Artifact** with a
  **Release Readiness Proof ID**.
- **10 readiness checks:** Test Execution, UAT Completion, Security Scan,
  Vulnerability Remediation, CAB Approval, Change Approval, Deployment Approval,
  Rollback Validation, Compliance Control, Production Monitoring Readiness.
- **Release-aware input form** (Release Name, Release ID, Environment, Application,
  CAB Reference, Release Window) with enterprise sample data
  (REL-2026-001 · Payments Platform · Production · CAB-APPROVED-2026 · Weekend
  Deployment).
- **Release Readiness Certificate** view: Release Name, Environment, Readiness
  Score, Proof ID, cryptographic (Ed25519) signature, verification status and
  generated timestamp.
- Proof output surfaces Workflow Type, Release Name, Environment,
  Status (Ready / Not Ready), checks passed, timestamp, signature and Proof ID.
- Positioning + approach comparison: *Traditional* (Emails → Checklists →
  Screenshots → Approvals → Trust) vs *PFP* (Evidence → Validation →
  Cryptographic Proof → Verification).
- New documentation page: **Industry Use Cases → Change & Release Management**.

### Improvements
- Auditor verification now surfaces embedded release context (Release Name,
  Environment, etc.) for release proofs — verifiable with only the Proof ID.

### Security updates
- Industry `context` (Release Name, Environment, Release ID, …) is embedded in
  the **signed canonical payload**, so release metadata is cryptographically
  proven and tamper-evident — no raw release data is needed to verify.

### Documentation updates
- Added `USE_CASE_CHANGE_RELEASE.md`; surfaced it in the Documentation Portal
  under a new **Industry Use Cases** category.

### Breaking changes
- None. Reuses the existing proof engine, artifact structure, Proof ID
  generation, signing and auditor verification flows. The `IndustryContext`
  schema gained an optional, backward-compatible `context` field.

### Migration guidance
- None required.

---

## v2.0.0 — Developer Portal, Live Sandbox & Industry-Agnostic Positioning
**Release date:** 2026-06-15

### Features added
- **Branded Developer Portal** at `/developers` — the primary interactive
  onboarding and integration surface.
- **Sandbox key generation** — one-click, real, scoped, short-lived sandbox
  credentials via `POST /api/demo/sandbox-key` (rate-limited, `sandbox` tenant).
- **Generate a Proof Artifact** — live, in-browser proof generation against
  `POST /api/fea/generate` using the generated sandbox key, showing Proof ID,
  timestamp, hash and signature.
- **Verify a Proof Artifact** — live independent verification via
  `GET /api/public/verify/{id}` with signature / hash / timestamp checks.
- **SDK quick examples** — copy-paste Python, JavaScript, Java and .NET
  examples, auto-filled with the active sandbox key.
- **Documentation Portal** at `/docs` — centralized, searchable knowledge base
  (this portal) with left-nav tree, deep links and Markdown rendering.

### Improvements
- 5-step onboarding journey and "Why PFP" value proposition with the
  Event → Proof Generation → Proof Artifact → Independent Verification → Trust
  lifecycle.
- Industry use-case and capability sections for non-developer evaluators.
- Live platform status (API, Documentation, SDKs, Verification Engine, Demo).
- Responsive/mobile refinements across portals.

### Security updates
- **KMS / HSM readiness:** all signing now routes through a single pluggable
  KMS abstraction (`KMS_PROVIDER`), making Cloud KMS (AWS/GCP/Azure) a
  configuration-only switch and a native-HSM provider a drop-in — with no API,
  payload or proof-format changes.
- Non-secret signing posture exposed at `GET /api/health` (`signing`) and
  `GET /api/developer` (`signing` capability profile).
- Trust & Security messaging clearly separates **Current** (Ed25519 signing,
  proof generation/verification, multi-tenant architecture) from
  **Architecture Readiness** (Cloud KMS, HSM) and **Planned** (RFC-3161
  external time anchoring).

### Documentation updates
- Repo-wide terminology refresh: **"Financial Evidence Artifact" → "Proof
  Artifact"** across the Developer Portal, OpenAPI/Swagger metadata, route and
  schema descriptions, SDK README and guides — positioning PFP as
  general-purpose proof infrastructure.
- New `KMS_MIGRATION_GUIDE.md` (signing architecture, Cloud KMS/HSM migration
  path, security/trust model, RFC-3161 readiness).
- Regenerated `openapi.json` / `openapi.yaml` (canonical servers preserved).
- Canonical URLs established across all docs.

### Breaking changes
- None.

### Migration guidance
- None required. API contract names (`fea_id`, `/api/fea/*`, schema names,
  operationIds) are unchanged for backward compatibility.

---
