# Proof Fabric Protocol — Developer Guide

> **For external companies integrating PFP.**
> If you only need a 30-minute integration, jump to [**QUICKSTART.md**](./QUICKSTART.md).

---

## 1. What PFP is, and the problem it solves

When an important event happens across multiple systems — a settlement between
banks, an AI model's decision, a credential issuance, a shipment hand-off — each
party keeps its own record. Reconciling those records later requires trust:
others must trust that what each party shows them today matches what really
happened. That trust is brittle, and disputes are expensive.

**Proof Fabric Protocol (PFP)** is general-purpose proof infrastructure that
replaces that trust with **independently verifiable cryptographic evidence**:

- Every event is turned into a **Proof Artifact** — a deterministic, canonical
  JSON document with an Ed25519 signature. (The data-plane API and storage use
  the historical identifier `fea` / `fea_id`; it is a stable contract name, not
  a finance-only scope.)
- The Proof Artifact can be **re-verified by anyone**, using only the public key
  registry. No shared secret. No issuer round-trip required for verification.
- Replay protection guarantees an event can be evidenced **exactly once**.
  Idempotent issuance makes retries safe.

PFP applies across financial services, AI governance, education, telecom,
compliance, government, healthcare and supply chain. Concretely, it gives
integrators:

| Problem | PFP guarantee |
|---|---|
| Two parties show different data | Signed Proof Artifact pins the canonical record. |
| Records altered after the fact | Tampered artifacts fail `signature_valid`. |
| Same event issued twice with different data | `409 CONFLICT` on the replay. |
| Audit needs raw data | Verifier checks the signature against the public key — no data sharing required. |
| Key rotation / compromise | `active` / `retired` / `revoked` status per key; revoked keys fail verification. |

---

## 2. Base URLs

| Environment | URL |
|---|---|
| **Production API** | `https://api.pfprotocol.com` |
| **Live demo / sandbox** | `https://demo.pfprotocol.com` |

All endpoints are prefixed with **`/api`**. See
[`CANONICAL_ENDPOINTS.md`](./CANONICAL_ENDPOINTS.md) for the authoritative,
always-current list of PFP URLs and environment status.

---

## 3. Authentication

PFP uses **API key** authentication via the `X-API-Key` HTTP header.

```http
X-API-Key: pfp_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- **Sandbox:** `POST /api/demo/sandbox-key` issues a real, scoped, short-lived
  sandbox key (no auth, rate-limited) — used by the Developer Portal's
  "Generate Sandbox Key" button. Outside production, `GET /api/config` also
  returns a static `test_api_key`. Do not call `/api/config` from production.
- **Production:** keys are provisioned by the PFP team — email
  **support@pfprotocol.com** to request one.

Endpoints that require authentication are explicitly marked below. Public
verification endpoints (`/api/public/*`) require **no auth** so auditors can
verify independently.

---

## 4. Endpoint reference

### 4.1 `POST /api/fea/generate` — issue an FEA *(auth)*

Issue a new signed Proof Artifact.

**Request body (`GenerateFEARequest`)**

| Field | Type | Required | Notes |
|---|---|---|---|
| `idempotency_key` | string | ✅ | Unique per logical request. Safe to retry with the same value. |
| `transaction_id` | string | ✅ | Your transaction reference. |
| `timestamp` | string | ✅ | ISO-8601 UTC. Part of the global uniqueness key. |
| `amount` | integer | ✅ | **Smallest currency unit** (e.g. paise, cents). |
| `currency` | string(3) | ✅ | ISO-4217 code (`INR`, `USD`, …). |
| `payer_id` | string | ✅ | **Hashed / tokenized** payer identifier. Never raw PII. |
| `payee_id` | string | ✅ | Same convention as `payer_id`. |
| `metadata` | object | optional | Arbitrary JSON — bound to the FEA via `metadata_hash`. |

**Example request**

```bash
curl -X POST https://demo.pfprotocol.com/api/fea/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PFP_API_KEY" \
  -d '{
    "idempotency_key": "idem-2026-02-10-9f3a",
    "transaction_id": "TXN-8F2C-2026-00418",
    "timestamp": "2026-02-10T14:23:00Z",
    "amount": 245000,
    "currency": "INR",
    "payer_id": "sha256:7b9c…",
    "payee_id": "sha256:a14d…",
    "metadata": { "channel": "upi", "rail": "NPCI" }
  }'
```

**Response 200 (`FEAResponse`)**

```json
{
  "fea_id": "f1c2c45e-9c91-4f12-8e7c-2c5c5b1a4b0e",
  "fea_payload": {
    "fea_version": "1.0",
    "issuer_id": "pfp-issuer-001",
    "public_key_id": "key_0c6c7071b3086f1a",
    "transaction_summary": {
      "transaction_id": "TXN-8F2C-2026-00418",
      "timestamp": "2026-02-10T14:23:00Z",
      "amount": 245000,
      "currency": "INR"
    },
    "parties": { "payer_hash": "sha256:7b9c…", "payee_hash": "sha256:a14d…" },
    "metadata_hash": "8d51b…",
    "fea_hash": "9e2c4…"
  },
  "signature": "MEUCIQDp…base64…",
  "signature_version": "v2",
  "public_key_id": "key_0c6c7071b3086f1a",
  "created_at": "2026-02-10T14:23:01.221Z"
}
```

> **Persist the entire response** in your records. `fea_id` is what auditors
> use to re-verify; `fea_payload` + `signature` are what anyone needs to
> verify *without* round-tripping back to PFP.

---

### 4.2 `POST /api/fea/verify` — verify a payload + signature *(auth)*

For server-to-server verification.

**Request body (`VerifyFEARequest`)**

```json
{
  "fea_payload": { "...": "the exact payload returned at issue time" },
  "signature": "MEUCIQDp…base64…",
  "signature_version": "v2"
}
```

**Response (`VerifyFEAResponse`)**

```json
{ "valid": true, "reason": null, "signature_version": "v2", "verified_at": "2026-02-10T14:23:02.001Z" }
```

If invalid, `reason` explains why (e.g. `"Signature mismatch"`,
`"Key revoked"`, `"Key not found"`).

---

### 4.3 `GET /api/public/verify/{fea_id}` — independent verification *(no auth)*

The auditor / external verification path. Returns the stored payload, its
signature, and `signature_valid` re-computed at request time.

```bash
curl https://demo.pfprotocol.com/api/public/verify/f1c2c45e-9c91-4f12-8e7c-2c5c5b1a4b0e
```

Response (`PublicVerifyResponse`):

```json
{
  "fea_id": "f1c2c45e-9c91-4f12-8e7c-2c5c5b1a4b0e",
  "fea_payload": { "...": "..." },
  "signature": "MEUCIQDp…",
  "signature_version": "v2",
  "signature_valid": true,
  "issuer_id": "pfp-issuer-001",
  "created_at": "2026-02-10T14:23:01.221Z"
}
```

Errors: **404** when the `fea_id` is unknown.

---

### 4.4 `GET /api/public/keys` — key registry *(no auth)*

Returns all keys including retired ones (auditors verifying old FEAs need
them).

```json
{
  "keys": [
    {
      "public_key_id": "key_0c6c7071b3086f1a",
      "public_key": "<base64>",
      "algorithm": "Ed25519",
      "created_at": "2026-02-01T00:00:00Z",
      "status": "active"
    }
  ],
  "total": 1,
  "active_count": 1,
  "retired_count": 0
}
```

`status` is one of `active`, `retired`, `revoked`. Verification accepts
`active` and `retired`; **`revoked` always fails**.

---

### 4.5 System endpoints *(no auth)*

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/` | Service metadata + status. |
| `GET` | `/api/health` | Liveness check (`{ "status": "healthy" }`). |
| `GET` | `/api/config` | Sandbox-only test API key + issuer ID. Should be disabled in production. |

---

### 4.6 Demo endpoints — `/api/demo/*`

These power the public demo at **demo.pfprotocol.com** and are convenient
for prototyping, but they're **not the production integration surface**.
Production integrations should always use `/api/fea/*`.

- `POST /api/demo/issue` — issue a compliance-aware demo proof.
- `GET /api/demo/verify/{proof_id}` — verify a demo proof by ID.
- `POST /api/demo/artifact` — build a downloadable signed JSON artifact
  (`Content-Type: application/pfp-proof+json;v=1`).
- `POST /api/demo/artifact/verify` — independently verify an uploaded
  artifact.
- `POST /api/demo/proof` — stateless canonical-hash helper.

See **openapi.yaml** for full schemas.

---

## 5. Error codes

| HTTP | When | Body |
|---|---|---|
| `400` | Malformed input (bad timestamp, etc.). | `{ "detail": "Invalid timestamp" }` |
| `401` | Missing or invalid `X-API-Key`. | `{ "detail": "Invalid API key" }` |
| `404` | Unknown `fea_id`. | `{ "detail": "FEA not found: …" }` |
| `409` | Idempotency conflict OR replay attack. | `{ "detail": "Transaction replay detected with conflicting data" }` |
| `422` | Pydantic schema validation. | Array of `{loc, msg, type}` per FastAPI. |
| `429` | Rate limit. Honor `Retry-After`. | Standard slowapi response. |
| `5xx` | Backend error. Retry with exponential backoff. | `{ "detail": "..." }` |

---

## 6. Verification workflow

```
Issuer (you)        PFP                Auditor (anyone)
   │                  │                       │
   │  POST /fea/gen   │                       │
   │ ───────────────► │                       │
   │ ◄ FEAResponse    │                       │
   │   (fea_id +      │                       │
   │    signature)    │                       │
   │                  │                       │
   │ store FEA        │                       │
   │ + share fea_id   │                       │
   │ ────────────────────────────────────────►│
   │                  │                       │
   │                  │  GET /public/verify/  │
   │                  │ ◄─────────────────────│
   │                  │                       │
   │                  │ -- re-canonicalize    │
   │                  │ -- resolve kid → pub  │
   │                  │ -- Ed25519 verify     │
   │                  │ ─────────────────────►│
   │                  │  signature_valid: ✓   │
```

**Two equally valid verification paths:**

- **Server-to-server** — `POST /api/fea/verify` with the payload + signature
  you already hold (needs API key).
- **Independent / auditor** — `GET /api/public/verify/{fea_id}` (no API key)
  *or* fetch `/api/public/keys` and verify the signature locally with any
  Ed25519 library.

---

## 7. Replay protection

PFP enforces two complementary uniqueness guarantees:

1. **Idempotency key uniqueness** — the same `idempotency_key` may be reused
   only with **byte-identical payload**; in that case the original FEA is
   returned (HTTP 200). With a different payload → **409**.
2. **Transaction uniqueness** — the pair `(transaction_id, timestamp)` is
   globally unique. Reissuing with the same business payload returns the
   original FEA; reissuing with a different `amount`, `currency`, or party
   → **409**.

A retry policy that always sends the same `idempotency_key` for the same
logical operation is the recommended pattern (see code samples in §10).

---

## 8. Idempotency

- Generate `idempotency_key` per logical attempt (a UUIDv4 is fine).
- **Persist it before issuing**: if your service crashes mid-call, retry
  with the same key.
- For retries that observe a `409`, **investigate** — do not change the
  payload to "make it succeed". A `409` means the same `(transaction_id,
  timestamp)` already exists with different data, which is almost always a
  business-logic bug.

---

## 9. Rate limits

- Endpoint-level limits are enforced via slowapi.
- Today: `100 req/min` on `/api/`. FEA endpoints inherit FastAPI defaults
  and may be tightened per-tier.
- On `429`, honor the `Retry-After` response header. Exponential backoff is
  expected.

---

## 10. Integration examples

### 10.1 Python

```python
import os, uuid, requests

BASE = "https://demo.pfprotocol.com"
API_KEY = os.environ["PFP_API_KEY"]
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

def issue_fea(txn):
    payload = {
        "idempotency_key": txn["idem_key"],
        "transaction_id": txn["id"],
        "timestamp": txn["ts"],            # ISO-8601 UTC
        "amount": txn["amount_minor"],     # int, smallest unit
        "currency": txn["currency"],
        "payer_id": txn["payer_hash"],
        "payee_id": txn["payee_hash"],
        "metadata": txn.get("metadata"),
    }
    r = requests.post(f"{BASE}/api/fea/generate", json=payload, headers=HEADERS, timeout=10)
    if r.status_code == 409:
        raise RuntimeError(f"Replay/idem conflict: {r.json()['detail']}")
    r.raise_for_status()
    return r.json()  # store this whole response

def verify_public(fea_id):
    r = requests.get(f"{BASE}/api/public/verify/{fea_id}", timeout=10)
    r.raise_for_status()
    data = r.json()
    return data["signature_valid"], data

# Usage
fea = issue_fea({
    "idem_key": f"idem-{uuid.uuid4()}",
    "id": "TXN-8F2C-2026-00418",
    "ts": "2026-02-10T14:23:00Z",
    "amount_minor": 245000,
    "currency": "INR",
    "payer_hash": "sha256:7b9c…",
    "payee_hash": "sha256:a14d…",
})
print("FEA issued:", fea["fea_id"])
ok, info = verify_public(fea["fea_id"])
print("Auditor verify:", ok)
```

### 10.2 JavaScript (Node.js / TypeScript)

```ts
const BASE = "https://demo.pfprotocol.com";
const API_KEY = process.env.PFP_API_KEY!;
const headers = { "X-API-Key": API_KEY, "Content-Type": "application/json" };

export async function issueFEA(txn: {
  idemKey: string; id: string; ts: string;
  amountMinor: number; currency: string;
  payerHash: string; payeeHash: string;
  metadata?: Record<string, unknown>;
}) {
  const res = await fetch(`${BASE}/api/fea/generate`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      idempotency_key: txn.idemKey,
      transaction_id: txn.id,
      timestamp: txn.ts,
      amount: txn.amountMinor,
      currency: txn.currency,
      payer_id: txn.payerHash,
      payee_id: txn.payeeHash,
      metadata: txn.metadata,
    }),
  });
  if (res.status === 409) throw new Error(`Replay/idem conflict: ${(await res.json()).detail}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function verifyPublic(feaId: string) {
  const res = await fetch(`${BASE}/api/public/verify/${feaId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return { valid: data.signature_valid as boolean, data };
}
```

---

## 11. Security model

- **Algorithm:** Ed25519 (libsodium). 256-bit security, deterministic
  signatures, constant-time verification.
- **Canonicalization:** sorted-key JSON, UTF-8, no insignificant
  whitespace. Identical inputs always produce identical `fea_hash`.
- **Key resolution:** signatures embed a `public_key_id` (kid); verifiers
  look it up in the public registry. Keys carry a status — `revoked`
  always fails verification.
- **Domain separation:** every signed artifact format uses a unique domain
  prefix to prevent cross-protocol signature reuse.
- **Replay defence:** dual layer — idempotency key + `(transaction_id,
  timestamp)` compound uniqueness in the database.
- **No raw PII:** PFP never asks for or stores raw payer/payee identifiers
  — only hashed values.
- **Transport:** TLS 1.2+ on all endpoints.

### 11.1 Signing & key management (pluggable KMS)
- Signing keys are resolved through a **pluggable KMS abstraction**
  (`KMS_PROVIDER`): `local` (software, active) and **Cloud-KMS-ready** providers
  for AWS Secrets Manager, GCP Secret Manager and Azure Key Vault — switchable by
  configuration with no API or proof-format change. A **native HSM** provider
  (key never leaves the HSM) is a planned enhancement of the same interface.
- Production and demo use **separate signing keys** (distinct trust domains).
- Non-secret signing posture is observable at `GET /api/health` (`signing`) and
  `GET /api/developer` (`signing` capability profile) — never key material.
- Full migration steps, security model and **RFC-3161 time-anchoring readiness**
  are in [`KMS_MIGRATION_GUIDE.md`](./KMS_MIGRATION_GUIDE.md) and
  [`ARCHITECTURE.md`](./ARCHITECTURE.md) §8.

---

## 12. Best practices

1. **Hash before sending** — never put raw payer/payee identifiers in
   `payer_id` / `payee_id`. Send SHA-256 with a per-tenant salt.
2. **One `idempotency_key` per logical attempt.** Persist it before issuing.
3. **Store the entire `FEAResponse`** — `fea_id`, `fea_payload`,
   `signature`, `signature_version`, `public_key_id`. You'll need them all
   to verify offline.
4. **Verify on receipt** in your own code path, even when PFP says it
   succeeded — defence in depth.
5. **Treat 409 as a business bug**, not a transport error. Do not retry
   with a "fixed" payload.
6. **Pin your time source** — drifting clocks cause spurious timestamp
   mismatches. NTP or your cloud provider's sync service is fine.
7. **Don't log API keys.** Keep them in your secret manager.
8. **Rotate periodically** — request a fresh key annually or on incident.
   Old keys can be retired (verification still works for historical FEAs).

---

## 13. Support

- Integration & key provisioning: **support@pfprotocol.com**
- Status page: TBA
- Interactive API reference: open **`/docs/swagger.html`** in any browser
  (loads `openapi.yaml` next to it).

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
