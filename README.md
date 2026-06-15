# Proof Fabric Protocol (PFP)

Turn **any event** — a payment, an AI decision, a credential, a shipment, a
compliance record — into a **Proof Artifact**: a deterministic, Ed25519-signed,
content-addressed proof that **anyone** can independently verify with only the
public key, without trusting or contacting the issuer. PFP is general-purpose
proof infrastructure, applicable across financial services, AI governance,
education, telecom, compliance, government, healthcare and supply chain.

## Links
| What | URL |
|---|---|
| Product website | **https://pfprotocol.com** |
| Demo platform (Transaction Evidence Dashboard) | **https://demo.pfprotocol.com** |
| Developer Portal | **https://demo.pfprotocol.com/developers** |
| Admin portal | **https://demo.pfprotocol.com/admin/login** |
| Public verifier | **https://demo.pfprotocol.com/verify** |
| Production API base | **https://api.pfprotocol.com/api** |

> 📍 **Canonical, authoritative endpoint list:**
> [`docs/CANONICAL_ENDPOINTS.md`](docs/CANONICAL_ENDPOINTS.md).

## What's inside
- **Backend** (`backend/`): FastAPI + MongoDB. Ed25519 signing, deterministic
  canonicalization (PFP-JCS), idempotency + replay protection, persistent key
  registry, JWT+RBAC control plane, multi-tenancy, API-key data plane,
  webhooks, Prometheus metrics, hash-chained audit log.
- **Frontend** (`frontend/`): React demo portal (`/`), public verifier
  (`/verify`), admin dashboard (`/admin`), and a branded **Developer Portal**
  (`/developers`) with a live in-browser sandbox (generate key → sign proof →
  verify).
- **SDKs** (`sdks/`): Python, JavaScript, Java, .NET — client + **independent
  offline verification**.
- **Docs** (`docs/`): architecture, security, crypto, canonicalization spec,
  API reference + OpenAPI/Postman, integration & developer guides, runbooks,
  DR, deployment, readiness assessments. Start at
  [`docs/PFP_MASTER_INDEX.md`](docs/PFP_MASTER_INDEX.md).
- **Deploy** (`deploy/`): Dockerfile, docker-compose, Kubernetes, Helm,
  Terraform, CI/CD.

## Quick start
- **Integrate in 30 minutes:** [`docs/QUICKSTART.md`](docs/QUICKSTART.md).
- **Full developer reference:** [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md).
- **API reference:** [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

## Environment configuration
All config is environment-driven (no hardcoded secrets/URLs). Backend reads
`MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `KMS_PROVIDER`, `CORS_ORIGINS`, etc. from
the environment; the frontend uses `REACT_APP_BACKEND_URL`. See
[`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) for the full list.
