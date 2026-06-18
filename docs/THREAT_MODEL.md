# PFP — Threat Model (STRIDE)

Scope: PFP API, control plane, signing keys, data stores. Method: STRIDE per
trust boundary (see `ARCHITECTURE.md` §3).

## Assets
- Signing keys (production, demo) — highest value.
- Issued FEAs and their integrity.
- API keys, admin credentials, JWT secret.
- Audit trail integrity.
- Tenant data isolation.

## STRIDE analysis

### Spoofing
| Threat | Mitigation |
|---|---|
| Forged API key | Random 192-bit keys, SHA-256 stored, revocation + expiry checks |
| Forged admin session | HS256 JWT signed with `JWT_SECRET`, type-checked, user existence re-verified |
| Impersonating issuer (forging FEAs) | Ed25519 — forgery requires the private key (KMS-held) |

### Tampering
| Threat | Mitigation |
|---|---|
| Modify FEA payload | `fea_hash` + Ed25519 signature; verification recomputes and rejects |
| Tamper audit log | SHA-256 hash chain; `GET /api/admin/audit/verify` detects breaks |
| Substitute algorithm | `algorithm` field bound inside signature |
| Downgrade to legacy v1 | v1 rejected unless `ACCEPT_LEGACY_V1=true` |

### Repudiation
| Threat | Mitigation |
|---|---|
| "I never issued this" | `iat`, `jti`, `tenant_id` inside signed payload; audit entry |
| "When was it signed?" | Signed `iat`; optional RFC-3161 anchor (roadmap) |

### Information Disclosure
| Threat | Mitigation |
|---|---|
| API key leak via `/api/config` | Sandbox key only outside production; no key in prod |
| Cross-tenant data exposure | `tenant_id` filtering on all data-plane queries |
| PII in payload | Payer/payee are hashed/tokenized by contract; only `metadata_hash` stored |
| Secrets in logs | Field redaction in structured logger |

### Denial of Service
| Threat | Mitigation |
|---|---|
| Flood signing CPU | Rate limits on all write/sign endpoints; demo limited 60/min |
| Oversized body | `MAX_REQUEST_BYTES` (1 MiB) middleware |
| Unbounded demo writes | Isolated demo collections + rate limits |

### Elevation of Privilege
| Threat | Mitigation |
|---|---|
| Tenant admin acts on another tenant | `resolve_tenant_scope` blocks cross-tenant |
| Low role hits admin route | `require_permission` RBAC checks |
| API key escalates scope | Scope list enforced per request; immutable post-issue |

## Top residual risks (tracked)
1. **MongoDB without TLS/auth** in a misconfigured deployment → enforced via
   deployment manifests + ops runbook, not app code.
2. **Per-instance rate limiting** → add gateway/Redis limiter for cluster-wide.
3. **Software-key signing** → add HSM/native-KMS-sign provider.
4. **No external time anchor yet** → RFC-3161/transparency log on roadmap.
5. **No third-party pen test / crypto audit** → schedule before GA.

## Abuse cases
- *Mass minting of demo artifacts*: isolated to a separate demo signing key + dedicated demo collections, rate limited;
  cannot affect production trust.
- *Key compromise*: revoke via admin route (immediate verify-time effect),
  rotate, re-anchor. See `KEY_ROTATION_GUIDE.md` and `DISASTER_RECOVERY.md`.

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
