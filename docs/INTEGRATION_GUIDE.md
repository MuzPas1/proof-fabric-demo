# PFP — Enterprise Integration Guide

Audience: partner engineering teams (banks, telcos, government, healthcare)
integrating PFP for cryptographic evidence.

## 1. Get credentials
Your PFP operator provisions a **tenant** and an **API key** for you via the
admin control plane. You receive:
- Base URL (e.g., `https://api.pfprotocol.com`)
- API key `pfp_live_…` (shown once — store in your secret manager)
- Your `tenant_id`

In sandbox, fetch a test key from `GET /api/config` (development only).

## 2. Issue an FEA
```
POST /api/fea/generate
X-API-Key: pfp_live_...
Content-Type: application/json

{
  "idempotency_key": "idem-2026-06-10-0001",
  "transaction_id": "TXN-8F2C-00418",
  "timestamp": "2026-06-10T14:23:00Z",
  "amount": 245000,            // integer, smallest unit (paise/cents)
  "currency": "INR",
  "payer_id": "sha256:7b9c...",  // hashed/tokenized — NEVER raw PII
  "payee_id": "sha256:a14d...",
  "metadata": { "channel": "upi" }   // optional; only its hash is committed
}
```
Response: `fea_id`, signed `fea_payload` (v1.1), `signature`, `public_key_id`.

**Idempotency**: retrying with the same `idempotency_key` + identical payload
returns the same FEA; a different payload returns `409`.
**Replay protection**: `(tenant_id, transaction_id, timestamp)` is globally
unique per tenant.

## 3. Batch issuance
```
POST /api/fea/batch  { "items": [ {…}, {…} ] }   // up to 500
```
Returns per-item success/failure — partial failures don't abort the batch.

## 4. Verify
- **Server-side**: `POST /api/fea/verify` (scope `fea:verify`).
- **Public attestation**: `GET /api/public/verify/{fea_id}` (no auth).
- **Independent / offline** (recommended for auditors): use an SDK
  (`sdks/`), fetch the public key from `GET /api/public/keys`, and verify
  locally. This requires **no trust** in the PFP server. See
  `CANONICALIZATION_SPEC.md`.

```python
from pfp_sdk import PFPClient
pfp = PFPClient(BASE, api_key=KEY)
keys = pfp.public_keys()["keys"]
pub = next(k["public_key"] for k in keys if k["public_key_id"] == fea["public_key_id"])
assert pfp.verify_local(fea["fea_payload"], fea["signature"], pub)["valid"]
```

## 5. Webhooks
```
POST /api/webhooks/subscribe  { "url": "https://you/hook", "events": ["fea.generated"] }
```
Returns a `secret`. Each delivery includes `X-PFP-Signature: sha256=<hmac>` over
the raw body — verify it with the secret. Test with `POST /api/webhooks/test?webhook_id=…`.

## 6. List & fetch
- `GET /api/fea?limit=50&skip=0` — paginated list of your tenant's FEAs.
- `GET /api/fea/{fea_id}` — authenticated single fetch (tenant-scoped).

## 7. Data handling contract
- Send only **hashed/tokenized** identifiers for parties. PFP stores
  `metadata_hash`, not raw metadata.
- Amounts are integers in minor units.

## 8. Error handling
| Code | Meaning |
|---|---|
| 400 | Invalid input / business rule |
| 401 | Missing/invalid/expired API key |
| 403 | Missing scope / cross-tenant |
| 409 | Idempotency or replay conflict |
| 413 | Body too large |
| 422 | Schema validation |
| 429 | Rate limited (honor `Retry-After`) |

## 9. Integration effort
- First signed FEA over REST: ~0.5 day.
- Independent verification: **drop in an SDK** (Python/JS/Java/.NET) — no need to
  re-implement canonicalization. Hours, not weeks.

## 10. Inbound event ingestion (push events, no SDK required)
For source systems that should *push* business events instead of calling
`/api/fea/generate` directly, a PFP administrator configures an **inbound
integration**. Your system then posts events to a standardized endpoint and PFP
transforms each into a Proof Artifact automatically.

```
POST /api/ingest/{slug}
X-PFP-Signature: <hmac-sha256(secret, raw_body) hex>   # for the hmac provider
Content-Type: application/json

{ "type": "invoice.created", "id": "INV-1001",
  "timestamp": "2026-06-10T12:00:00Z",
  "actor": "system-a", "subject": "account-42",
  "amount": 25000, "currency": "USD" }
```
Response `201`: `{ "status":"accepted", "integration":"{slug}", "event_id":"INV-1001", "fea_id":"…" }`.

- **Auth is per-integration** (HMAC / API key / bearer) — not PFP admin auth.
- **Agnostic:** any JSON shape works; unmapped systems use a `field_map`, custom
  ones use a lightweight adapter (no core change).
- **Privacy:** `actor`/`subject` are tokenized (hashed) and extra fields are
  committed only as a metadata hash — no raw content is signed.
- Verify results exactly like any other proof via `GET /api/public/verify/{fea_id}`.
- Full details: [`INBOUND_EVENT_INGESTION.md`](INBOUND_EVENT_INGESTION.md).
