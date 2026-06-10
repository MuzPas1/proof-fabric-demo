# PFP — Master Deliverables Index

Single source-of-truth index of every artifact produced for the Proof Fabric
Protocol enterprise hardening. Dates are file last-modified (UTC, June 2026).

## Architecture
| Document | Path | Purpose | Modified |
|---|---|---|---|
| Architecture | `/app/docs/ARCHITECTURE.md` | Component topology, trust boundaries, request lifecycles, data model, scaling | 2026-06-10 |

## Security
| Document | Path | Purpose | Modified |
|---|---|---|---|
| Security Architecture | `/app/docs/SECURITY_ARCHITECTURE.md` | Identity/access, RBAC, key mgmt, transport, rate limits, audit, residual risks | 2026-06-10 |
| Threat Model | `/app/docs/THREAT_MODEL.md` | STRIDE analysis, assets, abuse cases, top residual risks | 2026-06-10 |

## Cryptography
| Document | Path | Purpose | Modified |
|---|---|---|---|
| Cryptographic Architecture | `/app/docs/CRYPTOGRAPHIC_ARCHITECTURE.md` | Primitives, v1.1 signed payload, signing/verify, rotation, time anchoring | 2026-06-10 |
| Canonicalization Spec (PFP-JCS v1) | `/app/docs/CANONICALIZATION_SPEC.md` | Byte-exact deterministic JSON rules for cross-language verification | 2026-06-10 |

## API
| Document | Path | Purpose | Modified |
|---|---|---|---|
| API Reference | `/app/docs/API_REFERENCE.md` | All 34 paths grouped by category, auth schemes, status codes | 2026-06-10 |
| OpenAPI (JSON) | `/app/docs/openapi.json` | Machine-readable spec (regenerated from live app, 34 paths) | 2026-06-10 |
| OpenAPI (YAML) | `/app/docs/openapi.yaml` | YAML spec + server list | 2026-06-10 |
| Postman Collection | `/app/docs/postman_collection.json` | 35 requests, auth-aware, variables for base_url/api_key/jwt | 2026-06-10 |
| Swagger UI | `/app/docs/swagger.html` | Interactive docs shell (legacy) | 2026-05-25 |

## Integration
| Document | Path | Purpose | Modified |
|---|---|---|---|
| Integration Guide | `/app/docs/INTEGRATION_GUIDE.md` | Partner onboarding, issue/verify/batch/webhooks, error handling | 2026-06-10 |
| Developer Guide | `/app/docs/DEVELOPER_GUIDE.md` | Protocol developer reference (prior) | 2026-06-10 |
| Quickstart | `/app/docs/QUICKSTART.md` | Fast-start guide (prior) | 2026-06-10 |

## SDKs
| SDK | Path | Purpose | Modified |
|---|---|---|---|
| Python | `/app/sdks/python/` (`pfp_sdk/__init__.py`, `verify.py`, `canonicalize.py`, `pyproject.toml`) | Client + independent verification (PyNaCl). **Verified live.** | 2026-06-10 |
| JavaScript | `/app/sdks/javascript/` (`index.js`, `canonicalize.js`, `package.json`) | Client + independent verification (zero-dep, Node 18+). **Verified live.** | 2026-06-10 |
| Java | `/app/sdks/java/` (`PfpVerifier.java`, `PfpCanonicalizer.java`, `pom.xml`) | Independent verification (native Ed25519, Jackson). Source-complete. | 2026-06-10 |
| .NET | `/app/sdks/dotnet/` (`PfpVerifier.cs`, `Pfp.Sdk.csproj`) | Independent verification (BouncyCastle). Source-complete. | 2026-06-10 |
| SDK README | `/app/sdks/README.md` | Capability matrix + quick starts | 2026-06-10 |

## Operations
| Document | Path | Purpose | Modified |
|---|---|---|---|
| Operations Runbook | `/app/docs/OPERATIONS_RUNBOOK.md` | Service mgmt, dashboards/alerts, common ops, prod checklist | 2026-06-10 |
| Disaster Recovery | `/app/docs/DISASTER_RECOVERY.md` | RPO/RTO, backups, recovery procedures, failover | 2026-06-10 |
| Key Rotation Guide | `/app/docs/KEY_ROTATION_GUIDE.md` | Scheduled + emergency rotation, in-flight FEA handling | 2026-06-10 |
| Pilot Deployment Guide | `/app/docs/PILOT_DEPLOYMENT_GUIDE.md` | End-to-end pilot setup + go/no-go checklist | 2026-06-10 |
| Load Test Report | `/app/docs/LOAD_TEST_REPORT.md` | Performance baseline (prior) | 2026-06-10 |

## Deployment / Infrastructure
| Artifact | Path | Purpose | Modified |
|---|---|---|---|
| Dockerfile | `/app/deploy/Dockerfile` | Non-root multi-worker backend image + healthcheck | 2026-06-10 |
| docker-compose | `/app/deploy/docker-compose.yml` | Local stack (mongo + backend) | 2026-06-10 |
| K8s manifests | `/app/deploy/k8s/deployment.yaml`, `config.yaml` | Deployment/Service/HPA/Ingress + ConfigMap/Secret template | 2026-06-10 |
| Helm chart | `/app/deploy/helm/pfp/` | Chart.yaml, values.yaml, templates/deployment.yaml | 2026-06-10 |
| Terraform | `/app/deploy/terraform/main.tf` | Multi-cloud secret store + k8s namespace/secret | 2026-06-10 |
| CI/CD | `/app/.github/workflows/ci.yml` | Test → build → Trivy scan → deploy | 2026-06-10 |

## Readiness Assessments
| Document | Path | Purpose | Modified |
|---|---|---|---|
| Assessment v1 (baseline) | `/app/docs/PRODUCT_READINESS_ASSESSMENT.md` | Feb-2026 audit — 4/10, 5 critical blockers | 2026-06-10 |
| Assessment v2 (post-hardening) | `/app/docs/PRODUCT_READINESS_ASSESSMENT_V2.md` | June-2026 audit — 8/10 Pilot Ready; blocker resolutions | 2026-06-10 |
## Admin Dashboard
| Item | Detail |
|---|---|
| **URL** | `/admin` (login at `/admin/login`) — same repo, same deployment, same backend |
| Demo portal (unchanged) | `/` (TransactionFlow), public verify `/verify` |
| Source | `/app/frontend/src/admin/` — `AdminApp.jsx`, `AuthContext.jsx`, `Layout.jsx`, `Login.jsx`, `api.js`, `TenantConnect.jsx`, `ui.jsx`, `pages/*` |
| Modules | Overview · Tenants · API Keys · Signing Keys · Proof Explorer · Webhooks · Audit Log |
| Backend changes | **None** — uses only existing verified endpoints |

### Dashboard architecture
- Two auth planes, both pre-existing:
  - **Control plane (JWT + RBAC):** Overview, Tenants, API Keys, Signing Keys, Audit → `Authorization: Bearer <jwt>`.
  - **Data plane (tenant API key):** Proof Explorer, Webhooks → `X-API-Key` for the selected tenant (the `TenantConnect` component binds a tenant's key for the session). Because keys are server-side tenant-scoped, this *is* the isolation enforcement.
- Route tree `/admin/*` rendered by `AdminApp` inside the existing `BrowserRouter`; demo routes untouched.

### Authentication flow
1. `POST /api/auth/login {email,password}` → `{access_token, role, tenant_id, email}` (also sets httpOnly cookies).
2. Token stored in `localStorage`; axios attaches `Authorization: Bearer`. `GET /api/auth/me` validates the session on load.
3. `Protected` route guard redirects unauthenticated users to `/admin/login`; a 401 from any control-plane call clears the session and redirects.
4. Logout clears token + session-scoped tenant keys.

### Admin user guide (quick)
- **Sign in** at `/admin/login` (super_admin: `admin@pfprotocol.com`).
- **Tenants** → create customer isolation boundaries (super_admin only).
- **API Keys** → create a tenant-scoped key (raw value shown once; auto-bound for data-plane modules), revoke when needed.
- **Signing Keys** → view registry; rotate (returns new seed once), retire, revoke.
- **Proof Explorer / Webhooks** → pick a tenant connection (created key, pasted key, or dev sandbox) to browse that tenant's FEAs / manage webhooks. Switching tenants proves isolation.
- **Audit Log** → every action recorded; "Verify Chain" confirms hash-chain integrity.

| Verification Audit (this) | `/app/docs/PFP_VERIFICATION_AUDIT.md` | Evidence-based verification of all hardening claims | 2026-06-10 |

## Tests
| Artifact | Path | Purpose |
|---|---|---|
| Offline crypto/parity unit tests | `/app/backend/tests/test_crypto_unit.py` | 7 tests — canonicalization, signing roundtrip, SDK parity, key separation |
| API integration tests | `/app/backend/tests/test_pfp_api.py` | FEA generate/verify/idempotency/replay (v1.1) |
| Test reports | `/app/test_reports/iteration_7.json` | 56/56 backend tests pass |
