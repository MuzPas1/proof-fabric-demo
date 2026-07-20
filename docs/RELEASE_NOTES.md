# PFP Release Notes

Chronological record of platform releases. Newest first. Future releases are
published by appending a new section to this document.

---

## v2.4.0 — Generalized Inbound Authentication Providers
**Release date:** 2026-06-28

> Additive and **fully backward compatible**. Existing `hmac`/`api_key`/`bearer`/
> `none` integrations are unchanged (`hmac` is now an alias of `hmac_sha256`).
> No change to the core ingestion or Proof Artifact pipeline. See
> `INBOUND_EVENT_INGESTION.md` §5.

### Features added
- **Generalized provider framework** — the inbound auth layer is now a pluggable
  registry supporting the major enterprise auth / webhook verification patterns:
  `hmac_sha256`, `hmac_sha1`, `api_key`, `bearer`, `basic`, `jwt`, `oauth2`,
  `mtls` (edge-forwarded headers), and configurable `custom` providers.
- **JWT verification** (PyJWT): HS256 shared secret, or RS256/ES256 via static
  PEM or a cached remote **JWKS URL**; validates `exp`/`iss`/`aud` with leeway
  and never trusts the token's `alg`.
- **OAuth 2.0**: inbound access-token validation via local JWKS verification or
  **RFC 7662 introspection** (cached, strict timeout, scope/audience checks),
  selectable per integration.
- **HMAC schemes**: raw-body, or `{timestamp}.{body}` templates including
  Stripe (`t=,v1=`) and Slack (`v0:ts:body`) styles, driven by `auth_config`.
- **Cross-cutting controls** (compose with every provider): **timestamp
  validation** (`require_timestamp` + tolerance), **replay protection**
  (`inbound_nonces` with unique index + TTL → `409` on replay), and idempotency.
- **Config-first onboarding**: new providers are added via `auth_config` or a
  lightweight `register_custom_provider(...)` adapter — no core change.
- **Admin Portal**: provider dropdown expanded; advanced `auth_config` (JSON) +
  provider-secret fields and timestamp/replay toggles for externally-configured
  providers. Secrets (incl. sensitive `auth_config` sub-keys) are redacted.

### Data / schema
- `integrations` gains optional `auth_config`, `require_timestamp`,
  `timestamp_tolerance_seconds`, `replay_protection`, `basic_password_hash`,
  `external_secret` (redacted). New `inbound_nonces` collection (TTL). No change
  to `feas` or existing collections; no migration required.

### Dependencies
- `pyjwt[crypto]`, `httpx` (added to `requirements.txt`).

### Breaking changes
- None.

---

## v2.3.0 — Inbound Event Ingestion Framework
**Release date:** 2026-06-25

> Additive, **feature-flagged and default OFF** (`ENABLE_EVENT_INGESTION`).
> **Fully backward compatible** — the core proof engine, existing APIs, auth,
> admin features and customer flows are unchanged. See
> `INBOUND_EVENT_INGESTION.md`.

### Features added
- **Generic inbound ingestion:** any external application/platform/enterprise
  system can submit verifiable business events to `POST /api/ingest/{slug}`; each
  is transformed into a Proof Artifact via the *existing* generation pipeline
  (no core change). Application-, department-, industry- and sector-agnostic.
- **Common Event Model + modular adapters:** a vendor-neutral `CommonEvent` and a
  configurable `generic` adapter (field-mapping driven). New integrations need
  only a lightweight adapter — often just a `field_map`.
- **Pluggable inbound authentication:** `hmac` (HMAC-SHA256 over the raw body),
  `api_key`, `bearer`, or `none`. Credentials are shown once and stored hashed
  (or, for HMAC, redacted); external endpoints require the provider credential,
  **not** PFP admin auth.
- **Full Admin Portal management** (`PFP Admin → Integrations`,
  `/api/admin/integrations`): create, configure, enable/disable, rotate
  credentials, monitoring/health, recent-event log, audit, and a test tool
  (dry-run or issue a real test proof). Guarded by new RBAC permissions
  `integrations:manage` / `integrations:read`.
- **Privacy-preserving mapping:** actor/subject are tokenized (hashed) and extra
  fields are committed only as a metadata hash before signing.

### Data / schema
- New collections `integrations` and `inbound_events`. No change to `feas`,
  `key_registry`, or any existing collection. No migration required.

### Security
- Structured error handling (401/403/404/409/422), per-integration constant-time
  credential verification, rate-limited inbound endpoint, and hash-chained audit
  entries for all management actions.

### Breaking changes
- None.

---

## v2.2.0 — Crypto Agility, Federated Key Registry & Bring-Your-Own-Signing
**Release date:** 2026-06-18

> All new capabilities are **feature-flagged and default OFF**. Ed25519 + FEA
> v1.1 remains the default and only active behaviour. **Fully backward
> compatible** — existing proofs, proof IDs, verification APIs, SDKs, demo and
> auditor workflows are unchanged. See `CRYPTO_AGILITY.md`.

### Features added
- **Crypto Agility — signature suites:** `Ed25519` (default), `ES256`
  (ECDSA/secp256r1), `ES256K` (ECDSA/secp256k1). ECDSA uses raw `r‖s` (64B,
  base64) with **enforced low-S** (anti-malleability). Suite selectable via
  `signature_suite` on `POST /api/fea/generate`. Verifier binds the suite to the
  registry key's algorithm (**algorithm-confusion / downgrade defense**).
- **Federated Key Registry:** register customer/partner-owned public keys
  (`raw` / `jwk` / `spki-pem`) with **proof-of-possession**, **validity windows**,
  tenant ownership, and revocation/retirement —
  `POST /api/admin/keys/federated/register` + `/confirm`.
- **Bring-Your-Own-Signing (BYOS):** per-tenant signer —
  `local` KMS, `remote` HTTP signer, or `cloud-kms` (native, config-gated).
  `POST/GET/DELETE /api/admin/signers`, `GET /api/admin/signers/health`.
  Independent verification never depends on signer availability.
- **SDKs:** Python + JavaScript verifiers are suite-aware (parity proven via
  shipped `sdks/test_vectors.json`); Java + .NET verifiers updated for ES256/ES256K.
- **Feature flags:** `ENABLE_CRYPTO_SUITES`, `ENABLE_FEDERATED_KEYS`,
  `ENABLE_BYOS`, `DEFAULT_SIGNATURE_SUITE` (all default to existing behaviour).

### Data / schema
- `key_registry` gains optional federated fields (no migration; legacy docs
  default). New `signers` and `pop_challenges` collections. `feas` unchanged.
  Key rotation is now **algorithm-scoped** (Ed25519 rotation no longer retires
  ES256/ES256K keys).

### Security
- Threat analysis + mitigations for algorithm confusion, downgrade, key
  substitution, replay, remote-signer abuse, ECDSA malleability, and cross-tenant
  isolation (see `CRYPTO_AGILITY.md` §8 and `THREAT_MODEL.md`).

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
