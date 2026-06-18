# PFP — Crypto Agility + Federated Key Registry + BYO Signing — Implementation Plan

Status: ✅ IMPLEMENTED & VALIDATED (June 2026). All 6 phases complete; awaiting
deployment approval. Evidence below.

## Implementation status (all phases complete)
- Phase 1 Crypto Agility core — DONE (suites.py; KMS/signing/verify suite-aware; 19 tests)
- Phase 2 Federated Key Registry — DONE (PoP register/confirm, JWK/PEM, validity, tenant; 6 tests)
- Phase 3 BYOS — DONE (signers.py local/remote/cloud-kms, per-tenant config, health; 6 tests)
- Phase 4 SDKs — DONE (Python+JS suite-aware, parity proven; Java/.NET source updated)
- Phase 5 Docs + frontend — DONE (CRYPTO_AGILITY.md, RELEASE_NOTES, /docs portal, Trust section, /api/developer)
- Phase 6 Validation — DONE (146 backend pytest pass + 1 xfail; testing_agent 9/9 e2e + frontend; SDK parity 6/6)

Validation evidence: 146 pytest passed (0 failed); testing_agent iteration_17.json 0 issues;
backward compat confirmed (default Ed25519, demo, artifact, auditor unchanged); no residual
signer/state. Feature flags ENABLE_CRYPTO_SUITES/FEDERATED_KEYS/BYOS enabled in PREVIEW only.

Status: AWAITING APPROVAL (no code written yet). Date: June 2026.

Scope guardrails (HONORED): PFP stays a proof + verification platform. NO identity
orchestration, wallets, consensus, blockchain nodes, MPC, or payment routing.

---

## 0. Codebase Map (current signing/verification dependency graph)

```
routes/fea_routes.py ──> services/fea_service.py ──> crypto/signing.py ──> core/kms.py ──(provider)──> PyNaCl Ed25519
        │                                            │
        │                                            └─> crypto/canonicalize.py + crypto/hashing.py (SHA-256, deterministic)
        ▼
routes/public_routes.py ─> services/verification_service.py ─> crypto/signing.py (verify) + services/key_service.py (registry)
        │                                                                              │
        ▼                                                                              ▼
models/fea.py (FEA payload: fea_version 1.1, algorithm "Ed25519", public_key_id)   models/key_registry.py (PublicKeyInfo)
                                                                                       │
routes/demo_routes.py ─> services/artifact_service.py ─> crypto/signing.py (demo key) + demo_key_registry collection

sdks/{python,javascript,java,dotnet} ── independent verify (Ed25519 hardcoded) over canonical JSON + domain prefix
```

Key facts that make this tractable & backward-compatible:
- `algorithm` is ALREADY a signed field inside the v1.1 payload (`"algorithm":"Ed25519"`).
- ALL signing already routes through `get_kms().sign(logical, msg)` — single choke point.
- Verification resolves the public key from the registry by `public_key_id`, then verifies.
- `cryptography==46.0.5` already installed → supports secp256r1 (ES256) + secp256k1 (ES256K).
  PyNaCl handles Ed25519. **NO new dependencies required.**

Why each change is necessary:
- A suite layer is the minimal seam to add algorithms without touching callers.
- Binding verify-suite to the *registry key's* algorithm is the core anti-confusion control.
- Registry must carry algorithm/format/validity/owner/tenant to federate trust safely.
- Signer abstraction (broadening KMS) is required so private keys can live outside PFP (BYOS)
  while verification stays signer-independent.

---

## A. Crypto Agility — Signature Suite layer

NEW `crypto/suites.py`: a `SignatureSuite` registry.
- `Ed25519` (default, existing) — PyNaCl, 64-byte sig, base64.
- `ES256`  — ECDSA secp256r1 + SHA-256.
- `ES256K` — ECDSA secp256k1 + SHA-256.
- ECDSA signatures encoded as **raw r||s (64 bytes, base64)** (JOSE-style) for trivial
  cross-SDK parity; **low-S canonical form enforced on sign AND verify** (anti-malleability).
- ECDSA is randomized at signing but the proof_id/fea_hash (over the payload) stays
  deterministic; verification is deterministic for all suites.

Signing change: `crypto/signing.py` + `core/kms.py` gain a `suite` parameter resolved from
the signing key's algorithm. `fea_service.build_fea_payload` sets `algorithm` = suite.

Verification change (`verification_service.py`): resolve key → read key.algorithm → select
suite → **require payload.algorithm == key.algorithm == suite** (reject mismatch =
algorithm-confusion defense). Domain prefix `PFP_V2::` retained for all suites.

Feature flag: `ENABLE_CRYPTO_SUITES` (default **off** → only Ed25519 selectable).

## B. Federated Key Registry

Extend `models/key_registry.PublicKeyInfo` (ALL new fields optional, legacy docs default):
- `key_format`: "raw" | "jwk" | "spki-pem" (default "raw")
- `jwk`: optional dict (when format=jwk)
- `tenant_id`: owning tenant (default "default")
- `owner`: "platform" | "customer" | "partner" (default "platform")
- `not_before` / `not_after`: validity window (optional → always valid for legacy)
- `pop_verified`: bool (proof-of-possession evidence)
- status adds "pending" (awaiting PoP) alongside active/retired/revoked.

NEW flow (admin/tenant scoped):
- `POST /api/admin/keys/federated/register` → store key (raw/JWK/PEM) + algorithm +
  validity, status "pending", return a single-use PoP challenge (nonce, TTL).
- `POST /api/admin/keys/federated/confirm` → registrant signs the nonce with their private
  key; server verifies via the suite → status "active" (proves key control; blocks key
  substitution / registering a key you don't control).

Verify-time enforcement: key tenant must match FEA.tenant_id (cross-tenant rejected); key
must be within validity window at FEA.iat; revoked rejected; retired still verifies history.
`GET /api/public/keys` returns the enriched fields (additive). Feature flag:
`ENABLE_FEDERATED_KEYS` (default **off**).

## C. Bring-Your-Own-Signing (BYOS)

NEW `core/signers.py`: `Signer` interface { sign(msg, suite), public_key(), algorithm,
health(), native: bool }.
- `LocalSigner` — wraps existing local KMS (Ed25519 seed; signs locally).
- `CloudKmsSigner` — AWS/GCP/Azure **native** sign (key never leaves KMS); config-gated,
  raises `KMSNotConfigured` when SDK/creds absent (mirrors existing provider pattern).
- `RemoteSigner` — HTTP partner signer: POST canonical message → signature; allow-listed
  URL, auth header, timeout, expected algorithm + registered public key.

Per-tenant/per-key signer resolution via NEW `signers` collection (default tenant →
LocalSigner Ed25519). **Verification never calls a signer** → independent of signer
availability/health (already true structurally). Health: `GET /api/admin/signers/health`
+ `/api/health.signing`; latency/error Prometheus metrics. Feature flag: `ENABLE_BYOS`
(default **off**).

---

## Database changes (all additive / zero-downtime)
1. `key_registry`: new optional fields (no migration; Pydantic defaults for legacy docs);
   new index (tenant_id, status).
2. NEW `signers`: per-tenant signer config; seed default tenant = local Ed25519.
3. NEW `pop_challenges`: single-use PoP nonces, TTL index (auto-expire).
4. `feas`: NO schema change (payload already carries `algorithm`).

## API changes (all additive, contracts preserved)
- `POST /api/fea/generate`: optional `signature_suite` (default Ed25519 / tenant default).
- `GET /api/public/keys`: enriched key objects (additive fields).
- `POST /api/admin/keys/federated/register` + `/confirm`.
- `GET/POST /api/admin/signers`, `GET /api/admin/signers/health`.
- `/api/health.signing` + `/api/developer.signing` extended with suite/federation/BYOS profile.

## Backward-compatibility strategy
- Default suite Ed25519, default FEA v1.1 — unchanged unless a suite/BYOS is explicitly
  selected/configured. Existing proofs, artifacts, keys, APIs, SDKs, auditor flows, proof IDs
  all continue to work. Legacy v1 still gated by `ACCEPT_LEGACY_V1`. All new behaviour behind
  default-off feature flags; phased per-tenant/per-env enablement; no default cutover.

## Threat analysis & mitigations
- Algorithm confusion → bind verify-suite to registry key algorithm + require payload match.
- Downgrade → suites flag-gated + explicit selection; no auto-fallback.
- Key substitution → PoP on federated registration + tenant ownership + tenant binding check.
- Replay → existing dual-layer protection unchanged; PoP nonces single-use + TTL.
- Remote signer abuse → allow-list, auth, timeouts, rate-limit; signer signs server-built
  canonical payload only.
- ECDSA malleability → enforce low-S on sign + verify.
- Cross-tenant isolation → key ownership + FEA.tenant_id == key.tenant_id on verify.

## Test plan
- Unit: suite round-trips (Ed25519/ES256/ES256K), low-S enforcement, confusion/downgrade rejects.
- Test vectors: fixed key+message known-answer per suite (shipped for cross-SDK).
- Cross-SDK parity: Python/JS/Java/.NET verify same artifacts per suite.
- Legacy regression: existing Ed25519 proofs/artifacts/APIs/SDKs unchanged.
- Federated: PoP pass/fail, validity windows, revoke/retire, tenant isolation.
- BYOS: remote signer ok / down (issuance 503, verify still ok), per-tenant resolution, health.
- Security negatives: malformed sig, substitution, downgrade, confusion, cross-tenant.

## Operational readiness
- Signer health monitoring, verification-failure + key-mutation metrics, latency/error metrics,
  alert thresholds, audit evidence, runbooks for degraded signer/KMS.

## Phasing (app stays green after every phase; flags default off)
1. Crypto Agility core (backend) + unit tests + vectors.
2. Federated Key Registry (model/collection/PoP/validity/tenant) + tests.
3. BYOS (signer abstraction, remote/cloud, per-tenant config, health) + tests.
4. SDKs suite-aware verify (4 langs) + parity tests + shipped vectors.
5. Docs (architecture/API/SDK/verification/deploy/security/onboarding + /docs portal +
   dev-portal Trust section) + migration & change-management notes + per-suite examples.
6. Validation & evidence: full regression (testing_agent), backward-compat evidence,
   screenshots, evidence package. NO deploy/commit until evidence complete.

## Explicit list of what will NOT change
- Ed25519 default, FEA v1.1 default, PFP-JCS canonicalization, SHA-256 hashing, domain
  prefixes, proof_id derivation, replay protection, idempotency, contract names
  (`fea_id`, `/api/fea/*`, schema names), demo trust-domain isolation, existing auditor UI.
