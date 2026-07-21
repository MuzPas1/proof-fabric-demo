# PFP — Inbound Event Ingestion Framework

> **Status:** Implemented (backend + Admin Portal + SDK-free HTTP interface).
> **Feature flag:** `ENABLE_EVENT_INGESTION` (default OFF; additive). When OFF,
> the inbound and admin-integration routes return `404` and no existing behaviour
> changes. **Fully backward compatible** — the core proof engine, existing APIs,
> auth, admin features and customer flows are untouched.

The Inbound Event Ingestion Framework lets **any** external application,
platform, enterprise system, or service securely submit verifiable business
events that are transformed into **Proof Artifacts** using the *existing*
generation pipeline. It is application-, department-, industry-, and
sector-agnostic. New integrations require only a lightweight **adapter** (often
just a field mapping) — never a change to the core platform.

---

## 1. Design goals

| Goal | How it is met |
|---|---|
| Agnostic to app/industry/sector | Vendor-neutral `CommonEvent` + configurable `generic` adapter |
| Standardized inbound API | Single endpoint shape `POST /api/ingest/{slug}` |
| Pluggable authentication | `hmac` \| `api_key` \| `bearer` \| `none` providers |
| Payload normalization | Adapters map any JSON → `CommonEvent` |
| Event validation | Model + adapter validation, explicit error codes |
| Audit logging | Every accept/reject recorded; admin actions hash-chained |
| Robust error handling | Structured status codes (401/403/404/422/409) |
| Modular adapter architecture | `core/ingestion/adapters.py` registry + `register_adapter()` |
| No core proof-engine change | Reuses `routes.fea_routes._generate_one` |
| Scalable / reusable | DB-backed config; stateless request path; horizontal-scale safe |
| Lightweight new integrations | Add an adapter (or only a `field_map`) — no platform change |

---

## 2. Component architecture

```
                         External systems (ERP, ITSM, HR, IoT, SaaS, …)
                                          │  HTTPS POST /api/ingest/{slug}
                                          ▼
        ┌───────────────────────────────────────────────────────────────┐
        │  Public Inbound Endpoint (routes/ingestion_routes.py)           │
        │   • NO PFP admin auth  • rate-limited  • feature-gated          │
        └───────────────┬───────────────────────────────────────────────┘
                        │ raw body + headers
                        ▼
        ┌───────────────────────────────────────────────────────────────┐
        │  Ingestion Service (services/ingestion_service.py)              │
        │   1) resolve integration by slug + enabled check                │
        │   2) Auth Provider .verify()  (core/ingestion/auth_providers)   │  ◀── pluggable
        │   3) parse JSON                                                  │
        │   4) Adapter .normalize() → CommonEvent (core/ingestion/adapters)│ ◀── modular
        │   5) map CommonEvent → GenerateFEARequest (tokenize actor/subj.) │
        │   6) audit + monitoring counters                                │
        └───────────────┬───────────────────────────────────────────────┘
                        │ GenerateFEARequest
                        ▼
        ┌───────────────────────────────────────────────────────────────┐
        │  EXISTING Proof Artifact pipeline  (_generate_one → fea_service)│
        │   idempotency · replay protection · canonicalize · sign · store │   (UNCHANGED)
        └───────────────┬───────────────────────────────────────────────┘
                        ▼
                Proof Artifact (fea_id, signature) → verifiable via /api/public/verify/{fea_id}

        ┌───────────────────────────────────────────────────────────────┐
        │  Admin Control Plane (routes/ingestion_admin_routes.py)         │
        │   /api/admin/integrations — JWT + RBAC (integrations:manage/read)│
        │   create · configure · enable/disable · rotate-secret · delete  │
        │   · stats/health · events · test                                │
        └───────────────────────────────────────────────────────────────┘
```

---

## 3. Common Event Model

All adapters normalize inbound payloads into this single shape:

| Field | Type | Notes |
|---|---|---|
| `event_type` | string | e.g. `invoice.created`, `access.granted` |
| `external_id` | string | source system's event/reference id → proof `transaction_id` |
| `occurred_at` | string (ISO-8601) | event time |
| `source` | string | integration slug / originating system |
| `actor` | string (optional) | tokenized (SHA-256) before signing |
| `subject` | string (optional) | tokenized (SHA-256) before signing |
| `amount` | integer (default 0) | smallest unit; `0` for non-financial events |
| `currency` | string(3) (default per integration) | ISO currency code |
| `attributes` | object | any remaining fields → proof metadata (hashed) |
| `idempotency_key` | string (optional) | defaults to `{slug}:{external_id}:{occurred_at}` |

**Privacy:** `actor`/`subject` are hashed and free-form `attributes` are folded
into the proof's `metadata_hash` — no raw business content enters the signed
payload.

---

## 4. Inbound sequence

```
External System        Inbound Endpoint         Ingestion Service        Proof Pipeline
      │  POST /api/ingest/{slug}  │                      │                       │
      │ ─────────────────────────▶│                      │                       │
      │  (body + auth header)     │  process_inbound()   │                       │
      │                           │ ────────────────────▶│                       │
      │                           │      resolve + enabled check                 │
      │                           │      auth_providers.verify() ──┐             │
      │                           │      (401 on failure) ◀────────┘             │
      │                           │      adapter.normalize() → CommonEvent       │
      │                           │      map → GenerateFEARequest                │
      │                           │                      │ _generate_one() ─────▶│
      │                           │                      │   sign + persist      │
      │                           │                      │ ◀──── fea_id ─────────│
      │                           │      audit + counters│                       │
      │ ◀──── 201 {fea_id} ───────│                      │                       │
```

---

## 5. Authentication providers (pluggable)

The framework supports the major enterprise authentication and webhook
verification patterns. New providers are onboarded through **configuration** or
lightweight adapters; custom code is reserved for proprietary schemes.

| Provider | External sends | PFP stores | Verification | Credential source |
|---|---|---|---|---|
| `hmac_sha256` (alias `hmac`) | `X-PFP-Signature: <hex>` / `sha256=<hex>` (or Stripe/Slack scheme) | shared secret | `HMAC-SHA256` over raw body or `{timestamp}.{body}`, constant-time | PFP-minted |
| `hmac_sha1` | `X-…-Signature: <hex>` | shared secret | `HMAC-SHA1`, constant-time | PFP-minted |
| `api_key` | `X-Integration-Key: <token>` | SHA-256 hash | hash compare | PFP-minted |
| `bearer` | `Authorization: Bearer <token>` | SHA-256 hash | hash compare | PFP-minted |
| `basic` | `Authorization: Basic <b64>` | username + password hash | user + password-hash compare | PFP-minted (password) |
| `jwt` | `Authorization: Bearer <jwt>` | (none) / HS secret | PyJWT: HS256 secret, or RS256/ES256 via PEM or cached JWKS; validates `exp`/`iss`/`aud` with leeway; `alg` never trusted | Externally configured |
| `oauth2` | `Authorization: Bearer <token>` | (none) / client secret | JWKS local verify **or** RFC 7662 introspection (cached, timeout, scope/aud checks) | Externally configured |
| `mtls` | ingress-forwarded cert headers | (none) | `X-Client-Verify: SUCCESS` + optional subject/fingerprint allow-list (trust edge-set headers only) | Externally configured |
| `custom` | provider-specific | (none) | a registered callable (`register_custom_provider`) | Externally configured |
| `none` | — | — | open (explicit opt-in; not recommended) | — |

**Provider config** lives in `auth_config` (non-secret; sensitive sub-keys are
redacted in API responses). Externally-provided secrets (JWT HS256 shared
secret, OAuth introspection client secret) are supplied via the `secret` field
and stored redacted. PFP-minted credentials are returned **once** at
create/rotate and never retrievable afterward.

### Cross-cutting controls (apply to every provider)
- **Timestamp validation** — `require_timestamp` + `timestamp_tolerance_seconds`;
  enforced against the timestamp a scheme carries (e.g. Stripe `t=`, Slack
  `X-Slack-Request-Timestamp`, or a configured `timestamp_header`).
- **Replay protection** — `replay_protection`; a per-request key (signature /
  `jti` / body hash) is recorded in `inbound_nonces` with a TTL and a unique
  index, so a replayed request returns `409`.
- **Idempotency** — inherited from the existing proof pipeline via the derived
  `idempotency_key`.

These controls are enforced by the ingestion framework using the provider's
`AuthResult`, so they compose with all providers without core changes.

### Enterprise hardening (defense-in-depth)
- **Tenant binding at ingest.** Every inbound request re-asserts the
  slug → single-active-tenant invariant at request time and refuses an ambiguous
  slug or a request whose owning tenant has been deactivated, so events can never
  cross a tenant boundary.
- **Allow-list responses.** Public/admin responses are built from an explicit
  field allow-list (and `auth_config` from an approved-key allow-list), so no
  secret — present or future — can ever be serialized, even if a new sensitive
  field is later added to the model.
- **OAuth 2.0 introspection resilience.** Introspection calls use a strict
  timeout plus a per-endpoint circuit breaker (fail-fast when the IdP is
  repeatedly unavailable) and a short negative cache for known-bad tokens,
  preventing repeated slow calls while still failing closed on any error.

---

## 5a. Provider presets (configuration-only onboarding)

To simplify onboarding, the Admin Portal offers a **Provider** selector whose
options are vendor-spec-derived, recommended DEFAULT configurations. A preset
**only pre-fills the existing generic fields** (auth provider, signature scheme,
header, encoding, timestamp/replay handling) — it adds **no** code path to the
ingestion framework or the Proof Artifact pipeline, and **every value stays
reviewable and overridable** before saving.

| Preset | Auth provider | Signature scheme | Header | Encoding | Timestamp | Secret source |
|---|---|---|---|---|---|---|
| Generic (PFP-signed) | `hmac_sha256` | plain | `X-PFP-Signature` | hex | — | PFP-minted |
| Cashfree | `hmac_sha256` | cashfree | `x-webhook-signature` | base64 | `x-webhook-timestamp` (ms) | Vendor secret |
| Stripe | `hmac_sha256` | stripe | `Stripe-Signature` (`t`,`v1`) | hex | `t=` in header | Vendor `whsec_…` |
| Razorpay | `hmac_sha256` | plain | `X-Razorpay-Signature` | hex | — | Vendor secret |
| GitHub | `hmac_sha256` | plain (`sha256=` prefix) | `X-Hub-Signature-256` | hex | — | Vendor secret |
| Slack | `hmac_sha256` | slack (`v0=` prefix) | `X-Slack-Signature` | hex | `X-Slack-Request-Timestamp` | Vendor signing secret |
| Shopify | `hmac_sha256` | plain | `X-Shopify-Hmac-Sha256` | base64 | — | Vendor secret |

- **Config-only & secret-free.** Presets contain only non-secret configuration.
  Vendors that sign with their own key are flagged so the operator supplies that
  secret (stored redacted); PFP never embeds secrets in a preset.
- **Extensible.** Add a provider by appending a `ProviderPreset` to
  `core/ingestion/presets.py` — no core change, because a preset is just a bundle
  of the same config keys the framework already understands.
- **API.** `GET /api/admin/integrations/presets` (RBAC `integrations:read`)
  returns the catalog for the Admin Portal.

### Body-derived signed payloads (`{body:...}` placeholders)

Some providers sign a string assembled from fields **inside the JSON body**
rather than from headers. The generic HMAC branch supports this via the
`signed_payload_format` template, which understands three placeholders:

| Placeholder | Resolves to |
|---|---|
| `{body}` | the raw request body, verbatim |
| `{timestamp}` | the value of the configured `timestamp_header` |
| `{body:a.b.c}` | a value read from the JSON body at a dotted path |

`{body:...}` is resolved before the literal `{body}`, so they never collide.
An optional `timestamp_field` (a dotted path into the body) supplies the epoch
used for replay/skew checks when the timestamp lives in the body.

**Tazapay** — signs `HMAC-SHA256(secret, <event_id><rawBody><created_at>)`,
Base64-encoded, in the `webhook-signature` header, where `event_id` is the
top-level `id` and `created_at` is the top-level timestamp (both in the body).
Configure as a generic `hmac_sha256` integration with the vendor's webhook
secret and this `auth_config` (no bespoke scheme, no preset required):

```json
{
  "signature_header": "webhook-signature",
  "signature_encoding": "base64",
  "signed_payload_format": "{body:id}{body}{body:created_at}",
  "timestamp_field": "created_at"
}
```

---

## 6. Extension model — adding a new integration

Most integrations need **no code**: create an integration with the `generic`
adapter and (optionally) a `field_map` that maps canonical fields to the source
system's JSON keys.

When a source needs bespoke logic, add a lightweight adapter:

```python
# core/ingestion/adapters.py
class MySystemAdapter(EventAdapter):
    name = "my-system"
    def normalize(self, payload, integration) -> CommonEvent:
        return CommonEvent(
            event_type=payload["kind"],
            external_id=payload["ref"],
            occurred_at=payload["ts"],
            attributes={"region": payload.get("region")},
        )

register_adapter(MySystemAdapter())
```

No change to routes, services, the proof engine, or the admin portal is
required — the new adapter name becomes selectable on an integration.

---

## 7. Administrative management (Admin Portal)

`PFP Admin → Integrations` (and `/api/admin/integrations`) provides:
create, configure, enable/disable, credential rotation, monitoring counters &
health, recent-event log, audit, and a **test** tool (dry-run normalization or
issue a real test proof). All management requires `integrations:manage`
(read views require `integrations:read`); external inbound endpoints do **not**
use admin auth.

---

## 8. Error handling

| Condition | HTTP | Body |
|---|---|---|
| Feature disabled | 404 | `Event ingestion is not enabled` |
| Unknown slug | 404 | `integration not found` |
| Integration disabled | 403 | `integration is disabled` |
| Auth failure | 401 | `authentication failed: <reason>` |
| Invalid JSON | 400 | `request body must be valid JSON` |
| Normalization/validation failure | 422 | `event validation failed: <reason>` |
| Idempotency/replay conflict | 409 | (from the existing pipeline) |
| Accepted | 201 | `{ "status":"accepted", "integration", "event_id", "fea_id" }` |

---

## 9. Backward compatibility & safety

- Additive module; **default OFF**. No change to existing collections, APIs,
  auth, proof format, admin features, or customer flows.
- Reuses the existing generator, so idempotency, replay protection, signing,
  and verification behave identically.
- New collections: `integrations`, `inbound_events`. New permissions:
  `integrations:manage`, `integrations:read` (granted to super/tenant admins;
  read to auditor/external-reviewer).
- Implementation-safe documentation: no secrets, keys, credentials, or
  production configuration are exposed here.
