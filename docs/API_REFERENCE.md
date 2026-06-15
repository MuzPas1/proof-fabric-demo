# PFP — API Reference (v2.0.0)

Base URL `{BASE}` — production `https://api.pfprotocol.com`, live demo/sandbox
`https://demo.pfprotocol.com` (authoritative list:
[`CANONICAL_ENDPOINTS.md`](CANONICAL_ENDPOINTS.md)). All routes are prefixed
with `/api`. Machine-readable spec: [`openapi.json`](openapi.json) /
[`openapi.yaml`](openapi.yaml).

Auth schemes:
- **API key** (`X-API-Key`) — data plane (`/fea`, `/webhooks`).
- **JWT** (`Authorization: Bearer`) — control plane (`/auth`, `/admin`).
- **None** — public verification + system.

## System
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/` | none | Liveness + version + environment |
| GET | `/api/health` | none | Deep health: `database`, `key_registry`, `signing_service`, `demo_db` |
| GET | `/api/metrics` | none | Prometheus metrics |
| GET | `/api/config` | none | Endpoints map; sandbox key **only outside production** |

## Auth (control plane)
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/auth/login` | none | `{email,password}` → access+refresh tokens (+cookies) |
| GET | `/api/auth/me` | JWT | Current user |
| POST | `/api/auth/refresh` | cookie | New access token |
| POST | `/api/auth/logout` | JWT | Clears cookies |

## Admin (JWT + RBAC)
| Method | Path | Permission |
|---|---|---|
| POST | `/api/admin/api-keys/create` | `apikeys:manage` |
| GET | `/api/admin/api-keys` | `apikeys:manage` |
| POST | `/api/admin/api-keys/revoke?key_id=` | `apikeys:manage` |
| POST | `/api/admin/keys/create` | `keys:manage` |
| POST | `/api/admin/keys/rotate` | `keys:manage` |
| POST | `/api/admin/keys/revoke?public_key_id=` | `keys:manage` |
| POST | `/api/admin/keys/retire?public_key_id=` | `keys:manage` |
| POST | `/api/admin/tenants` | `tenants:manage` (super_admin) |
| GET | `/api/admin/tenants` | `tenants:manage` |
| GET | `/api/admin/audit` | `audit:read` |
| GET | `/api/admin/audit/verify` | `audit:read` |

## FEA (API key)
| Method | Path | Scope |
|---|---|---|
| POST | `/api/fea/generate` | `fea:write` |
| POST | `/api/fea/batch` | `fea:write` (≤500 items) |
| POST | `/api/fea/verify` | `fea:verify` |
| GET | `/api/fea?limit=&skip=` | `fea:read` |
| GET | `/api/fea/{fea_id}` | `fea:read` |

### `POST /api/fea/generate` body
```json
{ "idempotency_key": "string", "transaction_id": "string",
  "timestamp": "ISO-8601 UTC", "amount": 0, "currency": "ISO-4217 (3)",
  "payer_id": "hashed", "payee_id": "hashed", "metadata": {} }
```
Returns `fea_id`, signed `fea_payload` (v1.1 with `iat/jti/tenant_id/algorithm`),
`signature`, `public_key_id`, `created_at`.

## Public (no auth)
| Method | Path | Notes |
|---|---|---|
| GET | `/api/public/verify/{fea_id}` | PFP-attested verification + payload |
| GET | `/api/public/keys` | Public key registry (active/retired/revoked) |

## Webhooks (API key, scope `webhooks:manage`)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/webhooks/subscribe` | `{url,events}` → returns HMAC `secret` |
| GET | `/api/webhooks` | List subscriptions |
| POST | `/api/webhooks/test?webhook_id=` | Send a test delivery |
| DELETE | `/api/webhooks/{webhook_id}` | Remove subscription |

Delivery header: `X-PFP-Signature: sha256=<hmac-sha256(secret, body)>`.

## Demo (rate-limited, isolated collections, no auth)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/demo/proof` | Stateless canonical hash |
| POST | `/api/demo/issue` | Compliance-aware proof (`demo_proofs` collection) |
| GET | `/api/demo/verify/{proof_id}` | Lookup + re-hash |
| POST | `/api/demo/artifact` | Downloadable Ed25519 artifact (demo key) |
| POST | `/api/demo/artifact/verify` | Independent artifact verification |

## Status codes
`400` bad input · `401` auth · `403` scope/tenant/role · `404` not found ·
`409` idempotency/replay · `413` body too large · `422` schema · `429` rate limit.
