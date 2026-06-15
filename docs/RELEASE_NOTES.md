# PFP Release Notes

Chronological record of platform releases. Newest first. Future releases are
published by appending a new section to this document.

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
