# PFP — Canonical Endpoints & Environment Status

**Authoritative reference** for every public Proof Fabric Protocol (PFP) URL.
If any other document disagrees with this file, **this file wins**. Last
updated: **2026-06-12**.

---

## 1. Production Website
| Item | Value |
|---|---|
| Marketing / product website | **https://pfprotocol.com** |
| Purpose | Product overview, positioning, contact, documentation entry point |
| Status | 🟢 Live |

## 2. Demo Environment (live, evaluatable)
| Item | Value |
|---|---|
| Interactive demo (Transaction Evidence Dashboard) | **https://demo.pfprotocol.com** |
| Public verifier UI | **https://demo.pfprotocol.com/verify** |
| Admin / control-plane dashboard | **https://demo.pfprotocol.com/admin** (login at `/admin/login`) |
| Demo + sandbox API base | **https://demo.pfprotocol.com/api** |
| Sandbox key bootstrap | `GET https://demo.pfprotocol.com/api/config` → `test_api_key` (non-production only) |
| Status | 🟢 Live |

> The demo environment exposes the **full API surface** (demo, FEA sandbox,
> public verification, admin). It is the environment external reviewers and
> integrators evaluate against.

## 3. Production Integration API
| Item | Value |
|---|---|
| Production API base (provisioned/licensed integrators) | **https://api.pfprotocol.com/api** |
| Ingress host (Helm/K8s) | `api.pfprotocol.com` |
| Key provisioning | `POST /api/admin/api-keys/create` (admin JWT) — keys shown once |
| `/api/config` sandbox key | **Not exposed** when `ENVIRONMENT=production` |
| Status | 🟡 Templated in deploy configs (`deploy/helm`, `deploy/k8s`); provision per customer |

## 4. API Conventions
- All routes are prefixed with **`/api`**.
- **Data plane** (`/api/fea/*`, `/api/webhooks/*`): `X-API-Key: <key>`.
- **Control plane** (`/api/auth/*`, `/api/admin/*`): `Authorization: Bearer <jwt>`.
- **Public** (`/api/public/*`, `/api/demo/*`, system): no auth.
- Machine-readable spec: [`openapi.yaml`](openapi.yaml) / [`openapi.json`](openapi.json).
  Full route table: [`API_REFERENCE.md`](API_REFERENCE.md).

## 5. SDK References
| Language | Path | Verification dependency |
|---|---|---|
| Python | [`../sdks/python/`](../sdks/python) | PyNaCl |
| JavaScript (Node 18+) | [`../sdks/javascript/`](../sdks/javascript) | none (built-in `crypto`) |
| Java (JDK 17+) | [`../sdks/java/`](../sdks/java) | jackson-databind (native Ed25519) |
| .NET (8.0) | [`../sdks/dotnet/`](../sdks/dotnet) | BouncyCastle |

Point the SDK client at the **production API base** (`https://api.pfprotocol.com`)
or the **demo/sandbox base** (`https://demo.pfprotocol.com`). All four SDKs
implement identical canonicalization (`PFP-JCS`,
[`CANONICALIZATION_SPEC.md`](CANONICALIZATION_SPEC.md)) so a proof signed by the
server verifies byte-identically in any language.

## 6. Current Environment Status
| Environment | URL | Role | Status |
|---|---|---|---|
| Production website | https://pfprotocol.com | Marketing / docs | 🟢 Live |
| Demo / sandbox | https://demo.pfprotocol.com | Live demo + evaluation API | 🟢 Live |
| Production API | https://api.pfprotocol.com | Licensed integration API | 🟡 Deploy template |

### Data & deployment notes (current)
- **Single managed database.** Production and demo data share one MongoDB
  database. Demo is logically isolated via dedicated collections
  (`demo_proofs`, `demo_key_registry`) and a **separate demo signing key** — so
  demo-signed artifacts never verify against production keys. (`DEMO_DB_NAME`
  was removed on 2026-06-12; a second physical DB breaks managed deployments.)
- **Signing:** local Ed25519 software signing today; cloud KMS
  (`KMS_PROVIDER=aws|gcp|azure`) abstraction is implemented and templated.
- **Readiness:** 8/10 Pilot Ready — see
  [`PRODUCT_READINESS_ASSESSMENT_V2.md`](PRODUCT_READINESS_ASSESSMENT_V2.md).

---

## 7. Deprecated / removed references
| Old reference | Replace with |
|---|---|
| `https://transaction-sign-1.preview.emergentagent.com` (internal preview pod) | `https://demo.pfprotocol.com` (demo/sandbox) or `https://api.pfprotocol.com` (prod) |
| `https://app.pfprotocol.com` (placeholder app origin) | `https://pfprotocol.com` and `https://demo.pfprotocol.com` |
| `DEMO_DB_NAME` / separate `pfp_demo` database | Removed — single DB + `demo_proofs` / `demo_key_registry` collections |
