# PFP — Architecture

## 1. Overview
Proof Fabric Protocol (PFP) is a cryptographic evidence platform. It turns
structured records (financial transactions and, in the demo domain, any
regulated workflow) into **Financial Evidence Artifacts (FEAs)**: deterministic,
Ed25519-signed, content-addressed proofs that can be verified by anyone holding
the public key — without trusting or contacting the issuer.

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
                                      │  └─ demo DB (isolated)│
                                      │     demo_proofs, keys │
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
| Demo domain | separate database + separate signing key |
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
| `demo_proofs` | **demo** | Demo issue/verify history (isolated) |
| `key_registry` | **demo** | Demo signing key (isolated) |

## 6. Scaling
API keys, users, tenants, and signing keys are all DB/KMS backed (no
process-local state), so the app scales horizontally to N uvicorn workers /
replicas. Rate limiting is per-instance (slowapi); for cluster-wide limits use
an ingress/gateway limiter or a Redis-backed limiter store.

## 7. Configuration
All configuration is environment-driven (`core/config.py`). No secrets or URLs
are hardcoded. Missing critical config fails fast at boot.
