# Integrate PFP in 30 minutes

A senior engineer can move from zero to a verified **Proof Artifact** in
**30 minutes** — or try the whole lifecycle in your browser in **5 minutes** at
the **Developer Portal**: **https://demo.pfprotocol.com/developers**.

PFP is general-purpose proof infrastructure: the same flow applies to a
payment, an AI decision, a credential, a shipment or any compliance event.
Here's the plan, with the clock running.

| Time | Step |
|---|---|
| 0–5 min | Get a sandbox key |
| 5–15 min | Issue your first Proof Artifact |
| 15–25 min | Verify it (both server-side and as an independent "auditor") |
| 25–30 min | Wire up production checklist |

### Key portals
| Portal | URL |
|---|---|
| Website | **https://pfprotocol.com** |
| Demo platform | **https://demo.pfprotocol.com** |
| Admin portal | **https://demo.pfprotocol.com/admin/login** |
| Developer Portal | **https://demo.pfprotocol.com/developers** |

---

## 0–5 min · Get a sandbox key

Generate a real, scoped, short-lived sandbox key (no auth, rate-limited):

```bash
curl -X POST https://demo.pfprotocol.com/api/demo/sandbox-key
```

Copy the `api_key` field (or click **Generate Sandbox Key** on the
[Developer Portal](https://demo.pfprotocol.com/developers)). A non-production
sandbox key is also exposed via `GET https://demo.pfprotocol.com/api/config`
(`test_api_key`).

```bash
export PFP_BASE="https://demo.pfprotocol.com"
export PFP_API_KEY="pfp_sandbox_………"   # paste it here
```

> **Production?** Email **support@pfprotocol.com** for a live key. Then
> switch `PFP_BASE` to `https://api.pfprotocol.com`. Everything else
> stays the same. (See [`CANONICAL_ENDPOINTS.md`](./CANONICAL_ENDPOINTS.md).)

---

## 5–15 min · Issue your first Proof Artifact

```bash
curl -sS -X POST "$PFP_BASE/api/fea/generate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PFP_API_KEY" \
  -d '{
    "idempotency_key": "idem-quickstart-001",
    "transaction_id": "EVT-QUICKSTART-001",
    "timestamp": "2026-02-10T14:23:00Z",
    "amount": 245000,
    "currency": "USD",
    "payer_id": "sha256:7b9cabd2b7a1e9c1",
    "payee_id": "sha256:a14d8c2f9b4e5d6a",
    "metadata": { "channel": "api" }
  }'
```

You'll get back a Proof Artifact response. **Save the entire JSON body** —
that's your evidence.

```json
{
  "fea_id": "f1c2c45e-…",
  "fea_payload": { "...": "..." },
  "signature": "MEUCIQDp…",
  "signature_version": "v2",
  "public_key_id": "key_…",
  "created_at": "2026-…"
}
```

Three things to internalise:

1. **`idempotency_key`** — your replay-safety lever. Reusing the same key
   with the same body returns the same FEA (idempotent retries are free).
2. **`amount`** is **always in the smallest currency unit** (paise, cents).
3. **`payer_id` / `payee_id`** must already be hashed/tokenized. Never raw
   PII.

---

## 15–25 min · Verify it (two ways)

### Server-side verify (authenticated)

```bash
curl -sS -X POST "$PFP_BASE/api/fea/verify" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PFP_API_KEY" \
  -d @- <<'JSON'
{
  "fea_payload": <PASTE fea_payload FROM ABOVE>,
  "signature":   "<PASTE signature FROM ABOVE>",
  "signature_version": "v2"
}
JSON
```

Expected: `{ "valid": true, … }`

### Public / auditor verify (no auth)

```bash
curl -sS "$PFP_BASE/api/public/verify/<fea_id>"
```

Expected: `"signature_valid": true`.

> Auditors can do this **without any credentials** — that's the entire
> point of PFP. The public key registry is at
> `GET /api/public/keys` if they want to verify with their own crypto
> library.

---

## 25–30 min · Production checklist

Before you flip your code from sandbox to live:

- [ ] Switched `PFP_BASE` to `https://api.pfprotocol.com`
- [ ] Production `PFP_API_KEY` stored in your secret manager
      (Vault / AWS Secrets Manager / GCP SM). **Never** in source.
- [ ] `idempotency_key` is **persisted before** the API call so a crash
      mid-request retries cleanly.
- [ ] You store the **entire `FEAResponse`** (payload + signature + kid).
- [ ] You verify on receipt in your own code path. Belt and braces.
- [ ] You handle `409 Conflict` as a **business-logic alert**, not a
      transport retry.
- [ ] You back-off on `429` honoring `Retry-After`.
- [ ] Time on your servers is synced (NTP / cloud time service).

---

## Common gotchas

| You see | Why | Fix |
|---|---|---|
| `401 Invalid API key` | Forgot `X-API-Key` or copied the key wrong. | Generate a fresh key from `POST /api/demo/sandbox-key` (sandbox) or your secret manager. |
| `409 Idempotency key already used with different payload` | Same `idempotency_key`, different body. | Use a **fresh** key, or send the exact same body. |
| `409 Transaction replay detected` | Same `(transaction_id, timestamp)`, different amount/parties. | Find the original FEA — almost always a business-logic dup. |
| `422 unprocessable entity` | Bad schema (e.g. `amount` as float). | `amount` must be **integer** in smallest unit. |
| Public verify returns `signature_valid: false` | Tampered FEA, or the key was `revoked`. | Check `GET /api/public/keys` for the `kid` status. |

---

## Where next

- 🔌 **Full integration story:** [`DEVELOPER_GUIDE.md`](./DEVELOPER_GUIDE.md)
- 📚 **Interactive API reference:** open
  [`swagger.html`](./swagger.html) — loads the OpenAPI spec.
- 📬 **Postman collection:** [`postman_collection.json`](./postman_collection.json)
  — imports with pre-wired sandbox bootstrap, idempotent test, replay-attack
  test, and public-verify call.
- ✉️ **Stuck?** support@pfprotocol.com

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
