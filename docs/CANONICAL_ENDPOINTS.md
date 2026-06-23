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

## 1a. Developer Portal (canonical developer entry point)
| Item | Value |
|---|---|
| Branded Developer Portal | **https://demo.pfprotocol.com/developers** |
| Purpose | Single entry point: Quick Start, API docs, Swagger/ReDoc/OpenAPI, Auth guide, SDK downloads, Postman, integration & architecture guides, verification examples, platform status |
| Status | 🟢 Live |

> The Developer Portal is an in-app React route on the existing deployment (no
> separate `api.pfprotocol.com` deployment). It links to the backend-served docs
> under `/api` so it works on any attached domain.

## 1b. Documentation Portal (structured knowledge base)
| Item | Value |
|---|---|
| Documentation Portal | **https://demo.pfprotocol.com/docs** |
| Purpose | Structured, searchable knowledge base: product, architecture, security & trust, SDKs, deployment & operations, governance & compliance, API specs, release notes (`/docs/releases`). Complements (does not duplicate) the Developer Portal and `/api/docs`. |
| Status | 🟢 Live |

> The Documentation Portal renders the backend-served Markdown docs
> (`/api/resources/docs/*.md`) with left-nav tree, full-text search, deep links
> and Markdown rendering. Interactive onboarding stays in `/developers`; endpoint
> reference stays in `/api/docs`.

## 2. Demo Environment (live, evaluatable)
| Item | Value |
|---|---|
| Interactive demo (Transaction Evidence Dashboard) | **https://demo.pfprotocol.com** |
| Public verifier UI | **https://demo.pfprotocol.com/verify** |
| Admin / control-plane dashboard | **https://demo.pfprotocol.com/admin/login** (login) |
| Demo + sandbox API base | **https://demo.pfprotocol.com/api** |
| Generate a sandbox key | `POST https://demo.pfprotocol.com/api/demo/sandbox-key` (public, rate-limited; returns a real scoped key) |
| Interactive API docs (Swagger UI) | **https://demo.pfprotocol.com/api/docs** |
| ReDoc | **https://demo.pfprotocol.com/api/redoc** |
| OpenAPI (live JSON) | **https://demo.pfprotocol.com/api/openapi.json** |
| Developer resource index | **https://demo.pfprotocol.com/api/developer** |
| Sandbox key bootstrap | `GET https://demo.pfprotocol.com/api/config` → `test_api_key` (non-production only) |
| Status | 🟢 Live |

> The demo environment exposes the **full API surface** (demo, FEA sandbox,
> public verification, admin) **plus interactive docs**. It is the environment
> external reviewers and integrators evaluate against.

## 3. Production Integration API
| Item | Value |
|---|---|
| Production API base (provisioned/licensed integrators) | **https://api.pfprotocol.com/api** |
| Interactive API docs (Swagger UI) | **https://api.pfprotocol.com/api/docs** |
| ReDoc | **https://api.pfprotocol.com/api/redoc** |
| OpenAPI (live JSON) | **https://api.pfprotocol.com/api/openapi.json** |
| Developer resource index | **https://api.pfprotocol.com/api/developer** |
| Ingress host (Helm/K8s) | `api.pfprotocol.com` |
| Key provisioning | `POST /api/admin/api-keys/create` (admin JWT) — keys shown once |
| `/api/config` sandbox key | **Not exposed** when `ENVIRONMENT=production` |
| Status | 🟡 Code-ready (CORS allow-listed); requires the domain to be linked to the deployment — see §8 |

> **`api.pfprotocol.com` points to the SAME deployment as the demo domain.**
> There is no separate "API-only" build — the Kubernetes ingress routes `/api/*`
> to the backend regardless of which domain is attached, so **every endpoint,
> Swagger, OpenAPI, Postman, SDKs and docs work identically** under whichever
> domain you link. No code changes are required when the domain is added.

## 4. API Conventions
- All routes are prefixed with **`/api`**.
- **Data plane** (`/api/fea/*`, `/api/webhooks/*`): `X-API-Key: <key>`.
- **Control plane** (`/api/auth/*`, `/api/admin/*`): `Authorization: Bearer <jwt>`.
- **Public** (`/api/public/*`, `/api/demo/*`, system): no auth.
- **Sandbox key issuance** (`POST /api/demo/sandbox-key`): no auth,
  rate-limited (20/hour/IP); returns a real, scoped (`fea:write`/`fea:read`/
  `fea:verify`), 1-day sandbox key bound to the isolated `sandbox` tenant.
- **Interactive docs** (served by the backend, on any attached domain):
  - Swagger UI — `/api/docs`
  - ReDoc — `/api/redoc`
  - OpenAPI JSON (live) — `/api/openapi.json`
  - Developer resource index (links to all of the below) — `/api/developer`
- **Hosted developer resources** (read-only static, under `/api/resources/`):
  - OpenAPI YAML — `/api/resources/docs/openapi.yaml`
  - Postman collection — `/api/resources/docs/postman_collection.json`
  - Guides (Quickstart, Developer, Integration, API Reference, this file) —
    `/api/resources/docs/<NAME>.md`
  - SDK sources (Python, JavaScript, Java, .NET) — `/api/resources/sdks/<lang>/`
- Static spec files in-repo: [`openapi.yaml`](openapi.yaml) /
  [`openapi.json`](openapi.json). Full route table: [`API_REFERENCE.md`](API_REFERENCE.md).

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
| Developer Portal | https://demo.pfprotocol.com/developers | Canonical developer entry point | 🟢 Live |
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
| `https://pfp-api.preview.emergentagent.com` (internal preview pod) | `https://demo.pfprotocol.com` (demo/sandbox) or `https://api.pfprotocol.com` (prod) |
| `https://app.pfprotocol.com` (placeholder app origin) | `https://pfprotocol.com` and `https://demo.pfprotocol.com` |
| `DEMO_DB_NAME` / separate `pfp_demo` database | Removed — single DB + `demo_proofs` / `demo_key_registry` collections |

---

## 8. Adding `api.pfprotocol.com` to the deployment
`api.pfprotocol.com` is an **additional custom domain** on the *same* Emergent
deployment — not a new build. The code side is already done (CORS allow-list
includes it; `/api/*`, Swagger, OpenAPI, Postman, SDKs and docs are served on
any attached domain). Remaining steps are **domain/DNS** actions in the Emergent
UI:

1. Open the deployment → **Link domain** → type `api.pfprotocol.com` → click
   **Entri** and follow the on-screen DNS instructions. TLS/SSL is
   auto-provisioned.
2. DNS propagation: ~5–15 minutes (up to 24 h globally). If the site isn't up
   after 15 min, remove any conflicting `A` records and re-link via Entri.
3. After linking, **redeploy** so the production `CORS_ORIGINS` (which now
   includes `https://api.pfprotocol.com`) takes effect.
4. Verify: `https://api.pfprotocol.com/api/health` → `{"status":"healthy"}` and
   `https://api.pfprotocol.com/api/docs` renders Swagger.

> Whether **multiple** custom domains can attach to one deployment is a platform
> capability that may need confirmation from Emergent Support
> (support@emergent.sh) with your job ID. If only one custom domain is allowed
> per deployment, either (a) keep `demo.pfprotocol.com` as the single public
> origin (the API already lives at `demo.pfprotocol.com/api`), or (b) stand up a
> second deployment of this same repo and attach `api.pfprotocol.com` to it.
> No code differs between the two — same image, same `/api` surface.

---

## Crypto Agility, Federated Keys & Bring-Your-Own-Signing (v2.2.0)

PFP supports selectable signature suites — **Ed25519** (default), **ES256**
(ECDSA/secp256r1), **ES256K** (ECDSA/secp256k1) — a **federated key registry**
(customer/partner-owned keys via raw/JWK/SPKI-PEM with proof-of-possession,
validity windows and tenant ownership), and **Bring-Your-Own-Signing**
(per-tenant local / remote HTTP / cloud-KMS signers). All are **feature-flagged
and default OFF**; Ed25519 + FEA v1.1 remains the default and is fully backward
compatible. Verification binds the suite to the trusted registry key's algorithm
(algorithm-confusion / downgrade defense) and never depends on signer
availability. See **CRYPTO_AGILITY.md** for the authoritative reference,
threat analysis, migration and change-management gates.
