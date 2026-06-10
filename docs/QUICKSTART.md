# Integrate PFP in 30 minutes

A senior engineer can move from zero to a verified FEA in **30 minutes**.
Here's the plan, with the clock running.

| Time | Step |
|---|---|
| 0–5 min | Get a sandbox key |
| 5–15 min | Issue your first FEA |
| 15–25 min | Verify it (both server-side and as an "auditor") |
| 25–30 min | Wire up production checklist |

---

## 0–5 min · Get a sandbox key

```bash
curl https://pfp-evidence.preview.emergentagent.com/api/config
```

Copy the `test_api_key` field.

```bash
export PFP_BASE="https://pfp-evidence.preview.emergentagent.com"
export PFP_API_KEY="pfp_test_………"   # paste it here
```

> **Production?** Email **support@pfprotocol.com** for a live key. Then
> switch `PFP_BASE` to `https://demo.pfprotocol.com`. Everything else
> stays the same.

---

## 5–15 min · Issue your first FEA

```bash
curl -sS -X POST "$PFP_BASE/api/fea/generate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PFP_API_KEY" \
  -d '{
    "idempotency_key": "idem-quickstart-001",
    "transaction_id": "TXN-QUICKSTART-001",
    "timestamp": "2026-02-10T14:23:00Z",
    "amount": 245000,
    "currency": "INR",
    "payer_id": "sha256:7b9cabd2b7a1e9c1",
    "payee_id": "sha256:a14d8c2f9b4e5d6a",
    "metadata": { "channel": "upi" }
  }'
```

You'll get back a `FEAResponse`. **Save the entire JSON body** — that's
your evidence.

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

- [ ] Switched `PFP_BASE` to `https://demo.pfprotocol.com`
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
| `401 Invalid API key` | Forgot `X-API-Key` or copied the key wrong. | Re-fetch from `/api/config` (sandbox) or your secret manager. |
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
