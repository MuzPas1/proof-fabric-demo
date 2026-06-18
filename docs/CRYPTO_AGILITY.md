# Crypto Agility, Federated Key Registry & Bring-Your-Own-Signing

> **Status:** Shipped (backend + SDKs). All capabilities are **feature-flagged
> and default OFF**. Ed25519 + FEA v1.1 remains the default and only active
> behaviour unless a suite/federated key/BYOS signer is explicitly enabled and
> selected. **Fully backward compatible** — existing proofs, proof IDs,
> verification APIs, SDKs, demo and auditor workflows are unchanged.

This document is the authoritative reference for the three capabilities and
covers architecture, API, SDK, verification, migration, change management, data
migration, security threat analysis, backward compatibility, and examples.

---

## 1. Overview

PFP evolved from a single-signature platform into a **crypto-agile, federated
proof fabric** while remaining strictly a *proof issuance + verification*
platform. PFP explicitly does **not** implement identity orchestration, wallets,
MPC, blockchain consensus/nodes, or payment routing — it integrates with such
systems, it does not replace them.

| Capability | What it adds | Default |
|---|---|---|
| **Crypto Agility** | `Ed25519` (default), `ES256` (secp256r1), `ES256K` (secp256k1) signature suites | Ed25519 only |
| **Federated Key Registry** | Customer/partner-owned public keys (raw / JWK / SPKI PEM) with proof-of-possession, validity windows, tenant ownership | off |
| **Bring-Your-Own-Signing** | Per-tenant signer: local KMS, remote HTTP signer, or cloud KMS (native) | platform LocalSigner |

---

## 2. Crypto Agility — Signature Suites

### 2.1 Supported suites

| Suite | Algorithm | Curve | Hash | Signature encoding |
|---|---|---|---|---|
| `Ed25519` | EdDSA | Curve25519 | (built-in) | raw 64 bytes, base64 |
| `ES256` | ECDSA | secp256r1 (NIST P-256) | SHA-256 | raw `r‖s` 64 bytes, base64, **low-S** |
| `ES256K` | ECDSA | secp256k1 | SHA-256 | raw `r‖s` 64 bytes, base64, **low-S** |

* The signing message is the **same deterministic canonical JSON** (PFP-JCS)
  prefixed with the existing domain separator `PFP_V2::` for ALL suites.
* ECDSA signatures are normalized to **low-S** on signing and **high-S is
  rejected** on verification (anti-malleability ⇒ deterministic verification).
* `algorithm` is a **signed field** inside the FEA payload (v1.1) and is bound to
  the trusted registry key's algorithm at verification time.

### 2.2 Selecting a suite

```http
POST /api/fea/generate
X-API-Key: <key>
{
  "idempotency_key": "...", "transaction_id": "...",
  "timestamp": "2026-06-10T12:00:00Z", "amount": 250000, "currency": "USD",
  "payer_id": "...", "payee_id": "...",
  "signature_suite": "ES256"        // optional: Ed25519 (default) | ES256 | ES256K
}
```

* If omitted → **Ed25519** (or the tenant's BYOS signer algorithm).
* A non-Ed25519 suite requires `ENABLE_CRYPTO_SUITES=true` AND a configured
  signing key for that suite; otherwise the request is rejected `400`.

### 2.3 Anti-confusion / anti-downgrade

The verifier resolves the public key from the registry, reads **the key's
algorithm** (the trusted source), and requires `payload.algorithm == key.algorithm`.
A payload that claims a different suite than its key is rejected:
`Algorithm mismatch … (algorithm-confusion defense)`. New suites are gated behind
`ENABLE_CRYPTO_SUITES` and require explicit selection — there is **no automatic
fallback** to a weaker algorithm.

---

## 3. Federated Key Registry

Register customer/partner-owned public keys so proofs they sign (via BYOS or
their own tooling) verify within PFP, with strong onboarding controls.

### 3.1 Key formats

* `raw` — base64 of the raw public key (Ed25519 32B; EC `0x04‖X‖Y` 65B).
* `jwk` — JWK object (`OKP/Ed25519` or `EC/P-256` / `EC/secp256k1`).
* `spki-pem` — base64 of an SPKI PEM/DER public key.

### 3.2 Onboarding flow (proof-of-possession)

```
POST /api/admin/keys/federated/register   (KEYS_MANAGE)
  body: { algorithm, key_format, public_key|jwk, owner, label?, not_before?, not_after? }
  -> { public_key_id, status:"pending", pop_challenge, pop_domain_prefix:"PFP_POP_V1::", expires_at }

# Sign (PFP_POP_V1:: + pop_challenge) with the matching PRIVATE key:
POST /api/admin/keys/federated/confirm     (KEYS_MANAGE)
  body: { public_key_id, pop_signature }
  -> { status:"active", pop_verified:true }
```

Proof-of-possession proves the registrant controls the private key for the
submitted public key — defeating **key-substitution** (registering someone
else's key). Challenges are single-use and auto-expire (TTL 15 min).

### 3.3 Validity windows, ownership, lifecycle

* `not_before` / `not_after` (optional, ISO-8601) — enforced at the proof's
  `iat` during verification.
* `owner` (`customer` | `partner`) + `tenant_id` — a non-platform key may only
  verify proofs of **its own tenant** (cross-tenant use rejected).
* Lifecycle: `pending → active → retired` (still verifies history) / `revoked`
  (fails verification immediately).

Federated keys appear in the public registry `GET /api/public/keys` with their
`algorithm`, `key_format`, `owner`, `tenant_id`, validity window and status.

---

## 4. Bring-Your-Own-Signing (BYOS)

Each tenant can route signing to a configured signer. **Verification never
contacts a signer** — it uses only the registered public key, so verification is
independent of signer availability/health.

| Signer | Custody | Notes |
|---|---|---|
| `local` | PFP KMS | Default; Ed25519/ES256/ES256K. |
| `remote` | Partner HTTP endpoint | Private key stays with the partner; PFP POSTs the canonical message, gets a signature, and re-checks it against the registered public key before use. |
| `cloud-kms` | AWS/GCP/Azure KMS | **Native** signing (key never leaves the KMS). Config-gated; raises a clear error until provisioned with provider credentials (see `KMS_MIGRATION_GUIDE.md`). |

### 4.1 Configure / inspect

```
POST   /api/admin/signers          (KEYS_MANAGE)  body: SignerConfig
GET    /api/admin/signers                          list tenant signers (secrets redacted)
GET    /api/admin/signers/health                   default + per-tenant signer health
DELETE /api/admin/signers          (KEYS_MANAGE)  remove tenant signer (revert to local)
```

Remote signer config:
`{"type":"remote","algorithm":"Ed25519","endpoint":"https://signer/...","public_key":"<b64>","auth_header":"Bearer ..."}`.
Cloud-KMS config:
`{"type":"cloud-kms","provider":"aws","key_ref":"arn:...","algorithm":"ES256","public_key":"<b64>"}`.

When a signer is configured its public key is auto-registered (active) so
verification works immediately and independently.

### 4.2 Remote signer contract

```
POST <endpoint>
  -> {"algorithm":"<suite>","message_b64":"<base64 of PFP_V2::+canonical>"}
  <- {"signature_b64":"<base64 raw signature>"}
```

A remote signer **outage fails issuance** (HTTP error) but **does not affect
verification** of previously issued proofs.

---

## 5. Independent verification (any suite)

Verification requires only the public key (`GET /api/public/keys`, match
`public_key_id`) and the payload's `algorithm`. SDKs auto-read `algorithm`.

```python
from pfp_sdk.verify import verify_fea
pub = next(k["public_key"] for k in keys["keys"] if k["public_key_id"] == fea["public_key_id"])
print(verify_fea(fea["fea_payload"], fea["signature"], pub))   # {'valid': True, ...}
```
```js
const { PFPClient } = require('@pfp/sdk');
PFPClient.verifyLocal(fea.fea_payload, fea.signature, pub);     // reads algorithm from payload
```

Shipped cross-SDK **test vectors** (`sdks/test_vectors.json`) contain one signed
proof per suite. Python + JavaScript parity is proven in CI
(`backend/tests/test_sdk_parity.py`, `sdks/javascript/parity_test.js`). The Java
and .NET verifiers are suite-aware (`SHA256withECDSA` / `ECDsa` with
`IeeeP1363` raw `r‖s`, low-S rejection).

---

## 6. Feature flags, rollout gates & change management

| Flag (env) | Default | Effect when OFF |
|---|---|---|
| `ENABLE_CRYPTO_SUITES` | `false` | Only Ed25519 selectable; non-Ed25519 `signature_suite` → 400 |
| `ENABLE_FEDERATED_KEYS` | `false` | Federated register/confirm → 403; tenant-isolation check inactive |
| `ENABLE_BYOS` | `false` | Signer config endpoints → 403; all signing uses platform LocalSigner |
| `DEFAULT_SIGNATURE_SUITE` | `Ed25519` | Default suite for issuance |

**Rollout gates (recommended):**
1. Enable in a **non-production** environment first; run the full regression +
   backward-compat suite (existing Ed25519 proofs must still verify).
2. Enable `ENABLE_CRYPTO_SUITES` → validate ES256/ES256K issue + independent
   verify (Python/JS) → only then consider federated/BYOS.
3. Enable `ENABLE_FEDERATED_KEYS` / `ENABLE_BYOS` **per tenant**, canary first.
4. **No default cutover:** `DEFAULT_SIGNATURE_SUITE` stays `Ed25519` until
   backward-compatibility evidence is complete.

**Rollback triggers:** any existing Ed25519 proof failing verification, any SDK
verification regression, or signer-induced issuance errors on the default
tenant. **Rollback:** set the relevant flag back to `false` (and/or
`DELETE /api/admin/signers` for a tenant) — no data migration is required.

---

## 7. Data migration

* **`key_registry`** — new fields (`key_format`, `jwk`, `tenant_id`, `owner`,
  `not_before`, `not_after`, `pop_verified`, `label`) are **all optional**.
  Legacy documents omit them; Pydantic supplies safe defaults
  (`algorithm="Ed25519"`, `owner=platform`, no validity window). **No
  migration script required; zero downtime; legacy and new records coexist.**
* **New `signers` collection** — per-tenant signer config; absent ⇒ LocalSigner.
* **New `pop_challenges` collection** — single-use PoP nonces (TTL auto-expire).
* **`feas`** — **no schema change**; the payload already carries `algorithm`.
* **Key rotation is now algorithm-scoped** — rotating the Ed25519 key no longer
  retires active ES256/ES256K keys.

---

## 8. Security threat analysis & mitigations

| Threat | Mitigation (implemented) |
|---|---|
| Algorithm confusion | Verify-suite bound to the **registry key's** algorithm; `payload.algorithm` must match → else reject. |
| Signature downgrade | New suites gated by `ENABLE_CRYPTO_SUITES` + explicit selection; no auto-fallback; legacy v1 still gated by `ACCEPT_LEGACY_V1`. |
| Key substitution | Proof-of-possession on federated registration; tenant ownership; verify checks `FEA.tenant_id == key.tenant_id`. |
| Replay | Existing dual-layer replay protection unchanged; PoP nonces single-use + TTL. |
| Remote signer abuse | Allow-listed endpoint, auth header, timeout; PFP re-verifies the returned signature against the known public key; signer only signs the **server-built** canonical message. |
| ECDSA malleability | Low-S enforced on sign; high-S rejected on verify (platform + SDKs). |
| Cross-tenant isolation | Federated key ownership + tenant binding enforced at verify; signer config is tenant-scoped. |

---

## 9. Backward compatibility (guaranteed)

Unchanged: Ed25519 default, FEA v1.1 default, PFP-JCS canonicalization, SHA-256
hashing, domain prefixes, proof_id derivation, replay protection, idempotency,
contract names (`fea_id`, `/api/fea/*`, schema names, operationIds), demo
trust-domain isolation, the auditor/demo UI, and `GET /api/public/verify/{id}`.
Existing SDK calls keep working (suite is auto-detected from the payload, default
Ed25519).

---

## 10. Examples per suite

```bash
# Ed25519 (default)
curl -s $API/api/fea/generate -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
  -d '{"idempotency_key":"e1","transaction_id":"T1","timestamp":"2026-06-10T12:00:00Z","amount":100,"currency":"USD","payer_id":"a","payee_id":"b"}'

# ES256 (secp256r1)
curl ... -d '{ ... ,"signature_suite":"ES256"}'

# ES256K (secp256k1)
curl ... -d '{ ... ,"signature_suite":"ES256K"}'

# Public verification (suite-agnostic)
curl -s $API/api/public/verify/<fea_id>
```
