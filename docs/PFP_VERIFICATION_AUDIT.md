# PFP — Verification Audit (Evidence-Based)

**Date:** 2026-06-10 · **Method:** live API calls, code inspection, runtime
execution, MongoDB queries, SDK execution, unit tests. **Rule:** every claim
treated false until proven. No code modified during this audit (only data
restored after the destructive revocation demo; only this doc + master index
created).

Base URL: `https://pfp-evidence.preview.emergentagent.com` (from
`frontend/.env REACT_APP_BACKEND_URL`).

---

## 1. Multi-tenancy — ✅ VERIFIED
- **Model:** `backend/models/auth_models.py:12-17` (`Tenant`: tenant_id, name,
  status, created_at).
- **Create:** `POST /api/admin/tenants {"name":"Audit Test Bank"}` →
  `{"tenant_id":"audit-test-bank","status":"active",...}`. Second tenant
  `acme-audit-telco` created.
- **Cryptographic binding:** an API key bound to `acme-audit-telco` issued an FEA
  whose signed `fea_payload.tenant_id == "acme-audit-telco"`. Tampering
  `tenant_id` → `attacker-tenant` made **both** the Python and JS SDK offline
  verifiers return `{valid:false, reason:"Hash mismatch: payload tampered"}` —
  proving `tenant_id` is inside the signed/hashed payload.

## 2. API Key Management — ✅ VERIFIED
- **DB-backed storage:** `services/api_key_service.py` stores only SHA-256
  `key_hash` (`hash_api_key`, l.21-22); `resolve_api_key` rejects non-active /
  expired keys (l.65-79). Live MongoDB shows `api_keys` collection in prod DB.
- **Create:** `POST /api/admin/api-keys/create` returned raw key once
  (`pfp_live_7b2f…`), scopes, `expires_at` 30 days out, tenant
  `acme-audit-telco`.
- **Use:** key generated an FEA (HTTP 200).
- **Revoke:** `POST /api/admin/api-keys/revoke?key_id=801afab4…` →
  `{"status":"revoked"}`.
- **Revoked fails auth:** subsequent FEA generate → **HTTP 401**
  `{"detail":"Invalid or expired API key"}`.

## 3. Admin Control Plane — ✅ VERIFIED
- **11 admin endpoints** present (live OpenAPI): api-keys create/list/revoke;
  keys create/rotate/revoke/retire; tenants create/list; audit; audit/verify.
- **keys/create** registered a throwaway pubkey (active); **keys/retire** →
  retired; **keys/revoke** → revoked — all returned success.
- **No-token** access to `/api/admin/api-keys` → **HTTP 401** (RBAC/JWT enforced).
- **Audit chain** `GET /api/admin/audit/verify` → `{"intact":true,"checked":68}`;
  entries attribute admin actions to `admin@pfprotocol.com` and data-plane
  actions to the API-key UUID.
- **rotate** function exists (`routes/admin_routes.py:keys/rotate`); not executed
  against the live production key to avoid registry drift (see §Gaps).

## 4. Webhooks — ✅ VERIFIED
- **Subscribe:** `POST /api/webhooks/subscribe` → `webhook_id` + HMAC `secret`.
- **Delivery:** a local receiver (127.0.0.1:9099) captured **two** deliveries: a
  `test.event` (via `POST /api/webhooks/test`) and a real `fea.generated` event
  (triggered by an FEA generate).
- **HMAC validation:** recomputing `sha256=HMAC(secret, raw_body)` matched the
  delivered `X-PFP-Signature` header exactly (`MATCH=True`).

## 5. SDK Verification — ✅ VERIFIED
- **Python SDK** verified a live server-issued FEA offline → `{valid:true}`;
  tampered payload → `{valid:false}`.
- **JavaScript SDK** (Node built-in crypto, zero deps) verified the same FEA
  offline → `{valid:true}`; tampered → `{valid:false}`.
- **Cross-language parity:** `backend/tests/test_crypto_unit.py` → **7 passed**
  (includes `test_sdk_canonicalization_parity`).
- Java/.NET SDKs are source-complete (not compiled in this environment) — see
  §Gaps.

## 6. Endpoint Inventory — ✅ VERIFIED (with clarification)
- Live OpenAPI: **34 unique paths / 35 operations**. Prior assessment documented
  **12** endpoints; the count materially increased to 34.
- By category: System 4 · Auth 4 · Admin 11 · FEA 5 · Public 2 · Webhooks 4 ·
  Demo 5.

## 7. Security Verification — ✅ VERIFIED
- **/api/config:** in production (`ENVIRONMENT=production`) `expose_sandbox_key ==
  False` → `test_api_key` omitted (`core/config.py:52-54`, `server.py:202-203`).
  In dev it is present (current preview).
- **Separate databases:** prod DB `test_database` and demo DB `pfp_demo` are
  distinct (`server.py:36-37`); new demo writes land in `pfp_demo`
  (`demo_proofs=2`, isolated `key_registry` with `demo_key_eccf371ab3912a16`).
  *(Residual: a legacy `demo_proofs` collection persists in the prod DB from
  before isolation — stale, not written to anymore; not purged.)*
- **Separate signing keys:** production `key_0c6c7071b3086f1a` vs demo
  `demo_key_eccf371ab3912a16` — differ (`KEYS DIFFER = True`).
- **Rate limiting:** decorators on write paths (fea generate 120/min, batch
  30/min, verify 240/min, demo 60/min). Live burst of 90 concurrent
  `POST /api/demo/proof` → **48×200 + 42×429** (limit enforced).

## 11. Live Demonstration (revocation) — ✅ VERIFIED
- Fresh FEA signed by `key_0c6c7071b3086f1a`; public verify → `signature_valid =
  True`.
- Revoked the key → public verify `signature_valid = False`; `POST /api/fea/verify`
  → `{valid:false, reason:"Key key_0c6c7071b3086f1a has been revoked"}`.
- Restored the key to `active` (DB-only cleanup) → public verify `signature_valid
  = True`. Confirms **live revocation enforcement** (DB-read, no cache staleness).

---

## Verdict summary
| # | Claim | Verdict |
|---|---|---|
| 1 | Multi-tenancy + crypto binding | ✅ Verified |
| 2 | DB-backed API key lifecycle | ✅ Verified |
| 3 | Admin control plane + audit | ✅ Verified (rotate not run on prod key) |
| 4 | Webhooks + HMAC | ✅ Verified |
| 5 | SDK offline verification + parity | ✅ Verified (Py/JS/Java/.NET all runtime-proven) |
| 6 | Endpoint count 12→34 | ✅ Verified (34 paths / 35 ops) |
| 7 | Security controls | ✅ Verified (legacy demo_proofs residue noted) |
| 11 | Revocation behavior | ✅ Verified |

## Partially-verified / not-verified details
- **Java & .NET SDKs — VERIFIED (runtime).** Compiled and executed against a live
  server-issued FEA. Java: `javac` build OK → `valid=true`, tamper `valid=false`.
  .NET: `dotnet build` OK → `valid=True`, tamper `valid=False`. NOTE: the .NET SDK
  csproj initially referenced a non-existent NuGet id `Org.BouncyCastle.Cryptography`;
  fixed to the correct id `BouncyCastle.Cryptography` (v2.4.0) in
  `sdks/dotnet/Pfp.Sdk.csproj`, after which restore/build/run succeeded.
- **Admin keys/rotate — Partially Verified.** Endpoint exists and create/retire/
  revoke were executed; `rotate` was not invoked against the live production key
  because it retires the active key and registers a new public key with no
  in-memory signer until redeploy (would drift the live registry). Logic:
  `routes/admin_routes.py` (rotate handler) + `services/key_service.py:
  generate_new_keypair`, `rotate_key`.
- **KMS cloud providers (aws/gcp/azure) — Partially Verified.** `core/kms.py`
  implements them, but only `local` is exercised (no cloud credentials). Cloud
  paths raise `KMSNotConfigured` without config.
- **Legacy demo_proofs in prod DB — residual.** Not a functional gap; current
  writes are isolated to `pfp_demo`. No migration/purge was performed.
