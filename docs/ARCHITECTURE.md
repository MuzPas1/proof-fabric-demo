# PFP — Architecture

## 1. Overview
Proof Fabric Protocol (PFP) is general-purpose **proof infrastructure**. It turns
any structured event — a payment, an AI decision, a credential, a shipment, a
compliance record — into a **Proof Artifact**: a deterministic, Ed25519-signed,
content-addressed proof that can be verified by anyone holding the public key —
without trusting or contacting the issuer. (The data-plane API and storage use
the historical identifier `fea` / `fea_id` for these artifacts; this is a stable
contract name, not a finance-only scope.)

## 2. Component topology

```
                         ┌─────────────────────────────┐
   Browser / Partner ───▶│  Ingress (TLS, /api → 8001) │
                         └──────────────┬──────────────┘
                                        │
                         ┌──────────────▼──────────────┐
                         │   FastAPI app (uvicorn)      │
                         │  ┌───────── middleware ─────┐│
                         │  │ SecurityHeaders          ││
                         │  │ RequestSizeLimit         ││
                         │  │ Metrics (Prometheus)     ││
                         │  │ CORS (strict)            ││
                         │  │ RateLimit (slowapi)      ││
                         │  └──────────────────────────┘│
                         │  Routers:                    │
                         │   /api/auth   (JWT)          │
                         │   /api/admin  (JWT + RBAC)   │
                         │   /api/fea    (API key)      │
                         │   /api/public (none)         │
                         │   /api/demo   (rate-limited) │
                         │   /api/webhooks (API key)    │
                         └───┬───────────────┬──────────┘
                             │               │
              ┌──────────────▼──┐   ┌────────▼───────────┐
              │  KMS abstraction │   │  MongoDB           │
              │  local/aws/gcp/  │   │  ├─ prod DB        │
              │  azure           │   │  │  feas, keys,    │
              │  (signing keys)  │   │  │  api_keys, users,│
              └──────────────────┘   │  │  tenants, audit, │
                                      │  │  webhooks        │
                                      │  └─ demo collections  │
                                      │     (same DB):        │
                                      │     demo_proofs,      │
                                      │     demo_key_registry │
                                      └────────────────────┘
```

## 3. Trust boundaries
| Boundary | Control |
|---|---|
| Internet ↔ Ingress | TLS termination, HSTS (prod) |
| Ingress ↔ App | only `/api/*` routed to backend |
| Data plane (`/api/fea`) | per-tenant API key, scopes |
| Control plane (`/api/admin`) | JWT + RBAC |
| Signing keys | KMS provider — no plaintext on disk in prod |
| Demo domain | isolated collections (`demo_proofs`, `demo_key_registry`) + separate demo signing key |
| Audit log | append-only SHA-256 hash chain |

## 4. Request lifecycles

### 4.1 FEA generation (`POST /api/fea/generate`)
1. `RequestSizeLimit` + rate limit (120/min).
2. `require_scope("fea:write")` resolves the API key → `ApiKeyRecord` (tenant,
   scopes, expiry) from MongoDB.
3. Dual-layer replay protection scoped to the tenant:
   - idempotency key uniqueness;
   - `(tenant_id, transaction_id, timestamp)` compound unique index.
4. Build signed payload (v1.1: `iat`, `jti`, `tenant_id`, `algorithm`).
5. `fea_hash = SHA-256(canonical(payload − fea_hash))`.
6. `signature = Ed25519.sign("PFP_V2::" + canonical(payload))` via KMS.
7. Persist; emit audit event + webhook `fea.generated`.

### 4.2 Independent verification
Any party recomputes the hash and verifies the Ed25519 signature with the public
key from `GET /api/public/keys`. The SDKs do this fully offline.

## 5. Data model (MongoDB)
| Collection | DB | Purpose |
|---|---|---|
| `feas` | prod | Issued FEAs (tenant-scoped) |
| `key_registry` | prod | Production public keys (`active/retired/revoked`) |
| `api_keys` | prod | Hashed API keys + scopes/tenant/expiry |
| `users` | prod | Control-plane users (bcrypt) |
| `tenants` | prod | Tenant registry |
| `audit_log` | prod | Append-only hash-chained audit trail |
| `webhooks` | prod | Webhook subscriptions |
| `demo_proofs` | main | Demo issue/verify history (isolated collection) |
| `demo_key_registry` | main | Demo signing key (separate trust domain) |

## 6. Scaling
API keys, users, tenants, and signing keys are all DB/KMS backed (no
process-local state), so the app scales horizontally to N uvicorn workers /
replicas. Rate limiting is per-instance (slowapi); for cluster-wide limits use
an ingress/gateway limiter or a Redis-backed limiter store.

## 7. Configuration
All configuration is environment-driven (`core/config.py`). No secrets or URLs
are hardcoded. Missing critical config fails fast at boot.

## 8. Signing & key-management architecture

### 8.1 Single pluggable signing call site
All production signing flows through one abstraction (`core/kms.py`):

```
crypto.signing.sign_message()
      └─▶ get_kms().sign("production", "PFP_V2::" + canonical_json)
                 └─▶ <KMSProvider>.sign(...)   # provider-specific
```

The `KMSProvider` interface (`get_signing_key`, `sign`, `get_public_key_*`,
`status`) is selected by the `KMS_PROVIDER` env var. Because every signature in
the platform goes through `get_kms().sign(...)`, the signing backend can change
**without any API, payload-format, or caller changes**.

### 8.2 Provider capability matrix
| Provider | `KMS_PROVIDER` | Mode | Key material | Status |
|---|---|---|---|---|
| Local (software) | `local` | `seed-env` | Ed25519 seed from `PRIVATE_KEY` / `DEMO_PRIVATE_KEY` env | **Active** (dev/sandbox + current deploy) |
| AWS | `aws` | `seed-import` | seed pulled from AWS Secrets Manager, signed locally | Ready (config-only) |
| GCP | `gcp` | `seed-import` | seed pulled from GCP Secret Manager, signed locally | Ready (config-only) |
| Azure | `azure` | `seed-import` | seed pulled from Azure Key Vault, signed locally | Ready (config-only) |
| Native HSM | *(future)* | `native` | private key **never leaves** the HSM/KMS; remote sign | Planned |

Non-secret readiness is observable at `GET /api/health` (`signing` block) and
`GET /api/developer` (`signing` capability profile) — these never return key
material.

### 8.3 Trust domains & key registry
- **Production** and **demo** use **separate signing keys** (logical names
  `production` / `demo`) so demo artifacts can never verify against production
  keys.
- The **public** key registry (`key_registry`) supports `active / retired /
  revoked` states with rotation (`POST /api/admin/keys/rotate`). Verification
  selects the key by `public_key_id` embedded in the artifact, so historical
  proofs remain verifiable across rotations.

### 8.4 Cryptographic trust model
- **Algorithm:** Ed25519 (libsodium / PyNaCl) with domain separation prefix
  `PFP_V2::` to prevent cross-protocol signature reuse.
- **Determinism:** PFP-JCS canonicalization → SHA-256 → sign. Identical inputs
  produce byte-identical artifacts in any SDK language.
- **Independent verification:** anyone with the public key verifies offline; no
  issuer contact, no shared secret. Trust derives from the key, not the system.
- **Tamper-evidence:** any change to the payload breaks both the content hash
  and the signature.

> Full migration steps (env vars, secret refs, rollout/rollback) and the
> **RFC-3161 external time-anchoring readiness** assessment live in
> [`KMS_MIGRATION_GUIDE.md`](KMS_MIGRATION_GUIDE.md).

## 9. Future readiness (not yet active)
| Item | Status | Notes |
|---|---|---|
| Cloud KMS (AWS/GCP/Azure) | Architecture ready | Config-only switch; see migration guide |
| Native HSM signing | Planned | New provider implementing `KMSProvider.sign` remotely |
| External time anchoring (RFC-3161) | Planned (readiness documented) | `iat` is the current trusted issuance time; see migration guide §RFC-3161 |
