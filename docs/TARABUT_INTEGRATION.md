# Tarabut Gateway (Open Banking) — PFP Provider Integration

Tarabut Gateway is integrated into Proof Fabric Protocol (PFP) as a **first-class,
fully isolated provider**, alongside Jira, DocuSign, Auth0, Razorpay, Cashfree and
Tazapay. It reuses PFP's existing provider abstraction (registry → preset →
adapter → inbound auth verifier) and the **existing proof generation and
verification pipeline**. No existing provider, endpoint, schema, or the core proof
engine was modified. Region: **Bahrain** (`api.sandbox.tarabutgateway.io`).

Every authenticated Tarabut event — inbound payment webhooks and outbound OAuth2
API responses — produces a cryptographically signed PFP Proof Artifact through
the same canonicalization → hashing → Ed25519 signing → registry-verified path
used by all other providers.

---

## 1. Architecture (what was added)

| Layer | File | Purpose |
|---|---|---|
| Provider registry | `backend/core/ingestion/registry.py` | `tarabut` provider (category **Open Banking**, `rsa_sha256` default auth); new `rsa_sha256` auth method + label. |
| Provider preset | `backend/core/ingestion/presets.py` | `tarabut` preset (adapter=`tarabut`, auth=`rsa_sha256`, RS256 headers, region). Appears automatically in the Admin “Add integration” list. |
| Inbound auth verifier | `backend/core/ingestion/auth_providers.py` | `RsaSha256Provider` — RS256 (SHA256withRSA / PKCS#1 v1.5) detached-signature verification over the **raw** body, keyed by `x-signature-keyId`, using operator-supplied PEM / `rsa_public_keys` map / JWKS URL. Fails closed unless `accept_unverified=true`. |
| Event adapter | `backend/core/ingestion/adapters.py` | `TarabutEventAdapter` — normalizes payment webhooks, consent objects, account/transaction/intent resources, and the outbound service envelope into `CommonEvent`. All PII (IBAN, masked PAN, account holder, payer token, customer id, emails, names) is committed **hash-only**. |
| Outbound API client | `backend/core/ingestion/tarabut_client.py` | `TarabutClient` — OAuth2 client-credentials (AIS + Payments), token caching with skew, and typed helpers for every documented product area. |
| Service orchestration | `backend/services/tarabut_service.py` | Turns Tarabut events/API responses into Proof Artifacts via the existing `_generate_one` pipeline; status/catalog; outbound `prove_*` helpers. |
| Admin routes | `backend/routes/tarabut_routes.py` | `/api/admin/tarabut/*` — status, catalog, event→proof, webhook-key config, outbound triggers. |
| Config | `backend/core/config.py`, `backend/.env` | `TARABUT_*` env vars (operator-supplied; empty by default). |
| Admin UI | `frontend/src/admin/pages/Integrations.jsx` | Tarabut appears in the provider list; RS256 auth + JWKS/region connection fields. |

Inbound webhooks use the **existing** public endpoint `POST /api/ingest/{slug}` —
no new public route was introduced.

---

## 2. Configuration

### 2.1 Environment variables (`backend/.env`)

All secrets are operator-supplied and never hardcoded/logged. Base URLs default
to the Bahrain sandbox.

```
TARABUT_REGION="bahrain"
TARABUT_CLIENT_ID=""                 # AIS/Connect OAuth2 client id (Dev Portal → App Settings)
TARABUT_CLIENT_SECRET=""             # AIS/Connect OAuth2 client secret
TARABUT_REDIRECT_URI=""              # one of the redirect URIs registered on the portal
TARABUT_PAYMENT_CLIENT_ID=""         # Payments Merchant/Partner key (Merchant/Partner portal)
TARABUT_PAYMENT_CLIENT_SECRET=""     # Payments Merchant/Partner secret
TARABUT_WEBHOOK_JWKS_URL=""          # optional: Tarabut RS256 public-keys/JWKS endpoint
```

`TARABUT_CLIENT_ID/SECRET` and the payment key/secret are **generated per-account
on the Tarabut portals** and are not part of the public documentation — provide
them to activate live sandbox calls.

### 2.2 Redirect URI

Register your redirect/callback URL(s) (up to 10) on the Tarabut Dev Portal
(App Settings). For Connect, one of the registered URLs must be passed in Create
Intent. Set the same value in `TARABUT_REDIRECT_URI`.

### 2.3 Payment callback / webhook URL

In the Merchant/Partner portal, set the **Payment status change callback URL** to
the PFP inbound endpoint for your Tarabut integration:

```
https://<your-pfp-host>/api/ingest/<your-tarabut-integration-slug>
```

Tarabut signs payment webhooks with RS256 and sends `x-signature` (Base64) +
`x-signature-keyId`.

---

## 3. Authentication flows

### 3.1 Outbound — OAuth2 client credentials
- **Account Information / Connect:** `POST {oauth_base}/token` with JSON
  `{clientId, clientSecret, grantType:"client_credentials", redirect_uri}` →
  `{accessToken, expiresIn (900s), tokenType:"Bearer"}`. Sent as
  `Authorization: Bearer <token>`; `X-TG-CustomerUserId` scopes user data.
- **Payments:** `POST {payments_base}/api/oauth/token` form-urlencoded
  `grant_type/client_id/client_secret` → `{access_token, expires_in (3599s)}`.
- Tokens are cached in-memory with a 30s safety skew and refreshed on expiry.

### 3.2 Inbound — RS256 webhook signature verification
- Algorithm: **SHA256withRSA** (RSA PKCS#1 v1.5 + SHA-256). Never PSS, never a
  caller-controlled algorithm.
- Verified over the **exact raw request bytes** (before JSON parsing).
- Verification material is operator-supplied and configurable without code
  changes: `auth_config.public_key` (single PEM), `auth_config.rsa_public_keys`
  (`{kid: PEM}` map), or `auth_config.jwks_url` (RSA/RS256 only).
- If no key is configured yet, verification **fails closed** unless
  `auth_config.accept_unverified=true` (migration mode: accepted-and-flagged so
  onboarding can proceed; never accepts an *invalid* signature).

---

## 4. Sandbox setup guide

1. Create a Tarabut Dev Portal account → generate sandbox credentials
   (`clientId`/`clientSecret`) and configure Display Name + Redirect URI(s).
2. Put the credentials in `backend/.env` (`TARABUT_CLIENT_ID/SECRET`,
   `TARABUT_REDIRECT_URI`) and restart the backend.
3. For payments, create a Merchant/Partner account, generate the payment
   key/secret, set `TARABUT_PAYMENT_CLIENT_ID/SECRET`, and configure the callback
   URL to the PFP inbound endpoint.
4. In PFP Admin → Integrations → Add → **Tarabut Gateway (Open Banking)**: review
   the preset, add the RS256 public key (PEM/JWKS) if available (else leave the
   key blank and use accept-unverified to onboard), save, and enable.
5. Use the sandbox demo bank `BLUE` (Blue Bank) for Connect/Pay journeys.

---

## 5. End-to-end testing guide

All admin endpoints require a PFP admin JWT and `ENABLE_EVENT_INGESTION=true`.

**A. Validate the event→proof→verification path without live keys**
```
POST /api/admin/tarabut/prove-event
{ "event": { "type":"PAYMENT_STATUS_CHANGE", "paymentId":"demo-1",
             "status":"COMPLETED", "amount":10.95, "currency":"BHD",
             "payerToken":"tok", "destinationAccount":"BHD1" } }
→ { fea_id, event_type:"payment_completed", ... }
```
Then `GET /api/fea/public/{fea_id}` → `valid:true`, `event_descriptor.provider:"Tarabut"`,
`auth_method:"RSA Digital Signature (RS256)"`. Confirm no PII appears in the artifact.

**B. Validate the signed inbound webhook path**
- Create a Tarabut integration, configure a PEM public key via
  `POST /api/admin/tarabut/webhook-key`, enable it, then POST an RS256-signed body
  to `/api/ingest/{slug}` with `x-signature` + `x-signature-keyId`. A tampered
  body must return `401`.

**C. Connection self-test**
- `POST /api/admin/integrations/{id}/simulate` runs a Tarabut sample event through
  auth (skipped for RS256, as the private key is not held server-side) → adapter →
  proof → independent verification.

**D. Live outbound (once credentials configured)**
- `POST /api/admin/tarabut/connect/intent`, `/accounts`, `/consent/revoke`,
  `/payments/status` — each calls Tarabut and mints a Proof Artifact per event.

Automated coverage: `backend/tests/test_tarabut_provider.py`.

---

## 6. Supported Tarabut APIs (outbound client)

Auth: OAuth2 Access Token, Payments OAuth Token.
Connect: Create Intent, Providers.
Consent: Get All Consents, Get Consent Details, Revoke Consent, Create Consent Dashboard.
Account Information: Get Accounts, Get/Refresh Balances, Get Transactions (enriched),
Get Raw Transactions, Refresh Transactions.
Regular Payments: Beneficiaries, Direct Debits, Scheduled Payments, Standing Orders.
Payments: Create Payment (PIR), Get Payment Status, Create/Get Partner Payment.

The live catalog is served at `GET /api/admin/tarabut/catalog`.

## 7. Supported Proof Artifact events

`intent_created`, `connect_journey_started`, `account_linked`, `consent_granted`,
`consent_updated`, `consent_revoked`, `consent_expired`, `consent_retrieved`,
`redirect_completed`, `callback_received`, `account_retrieved`, `account_updated`,
`balance_retrieved`, `balance_refreshed`, `transaction_retrieved`,
`transaction_refreshed`, `enriched_transaction_retrieved`, `beneficiaries_retrieved`,
`direct_debits_retrieved`, `scheduled_payments_retrieved`, `standing_orders_retrieved`,
`payment_created`, `payment_processing`, `payment_completed`, `payment_settled`,
`payment_received`, `payment_failed`, `payment_expired`, `payment_refunded`,
`income_verification_requested/completed`, `salary_verification_requested/completed`,
`categorisation_requested/completed`.

---

## 8. Known sandbox limitations & confirmations needed

- **Credentials** (`clientId`/`clientSecret`, payment key/secret) are portal-generated
  and required for live calls; the provider is fully built and testable with
  Tarabut-shaped payloads without them.
- **Webhook public key / JWKS URL** is not published in the documentation; supply a
  PEM or JWKS URL via `auth_config`/`TARABUT_WEBHOOK_JWKS_URL`. Verification remains
  configurable — no code change needed.
- **Endpoint paths:** Create Intent, Accounts/Balances/Transactions (v2) and Payments
  (v1) paths are confirmed from the Developer Hub. Consent/Regular-Payments paths
  follow the documented resource model under the `accountInformation` base and
  should be confirmed against your account's Postman collection before production.
- Tarabut notes webhook messages can be **duplicated or out-of-order** — PFP's
  replay protection is enabled on the preset (`replay_protection=true`) and proof
  idempotency is enforced by the existing pipeline.

## 9. Future enhancement recommendations (documented, not implemented)

- Persist and expose Tarabut consent/payment state transitions in a dedicated
  read-model for the Release-Readiness Evaluator.
- Add a bespoke Admin “Tarabut” console panel (status card + outbound triggers)
  beyond the generic integration UI.
- Support Saudi region (`api.sau.sandbox.tarabutgateway.io`) via the existing
  `REGIONS` map and a per-integration region selector.
- Auto-fetch and cache the JWKS with rotation once the endpoint is confirmed.
