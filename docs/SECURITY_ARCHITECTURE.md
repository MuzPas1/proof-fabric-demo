# PFP — Security Architecture

## 1. Identity & access
### 1.1 Control plane (JWT)
- `POST /api/auth/login` issues HS256 access (30 min) + refresh (7 day) tokens,
  also set as `httpOnly` cookies. Tokens carry `sub`, `email`, `role`,
  `tenant_id`, `type`.
- Passwords hashed with **bcrypt** (`auth/passwords.py`). No plaintext storage.
- Admin seeded idempotently from `ADMIN_EMAIL`/`ADMIN_PASSWORD`; the hash is
  updated if the env password changes.

### 1.2 RBAC
Roles (`auth/rbac.py`): `super_admin`, `tenant_admin`, `auditor`, `verifier`,
`read_only`. Permissions are enforced via `require_permission(...)` dependencies.
Super admins may operate cross-tenant (via `X-Tenant-Id`); all other roles are
locked to their own tenant (`resolve_tenant_scope`).

### 1.3 Data plane (API keys)
- Keys are random 192-bit tokens (`pfp_live_…`). Only the **SHA-256 hash** is
  stored (`api_keys` collection). The raw key is returned **once** at creation.
- Each key carries `tenant_id`, `customer_id`, `scopes`, `expires_at`, `status`.
- Scope enforcement via `require_scope("fea:write" | "fea:read" | "fea:verify"
  | "webhooks:manage")`.
- Revocation and expiry are checked on every request.

## 2. Multi-tenant isolation
- Every FEA, API key, webhook, and audit entry is tagged with `tenant_id`.
- `tenant_id` is **inside the signed FEA payload** — cryptographically bound.
- Replay-protection uniqueness is scoped per tenant.
- All data-plane queries filter by the caller's tenant.

## 3. Key management
- Signing keys are resolved through a **KMS abstraction** (`core/kms.py`):
  `local` (dev, env seed), `aws` (Secrets Manager), `gcp` (Secret Manager),
  `azure` (Key Vault). Production must not use `local`.
- **Production and demo keys are distinct** (`production` vs `demo` logical
  keys). Demo artifacts can never be confused with production FEAs.
- Lifecycle: `active → retired → revoked`. Revoked keys **fail** verification
  (checked live from DB, no cache staleness). Retired keys still verify history.
- Rotation: `POST /api/admin/keys/rotate` generates a new keypair, registers the
  public key, retires the old, and returns the new seed once for KMS deployment.

## 4. Transport & headers
- Strict CORS: explicit origins; wildcard is only permitted when credentials are
  not required (the middleware disables credentials automatically for `*`).
- Security headers on every response: `X-Content-Type-Options`, `X-Frame-Options:
  DENY`, `Referrer-Policy`, `CSP`, `Permissions-Policy`, COOP, and **HSTS in
  production**.
- Request body size capped at `MAX_REQUEST_BYTES` (default 1 MiB) — DoS guard.

## 5. Rate limiting
slowapi limits: `fea/generate` 120/min, `fea/batch` 30/min, `fea/verify`
240/min, all `demo/*` write paths 60/min, root 100/min. Per-instance; pair with
an ingress limiter for cluster-wide enforcement.

## 6. Cryptographic policy
- Ed25519 signatures over canonical JSON with domain separation.
- **Legacy v1 (hash-signed) signatures are rejected** unless
  `ACCEPT_LEGACY_V1=true` — closes the downgrade-attack surface.
- Optional strict timestamp enforcement at verify (`ENFORCE_VERIFY_TIMESTAMP`).
- Constant-time comparison for all hash/signature checks.

## 7. Audit & non-repudiation
- Every admin action and FEA issuance writes an immutable, **hash-chained**
  audit entry (`services/audit_service.py`). `GET /api/admin/audit/verify`
  re-walks the chain to detect tampering or deletion.

## 8. Secrets & logging
- All secrets from environment; none hardcoded; missing config fails fast.
- Structured JSON logging with field redaction for `password`, `private_key`,
  `secret`, `authorization`, `x-api-key`, `token`.

## 9. Residual risks / hardening backlog
- Rate limiting is per-instance (use Redis store or gateway for cluster limits).
- MongoDB must be deployed with TLS + auth (`mongodb+srv`, credentials) —
  enforced by deployment config, not by app code.
- No external time anchor yet (RFC-3161 / transparency log) — see
  `CRYPTOGRAPHIC_ARCHITECTURE.md` §7 for the abstraction plan.
- Third-party crypto review and penetration test are recommended pre-GA.
