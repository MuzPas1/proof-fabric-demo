# Proof Fabric Protocol (PFP) — Product Readiness Assessment

**Reviewers:** Principal Solutions Architect / Enterprise Integration Architect / API Architect / Product Auditor / Technical DD
**Date of review:** Feb 2026
**Scope:** Full codebase, architecture, schemas, APIs, crypto, security, deployment, docs
**Tone:** Adversarial. Treated as if a partner like a bank, telco or government would put this through a 30-day technical due diligence before a pilot.

> Bottom line up front (verdict in §11): **C+ — Functional MVP / Demo-Grade**. The cryptographic core is sound and well-tested. The product around it (auth, multi-tenancy, key lifecycle, operations, deployment, SDKs, observability) is not pilot-ready for an enterprise partner. Do not commit to a 30-day pilot without addressing the **5 critical blockers** in §9.

---

## 1. Current Product Inventory

### 1.1 Implemented capabilities (real, not claimed)

| Capability | Status | Evidence |
|---|---|---|
| Deterministic JSON canonicalization | ✅ Real | `backend/crypto/canonicalize.py` (sorted keys, null-strip, timestamp normalize, float→int when whole) |
| SHA-256 hashing of canonical JSON | ✅ Real | `backend/crypto/hashing.py` |
| Ed25519 signing (v2, with domain prefix `PFP_V2::`) | ✅ Real | `backend/crypto/signing.py` `sign_message()` |
| Ed25519 signing — legacy v1 (sign the hash, no prefix) | ✅ Real but legacy / footgun | `sign_hash()` and `verify_signature_v1()` still active code paths |
| Constant-time hash & signature compare | ✅ Real | `hmac.compare_digest` in `signing.py` + `verification_service.py` |
| Idempotency by `idempotency_key` (same payload returns same FEA, different payload → 409) | ✅ Real | `fea_routes.py:90-111` |
| Replay protection by compound unique index `(transaction_id, timestamp)` | ✅ Real | `server.py:97-126` |
| Persistent MongoDB key registry with status `active / retired / revoked` | ✅ Schema real, **administrative endpoints not exposed** | `models/key_registry.py`, `services/key_service.py` |
| Downloadable signed artifact (Ed25519, schema v1, `PFP_ARTIFACT_V1::` domain) | ✅ Real | `services/artifact_service.py` + `/api/demo/artifact*` |
| Public verification by `fea_id` or by uploaded artifact | ✅ Real | `/api/public/verify/{fea_id}` and `/api/demo/artifact/verify` |
| Industry-aware compliance metadata embedded in canonical payload (demo only) | ✅ Real (added Feb 2026) | `routes/demo_routes.py` + `lib/industries.js` |
| Cross-party consistency proof comparison | ✅ Real (stateless hash) | `/api/demo/proof` |
| Rate limiting | ⚠️ Only on `GET /api/` root. No other endpoint is limited. | `server.py:139` is the only `@limiter.limit` |
| API-key authentication for `/api/fea/*` | ⚠️ Real **but in-memory only** | `routes/auth.py` `_api_keys: dict` |

### 1.2 Implemented API endpoints (12 total — extracted from FastAPI's OpenAPI)

| Method | Path | Auth | Tag | Notes |
|---|---|---|---|---|
| GET | `/api/` | none | — | rate-limited 100/min |
| GET | `/api/health` | none | — | DB connectivity NOT checked |
| GET | `/api/config` | **none** | — | **Returns the test API key to anyone** — see §6.1 |
| POST | `/api/fea/generate` | X-API-Key | FEA | Idempotent + replay-protected |
| POST | `/api/fea/verify` | X-API-Key | FEA | Verifies external payload + signature |
| GET | `/api/public/verify/{fea_id}` | none | Public | Looks up DB + re-verifies |
| GET | `/api/public/keys` | none | Public | Full key registry |
| POST | `/api/demo/proof` | none | Demo | Stateless cross-party hash |
| POST | `/api/demo/issue` | none | Demo | Persists a "demo" proof |
| GET | `/api/demo/verify/{proof_id}` | none | Demo | Lookup + re-hash verify |
| POST | `/api/demo/artifact` | none | Demo | Returns downloadable signed JSON |
| POST | `/api/demo/artifact/verify` | none | Demo | Independent verification |

### 1.3 Implemented MongoDB collections

| Collection | Indexes | Purpose | Notes |
|---|---|---|---|
| `feas` | `fea_id` unique, `idempotency_key`, `(transaction_id, timestamp)` unique | Production FEAs | Replay-protection compound index has a runtime-deduplication fallback (`server.py:101-128`) — fragile in concurrent boot |
| `key_registry` | `public_key_id` unique | Public key registry (active/retired/revoked) | No TTL, immutable by convention only — nothing prevents direct DB write |
| `demo_proofs` | none | Demo issue/verify history | **Lives in the SAME DB as production data** |

### 1.4 Cryptographic capabilities

| Primitive | Where | Real? |
|---|---|---|
| Ed25519 sign/verify (PyNaCl 1.6.2) | `crypto/signing.py`, `artifact_service.py` | Yes |
| SHA-256 over canonical JSON for `fea_hash` and `proof_id` | `crypto/hashing.py` | Yes |
| Domain separation `PFP_V2::` (FEA), `PFP_ARTIFACT_V1::` (Artifact) | `signing.py`, `artifact_service.py` | Yes — but two different separators across two formats |
| Deterministic JSON (RFC-8785-like, custom) | `canonicalize.py` | Yes — but not RFC-8785/JCS strict; see §7 risks |
| Constant-time compare | `hmac.compare_digest` | Yes |
| Key revocation enforcement at verify-time | Artifact verifier reads DB live; FEA verifier reads in-memory cache via `get_public_key_bytes_by_id` (cache populated at boot) | **Inconsistent** — see §7 |

### 1.5 Authentication / Authorization mechanisms

| Layer | Mechanism | Real? |
|---|---|---|
| `POST /api/fea/*` | `X-API-Key` header → SHA-256 hash → in-memory `dict` lookup | Yes, but ephemeral |
| Demo endpoints | None | N/A |
| Public verify | None | By design |
| Admin endpoints (key rotation, retirement, revocation, key issuance) | **Not exposed** — only internal functions exist (`retire_key`, `rotate_key`) | **Missing** |
| RBAC / scopes / tenant isolation | None | **Missing** |
| mTLS / request signing for B2B | None | **Missing** |

### 1.6 What is real vs demo/mock

| Component | Classification |
|---|---|
| Ed25519 + canonical JSON + SHA-256 pipeline | **Real** |
| FEA generate / verify endpoints | **Real (single tenant)** |
| Industry compliance checks | **Demo/UI simulation** — backend accepts and signs whatever the client sends; there is no actual KYC/AML/sanctions integration |
| Cross-party consistency | **Real hash equality**, but the "Party B" amount in the UI is a hardcoded simulated mismatch toggle |
| Compliance status (`COMPLIANT`/`NON-COMPLIANT`) | **Client-asserted**, signed verbatim. PFP does not adjudicate. |
| Key registry "rotation" | **Service code exists, no admin route** |
| Multi-tenant / multi-issuer | **Not implemented** — single `ISSUER_ID` env var, single global signing key |
| Webhooks / async / batch | **Not implemented** |
| Audit log of admin actions | **Not implemented** |

---

## 2. API Audit

### 2.1 Generated OpenAPI

The FastAPI app already exposes a live OpenAPI doc at `/openapi.json` (auto-generated). The hand-maintained `/app/docs/openapi.yaml` is stale — it predates `/api/demo/artifact*` and the industry-aware demo fields. **Use the auto-generated spec as the source of truth, treat the YAML as documentation drift.**

### 2.2 Per-endpoint audit

#### `POST /api/fea/generate` — auth: X-API-Key
- **Inputs:** `idempotency_key`, `transaction_id`, `timestamp` (ISO-8601), `amount` (int, smallest unit), `currency` (3-char), `payer_id`, `payee_id`, `metadata?`
- **Outputs:** `fea_id` (uuid4), `fea_payload` (canonical, includes `fea_hash`), `signature` (base64 Ed25519), `signature_version` ("v2"), `public_key_id`, `created_at`
- **Errors:** `400` invalid timestamp / shape, `401` missing or bad API key, `409` idempotency conflict OR transaction replay with conflicting data
- **Rate limit:** **None.** Anyone with the API key can fire as many writes as they want.
- **Gaps:**
  - No tenant binding — the API key has no scopes, no quota, no ownership
  - `amount` is `int` here but `string` in demo endpoints — type drift across the same product
  - No size limits on `metadata` (Pydantic accepts arbitrary dict)
  - `idempotency_key` has no TTL; collection grows forever
  - Timestamp validation is *skipped* (`skip_timestamp_validation=True` in `fea_routes.py:126`) despite the function existing — **the +5min/−1yr bound only runs in stateless `generate_fea()` test paths, not in the actual endpoint**

#### `POST /api/fea/verify` — auth: X-API-Key
- Why is this authenticated? Verification of a public payload using public keys is a public operation. This is a confused trust model.

#### `GET /api/public/verify/{fea_id}` — auth: none
- Discloses the full `fea_payload` (including `transaction_summary.amount`, `currency`, `payer_hash`, `payee_hash`) to anyone with the `fea_id`. Hashed identifiers, but a UUID `fea_id` is the only thing standing between the world and a transaction's structure. There is **no entitlement check**.

#### `GET /api/public/keys` — auth: none
- Returns the entire key registry (active + retired + revoked) with no pagination. Acceptable for now (registry size is tiny), but no `If-None-Match` / ETag / `last-updated` for caching.

#### `POST /api/demo/*` — auth: none
- **All five demo endpoints are public, unauthenticated writes** persisting into the same MongoDB instance as production FEAs. In a deployed environment, anyone can DoS-write the `demo_proofs` collection at will. No rate limit, no captcha, no token.

#### `GET /api/config` — auth: none
- **Returns the live test API key in plaintext.** Verified just now: `curl $URL/api/config` → `{"test_api_key":"pfp_test_..."}`. This is a **critical security defect** if the same code runs in production. See §6.1.

#### `GET /api/health`
- Returns a constant `{"status":"healthy"}`. **It does not check DB connectivity, key registry availability, or signing key loadability.** Useless for a real load balancer.

### 2.3 Rate limiting

- Single `@limiter.limit("100/minute")` on `GET /api/`. **Every other route is unlimited** including `POST /api/fea/generate` (writes), `POST /api/demo/issue` (writes), `POST /api/demo/artifact` (signing CPU). An attacker can saturate signing CPU at ~340 TPS (per load test report) without authentication via `/api/demo/artifact`.

### 2.4 Missing endpoints required for enterprise integration

| Missing endpoint | Why it matters |
|---|---|
| `POST /admin/keys/rotate` (with admin auth) | Documented as P1 in PRD, code exists in `key_service.rotate_key`, no route |
| `POST /admin/keys/{kid}/revoke` | Revocation is enforced at verify, but no operator path to trigger it |
| `POST /admin/keys/{kid}/retire` | Same — function exists, route doesn't |
| `POST /admin/api-keys` | No way to issue customer-bound API keys. The only key is auto-generated on boot. |
| `DELETE /admin/api-keys/{kid}` | No revocation |
| `GET /admin/audit` | No admin action log |
| `POST /fea/batch` | Documented as P1 — not implemented. Critical for high-volume reconciliation use cases (which the load test report itself highlights) |
| `POST /webhooks/subscribe` + `POST /webhooks/test` | No outbound integration model |
| `GET /fea/{fea_id}` (authenticated single-FEA fetch) | Only the **public** verify lookup exists; an authenticated tenant cannot fetch their own FEA by ID over a private channel |
| `GET /fea?since=…&limit=…` | No listing / pagination — auditors cannot iterate the FEA stream |
| `GET /metrics` (Prometheus) | No machine-readable health/perf |
| `POST /v1/proofs/anchor` (timestamp anchor / blockchain notarization) | The product positions itself as cryptographic evidence — no third-party time anchoring is implemented |

### 2.5 Incomplete / non-functional APIs

- `GET /api/config` is functional but should not exist in this form in production.
- `/api/fea/verify` returns `verified_at` but the field has no integrity binding — a caller can't prove "PFP verified this at time T."
- `OpenAPI yaml` in `/app/docs/` is **drift** — does not include the artifact endpoints or industry fields.

---

## 3. SDK Readiness

**Today: no SDK exists.** Integrators get a YAML and curl examples. That is a hand-rolled experience for every partner. Worse, the YAML is out of date.

### 3.1 Can external developers integrate today?

Technically yes (REST + JSON), practically no:
- API key must be retrieved out-of-band — `/api/config` works in dev only; there is no customer onboarding flow.
- No client side canonicalization library is published, so a customer who wants to **independently** recompute `fea_hash` before signing or before verifying needs to re-implement the canonicalization rules byte-perfectly (sorted keys, `null` stripping at *every* depth, the float→int rule, the timestamp normalization regex). Re-implementing this in Java or .NET is non-trivial and error-prone. **This is the single biggest practical blocker to multi-platform pilots.**
- The "v1 vs v2" signing model still exists in the verify path and is exposed to the integrator via `signature_version` — they have to handle two formats.

### 3.2 Minimal SDK shims (illustrative — these do not exist in the repo)

```python
# Python SDK shim (NOT in the codebase — illustrative only)
import requests, json
class PFP:
    def __init__(self, base, api_key): self.base, self.h = base, {"X-API-Key": api_key, "Content-Type":"application/json"}
    def generate(self, **kw): return requests.post(f"{self.base}/api/fea/generate", headers=self.h, json=kw).json()
    def verify(self, fea_payload, signature, version=None):
        return requests.post(f"{self.base}/api/fea/verify", headers=self.h,
                             json={"fea_payload":fea_payload,"signature":signature,"signature_version":version}).json()
    def public_verify(self, fea_id):
        return requests.get(f"{self.base}/api/public/verify/{fea_id}").json()
```

```javascript
// JS SDK shim (NOT in the codebase — illustrative only)
export class PFP {
  constructor(base, apiKey){ this.base=base; this.h={ "X-API-Key":apiKey, "Content-Type":"application/json" } }
  generate(body){ return fetch(`${this.base}/api/fea/generate`,{method:"POST",headers:this.h,body:JSON.stringify(body)}).then(r=>r.json()) }
  verify(p,s,v){ return fetch(`${this.base}/api/fea/verify`,{method:"POST",headers:this.h,body:JSON.stringify({fea_payload:p,signature:s,signature_version:v})}).then(r=>r.json()) }
}
```

```java
// Java SDK shim (NOT in the codebase — illustrative only)
// Uses java.net.http.HttpClient; omitted body for brevity — same shape.
// Verification on the Java side would require porting canonicalize.py exactly.
```

**None of these are sufficient for a real integration** because they do not give the integrator a *local* canonicalize+verify capability — they remain dependent on the PFP server to verify. That defeats the "independently verifiable" promise.

---

## 4. Integration Readiness (enterprise customer perspective)

Suppose a telco wants to integrate PFP for invoice evidence.

### 4.1 What they must send (today)
- An `X-API-Key` they cannot self-provision (they have to email us)
- A POST to `/api/fea/generate` with the 7 required fields + optional `metadata`
- They must already have hashed/tokenized `payer_id` / `payee_id` (the API documents this but doesn't enforce it — they could send PII)

### 4.2 What PFP stores
- `fea_id`, `idempotency_key`, `canonical_payload_hash`, `transaction_payload_hash`, the full `fea_payload`, `signature`, `signature_version`, `public_key_id`, `created_at`
- **No tenant column.** All customers' FEAs sit in one collection. A bug in a public verify route could expose any customer's record to any other.

### 4.3 What they get back
- `fea_id` (uuid4) + the canonical `fea_payload` echo + base64 Ed25519 `signature` + `signature_version` + `public_key_id` + `created_at`

### 4.4 How verification works
- **Authenticated:** `POST /api/fea/verify` with the payload + signature
- **Public:** `GET /api/public/verify/{fea_id}` (PFP looks up its own DB and re-runs the verifier — this is **not** independent verification, it's PFP-attested verification)
- **Truly independent:** Only via the *artifact* path (`POST /api/demo/artifact` to download → `POST /api/demo/artifact/verify` to re-check), and that path is **on the "demo" namespace**. There is no "production" independent artifact format.

### 4.5 How revocation / versioning works
- Key revocation: schema present (`status: revoked`), no admin endpoint. Operator must `db.key_registry.updateOne(...)` by hand in MongoDB. **No artifact-level revocation list (no CRL/OCSP analogue).** A signed FEA, once issued, cannot be revoked.
- Versioning: only `fea_version: "1.0"` is recognized. There is no migration / deprecation policy documented.

### 4.6 Integration effort estimate (honest)

| Customer maturity | Effort to first signed FEA in their staging | Effort to truly independent verification on their side |
|---|---|---|
| Senior backend team, willing to do REST + JSON | 0.5 day | **3–5 days** because they must port canonicalize.py rules byte-perfect |
| Compliance/audit team without strong devs | 2–3 days for REST | **2+ weeks**, will likely depend on PFP-side verify which defeats the value prop |

---

## 5. Proof Artifact Review

### 5.1 Real sample (from live API just now)

```json
{
  "fea_id": "3691df09-ddb5-4d68-bbb6-e24e9b0d232a",
  "fea_payload": {
    "fea_version": "1.0",
    "issuer_id": "pfp-issuer-001",
    "public_key_id": "key_0c6c7071b3086f1a",
    "transaction_summary": {
      "transaction_id": "TXN-AUDIT-001",
      "timestamp": "2026-02-25T12:00:00.000Z",
      "amount": 250000,
      "currency": "INR"
    },
    "parties": { "payer_hash": "payer_h_abc123", "payee_hash": "payee_h_xyz789" },
    "metadata_hash": "571fef69749cf26758c473598c361132e6b09a70b64791c188b746671eae3f77",
    "fea_hash": "9d48b29f29912f8f75fac0e5c6ce3a5cbd021a00727a9a51b67f91c5bbdf4574"
  },
  "signature": "hBQk4onNHKpVEXNEs80PQXRobIz0TjjvsxQdhywogXHyllrzTWCfsgiK+gdWzYYsNgkSWjslxGrVycj1KlLzAw==",
  "signature_version": "v2",
  "public_key_id": "key_0c6c7071b3086f1a",
  "created_at": "2026-06-10T15:10:21.612028+00:00"
}
```

### 5.2 Generation lifecycle
1. Validate request shape (Pydantic)
2. `idempotency_key` lookup → return existing if same canonical hash, 409 if conflicting
3. `(transaction_id, normalized_timestamp)` replay check → return existing if same `transaction_payload_hash`, 409 if conflicting
4. Build `fea_payload` (no `fea_hash` yet) → canonicalize → SHA-256 → set `fea_hash`
5. Canonicalize entire payload (now with `fea_hash`) → `signature = Ed25519.sign("PFP_V2::" + canonical_json)` → base64
6. Compute `canonical_payload_hash` (includes `idempotency_key`, for idempotency lookup)
7. Compute `transaction_payload_hash` (excludes `idempotency_key`, for replay)
8. Insert into `feas`. **No DB transaction** — if the insert fails after step 5, the client gets an error but the signing key already produced a signature artifact (low-risk, but worth noting).

### 5.3 Verification lifecycle
1. Validate `fea_version` ∈ {"1.0"}
2. Detect `signature_version` from external arg → payload → legacy prefix
3. Recompute `fea_hash` by canonicalizing payload-minus-`fea_hash`, then constant-time compare
4. Resolve `public_key_id` against `key_registry` (DB → cache fallback → current key fallback)
5. Verify Ed25519 over canonical full payload with `PFP_V2::` prefix (for v2)

### 5.4 Missing fields / weaknesses
- **No `iat` (issued at) inside the signed payload.** `created_at` lives outside the signature. An auditor reading only the signed payload cannot tell when PFP signed it — only when the transaction supposedly occurred.
- **No `exp` / validity window.** A signature is good "forever," which is fine but should be explicit.
- **No `jti` / unique nonce.** The replay protection is *server-side* via DB uniqueness; the signed artifact itself does not contain a nonce, so two different signatures over the *same payload* are possible across two issuers (or across a restart that drops state).
- **No `iss` distinct from `issuer_id`.** `issuer_id` is a string the operator sets, not a verifiable identity.
- **No `tenant_id` / `customer_id`.** Cannot prove "which customer requested this."
- **No `algorithm` / `signature_alg` inside the signed payload** — the verifier infers Ed25519. An attacker who substitutes a different key/algo would need to also tamper with the signature; the integrity comes from the signature itself, but explicit algorithm binding is best practice (algorithm-confusion defense).
- **`metadata_hash` is included if metadata is present, but the metadata itself is not stored.** Once the original metadata is gone, the hash is unverifiable. That's by design ("we don't store PII") but it should be documented as a feature, not left implicit.
- **Two artifact formats exist** — the FEA `fea_payload` and the downloadable artifact (`PFP_ARTIFACT_V1::` domain). Schemas are similar but not identical (artifact has `version: 1` int, FEA has `fea_version: "1.0"` string). Pick one.

---

## 6. Security Review

### 6.1 🔴 CRITICAL: Test API key publicly exposed
`GET /api/config` returns `{"test_api_key": "pfp_test_..."}` with **no auth**. The key authorizes `POST /api/fea/generate`. Anyone scanning the internet finds it. In the live preview right now:
```
$ curl https://pfp-evidence.preview.emergentagent.com/api/config
{"test_api_key":"pfp_test_d2e44e17ba6ef818ff8ccf4cf532279b68fd3038b975462d", ...}
```
**Action:** delete this endpoint or guard it behind an admin-only auth before any external pilot.

### 6.2 🔴 CRITICAL: API key store is in-memory dict
`routes/auth.py` keeps `_api_keys: dict = {}`. The "test" key is regenerated on every backend restart. There is no DB-backed customer key management. A horizontally scaled deployment (or even a `--workers 8` deployment as the load-test report suggests) will have **each worker with its own dict** — keys generated by worker A won't validate on worker B. This is structurally broken for production.

### 6.3 🔴 CRITICAL: Signing key stored as plaintext base64 in `.env`
`PRIVATE_KEY="8vU9cBlfDyl7lnuubAUtxAPlZQ5uAuGtHShS6OhwZ9Y="` lives on disk in `/app/backend/.env`. There is no HSM, no KMS (AWS KMS / GCP KMS / Azure Key Vault), no envelope encryption. Exfiltrating one file = forging FEAs forever. For any regulated customer this is a non-starter.

### 6.4 🔴 CRITICAL: Demo endpoints are public writes
`/api/demo/issue` and `/api/demo/artifact` are unauthenticated, unmetered, and write into the same MongoDB instance as production. An attacker can:
- Fill `demo_proofs` until disk is exhausted
- Burn signing CPU at ~340 TPS without an account
- Generate ostensibly "PFP-signed" artifacts that share the **same `kid`** as production FEAs

The last point is particularly bad: anyone can mint a signed `PFP_ARTIFACT_V1::` JSON with arbitrary transaction_id / amount / compliance, and the signature is genuine. Domain separation (`PFP_ARTIFACT_V1::` vs `PFP_V2::`) prevents cross-format confusion, but the signing key is the same — so the trust boundary leaks into the public verifier UX.

### 6.5 🟡 HIGH: CORS wide-open (`*`)
`CORS_ORIGINS="*"` in `.env`. Any origin can hit any endpoint from a browser, including a malicious site that auto-submits demo proofs in the background.

### 6.6 🟡 HIGH: No TLS / auth to MongoDB
`MONGO_URL="mongodb://localhost:27017"` — no `mongodb+srv`, no `?tls=true`, no `username:password@`. Acceptable in the sandbox, but the deployment guide must mandate a TLS-enabled, auth-enabled cluster before any pilot.

### 6.7 🟡 HIGH: Rate limiting on writes is absent
Only `GET /api/` is limited. Signing endpoints are unlimited.

### 6.8 🟡 HIGH: `verify_signature_v1` (legacy) is still mounted
The legacy hash-signing path can verify "v1" signatures. If a customer ever submits a `signature_version: "v1"` payload that someone produced with `sign_hash`, the path still works. This is a downgrade-attack surface area — there is no policy "we no longer accept v1 signatures."

### 6.9 🟡 HIGH: Timestamp validation is silently skipped in verify
`verification_service.verify_fea` calls `validate_timestamp` but, on failure, hits `pass # Allow for backward compatibility`. So a payload with a timestamp 10 years in the future will still verify if the signature is good. Documentation says "≤5 min future skew, ≤1 year past" — the code does not enforce this on verify.

### 6.10 🟢 LOW: Other notable hygiene gaps
- No security headers (HSTS, CSP, X-Content-Type-Options, X-Frame-Options) on the FastAPI app
- No request body size cap → `metadata: {...huge...}` denial of service
- No structured audit log of admin actions or key rotations
- No `/metrics` endpoint
- No PII detection / blocklist on `payer_id` / `payee_id`
- No log redaction policy

---

## 7. Cryptography Review

### 7.1 What is actually implemented
| Primitive | How it's used | Verdict |
|---|---|---|
| **Ed25519** (PyNaCl) | Sign canonical JSON message; verify with public key | ✅ Standard, sound |
| **SHA-256** | Hash canonical JSON to produce `fea_hash` and `proof_id` | ✅ Sound |
| **Domain separation** `PFP_V2::` for FEA, `PFP_ARTIFACT_V1::` for artifact | Prepended to message bytes before signing | ✅ Good — but the existence of two separators bound to *the same signing key* is an organizational smell |
| **Constant-time compare** | `hmac.compare_digest` for hash + signature paths | ✅ Good |
| **Canonical JSON** | Custom (sorted keys, null-strip, timestamp normalize, float→int when whole, no whitespace) | ⚠️ See risks below |

### 7.2 Claims vs reality
| Claim made by the product | Real? | Notes |
|---|---|---|
| "Deterministic canonicalization" | ✅ Mostly — same dict produces same bytes | But the float→int collapse is **non-RFC8785**. RFC-8785 (JCS) numbers are stringified per the JSON spec including precision. Any partner implementing RFC-8785 will canonicalize `100.0` differently. |
| "Cryptographically correct using Ed25519" | ✅ Yes, v2 path |
| "Strict replay protection" | ✅ Yes for FEA path (compound index + idempotency) ; ❌ No for demo path (`/api/demo/issue` re-upserts the same proof_id silently) |
| "Persistent immutable key registry" | ⚠️ Persistent yes; "immutable" enforced only by convention — nothing in the schema is append-only |
| "Independently verifiable" | ⚠️ True only via the *artifact* path, and only if the verifier re-implements your canonical JSON rules exactly. |

### 7.3 Cryptographic / implementation risks
1. **Canonical JSON is custom and ad-hoc.** No reference to RFC-8785 (JCS) or RFC-7515 JWS. The float→int rule is the highest-risk divergence — a partner running RFC-8785 in Java will produce a different canonical form and see verifications fail.
2. **Single global signing key, no per-tenant key, no rotation routes.** A pilot bank cannot be cryptographically isolated from another pilot.
3. **`PRIVATE_KEY` on disk** — see §6.3.
4. **No HSM / no envelope key.** The signing key cannot be rotated without restarting the backend and updating .env. A real rotation flow requires the SigningKey loader to refresh.
5. **Verification cache vs DB inconsistency.** The artifact verifier reads `key_registry` straight from the DB on every verify; the FEA verifier reads from the in-memory `_key_cache` populated at boot (`get_key_by_id` only hits DB if not cached). A revocation issued post-boot is honored by the artifact verifier but **not** by the FEA verifier until restart. This is a latent inconsistency.
6. **No proof of issuance time.** The signed payload contains `transaction_summary.timestamp` (the *event* time, asserted by the caller). It does not contain "PFP signed this at T_sign." A neutral observer cannot attribute the proof to a specific moment.
7. **No external time anchor.** PFP says "tamper-resistant evidence" but the only timestamps are self-asserted. No RFC-3161 TSA, no blockchain anchor, no transparency log. For "evidence" use cases (audit, regulatory), this is a real gap.
8. **The legacy v1 signature path is still live** (§6.8).

---

## 8. Documentation Status

The repo ships:
- `/app/docs/DEVELOPER_GUIDE.md` (16 KB) — usable but **out of date** w.r.t. the artifact endpoints and industry fields
- `/app/docs/QUICKSTART.md` (4.6 KB)
- `/app/docs/openapi.yaml` (24 KB) — **stale** (no artifact endpoints, no industry fields)
- `/app/docs/swagger.html` — standalone Swagger UI shell
- `/app/docs/postman_collection.json` — present
- `/app/docs/LOAD_TEST_REPORT.md` — present, useful (≈340 TPS in-pod, recommends `--workers 8`)
- `/app/backend/PROTOCOL_V2.md` (208 lines) — accurate technical spec for the v2 signing model

**Missing:**
- Architecture document (deployment topology, data flow, trust boundaries)
- Integration guide for enterprise customers (the existing developer guide is for individual devs)
- Threat model
- Operational runbook (incident response, key compromise procedure, DR)
- Compliance matrix (which controls map to SOC 2 / ISO 27001 / PCI-DSS / HIPAA touchpoints)

This document set is enough for a hackathon demo. It is not enough for a vendor risk review.

---

## 9. Pilot Readiness Assessment

### Readiness score: **4 / 10**

### What is pilot-ready today
- The cryptographic core (Ed25519 + canonicalize + SHA-256 + domain sep) — solid
- The happy-path FEA generate/verify flow over REST
- A polished demo UI showing the value prop across 9 industries
- A downloadable, file-based, independently re-verifiable artifact (good "leave-behind" for prospects)
- 66 backend tests passing

### What is NOT pilot-ready
- **Customer onboarding**: no real API-key issuance flow
- **Multi-tenancy / isolation**: none
- **Key management**: no rotation/revocation routes, no HSM, no per-tenant key
- **Deployment**: no Helm chart, no Dockerfile, no Terraform, no horizontal-scaling story (in-memory state)
- **Observability**: no `/metrics`, no structured logs, no tracing
- **Security**: §6 lists 4 critical issues
- **SDKs**: zero
- **Webhooks / batch**: zero
- **Independent verification on the customer side**: blocked on custom canonicalization
- **Compliance posture**: no SOC 2 / ISO / pen test

### Critical blockers (must fix before pilot)
1. **Remove or auth-gate `/api/config`** — currently leaks API key (§6.1)
2. **DB-backed API-key store** with per-customer issuance + admin route to create/revoke (§6.2)
3. **Demo endpoints**: either auth-gate them or move to a separate isolated DB / project (§6.4)
4. **Signing-key storage**: ship a KMS-backed key loader (`PRIVATE_KEY_KMS_ARN` style) — even a single-tenant pilot with a bank requires this on day 0 (§6.3)
5. **Admin endpoints for key rotation / retirement / revocation** with audit log (§2.4)

### Medium-priority gaps
- Rate limiting on all write endpoints
- Tenant model (even single-tenant-per-deployment is fine, but the data model needs `tenant_id`)
- Convergence on RFC-8785 or a vendor-published canonicalization library (Python + Java + JS) — without this, "independently verifiable" is marketing only
- Webhook + batch endpoints
- Operational runbook, threat model
- Bring DEVELOPER_GUIDE + openapi.yaml back in sync with the live spec
- Enforce timestamp bounds in `verify_fea` (currently silently passes)

### Low-priority improvements
- Drop the v1 signing path
- Add `iat`, `jti`, `tenant_id`, `algorithm` fields *inside* the signed payload
- External time anchor (RFC-3161 TSA or transparency log)
- PDF export, analytics dashboard, multi-tenant UI

---

## 10. Enterprise Due Diligence Q&A

Imagine the technical review meeting with a bank or telco partner tomorrow.

### Questions you can answer confidently with evidence
- "Show me the signing primitive." → `crypto/signing.py`, PyNaCl, Ed25519 with domain prefix
- "Show me canonicalization." → `crypto/canonicalize.py`
- "Show me your tests." → 66 backend tests, `pytest` clean
- "Show me a real signed artifact." → `/api/fea/generate` works end-to-end, downloadable artifact verifies independently
- "Show me a load test." → `LOAD_TEST_REPORT.md` (≈340 TPS in-pod)
- "Demo it." → The TransactionFlow UI is genuinely good

### Questions you will struggle with
- "Where is the customer's private key kept?" → on the **PFP** server, plaintext base64 in `.env`. There is no customer-held signing.
- "How do you issue and revoke our API keys?" → "We generate one on startup and store it in memory."
- "How is my data isolated from your other pilot customers?" → it isn't
- "Can we rotate our signing key on a 90-day cadence?" → not via API; manual env+restart
- "What happens to in-flight FEAs during a key rotation?" → no documented procedure
- "Show me your SOC 2 / ISO 27001 / pentest report." → none
- "Show me your incident response runbook." → none
- "Show me your data retention and deletion policy." → undocumented; in practice nothing is ever deleted
- "What is your SLA / SLO?" → none published
- "How do we integrate from Java? .NET?" → "Re-implement canonicalize.py yourselves." → 🚫
- "How do we get notified asynchronously when an FEA is generated?" → no webhooks
- "Has this gone through a third-party crypto review?" → no
- "What is your DR plan if MongoDB is corrupted?" → none
- "What is your business continuity plan if the single signing key is compromised?" → undefined

### Evidence missing today
- Threat model document
- Pen-test results
- Crypto audit
- Multi-tenant data model
- KMS integration design doc
- Customer key issuance API
- Webhook spec
- SLA / Status page
- Compliance crosswalk (PCI-DSS, SOC 2, ISO 27001, GDPR, HIPAA where relevant)
- Production deployment manifest (Docker / Helm / Terraform)

---

## 11. Final Verdict

| Class | Verdict |
|---|---|
| A. Concept only | ❌ |
| B. Prototype | ❌ |
| **C. Functional MVP** | ✅ **This is where PFP sits today.** |
| D. Pilot Ready | ❌ Not without the 5 critical blockers in §9 |
| E. Production Ready | ❌ Not even close |

### Justification (evidence-based)

**Why it qualifies as C (Functional MVP):**
- The crypto pipeline (Ed25519 + canonical JSON + SHA-256) is real and works end-to-end (verified live: `fea_id 3691df09-...` was issued and verifies).
- 66 backend tests pass.
- Two distinct proof formats exist (FEA + Artifact) and both verify independently.
- A polished, multi-industry demo UI exists.
- A persistent key registry with `active/retired/revoked` semantics is in place.

**Why it does NOT qualify as D (Pilot Ready):**
- `/api/config` leaks the API key publicly (`curl` confirmed).
- API keys are stored in process memory, not DB — broken under any multi-worker / multi-replica deploy.
- Signing key sits plaintext on disk — no KMS/HSM.
- Demo endpoints are unauthenticated writes against production DB.
- No admin endpoints for key rotation/retirement/revocation despite the code existing for those operations.
- No multi-tenancy. One bug = cross-customer data exposure.
- No SDKs; integrators cannot independently verify without re-implementing custom canonicalization.

**Honest recommendation:**
- **Do not** open external pilots with the current code in production.
- **Do** demo the preview environment for partner conversations — the UX, story, and crypto core are strong enough to win deals.
- **Build** the §9 critical-blocker list as the next 4-week sprint and re-run this assessment. With those done, the classification realistically moves to **D / Pilot Ready** for a single-tenant, supervised pilot.

---

*— End of assessment.*
