# PFP — KMS / HSM Migration & Time-Anchoring Readiness

This guide documents the **current signing architecture**, the **production
key-management approach**, the **migration path** to cloud KMS / HSM-backed
signing, the **security & cryptographic trust model**, and the **RFC-3161
external time-anchoring readiness** assessment.

> Status legend — **Active**: in use today · **Ready**: implemented, enable by
> configuration · **Planned**: documented, not yet implemented.

---

## 1. Current signing architecture (Active)

- **Algorithm:** Ed25519 (libsodium via PyNaCl), domain-separated with the
  prefix `PFP_V2::` (cross-protocol reuse protection).
- **Single call site:** every signature is produced by
  `crypto.signing.sign_message()`, which delegates to
  `core.kms.get_kms().sign("production", message)`. The demo trust domain uses
  the `"demo"` logical key.
- **Provider:** `KMS_PROVIDER=local` (software) today. The seed is read from the
  `PRIVATE_KEY` (production) / `DEMO_PRIVATE_KEY` (demo) environment variables
  and held only in process memory.
- **Public verification:** unchanged regardless of provider — verifiers only
  ever need the public key from `GET /api/public/keys`.

Because all signing flows through one abstraction, **changing the signing
backend requires no API, payload, or caller changes** — only configuration.

---

## 2. Key-management approach (Active)

| Concern | Approach |
|---|---|
| Key storage | Env-sourced seed today; cloud secret store in cloud modes. No plaintext key on disk in production deployments. |
| Key identity | `public_key_id = "key_" + sha256(pub)[:16]`, embedded in every artifact. |
| Registry | `key_registry` collection — states `active / retired / revoked`. |
| Rotation | `POST /api/admin/keys/rotate` mints a new keypair, marks the old key `retired`; historical proofs still verify by `public_key_id`. See [`KEY_ROTATION_GUIDE.md`](KEY_ROTATION_GUIDE.md). |
| Revocation | `POST /api/admin/keys/revoke` → verification of artifacts under that key fails. |
| Trust-domain isolation | Separate `production` / `demo` keys. |

---

## 3. Migration path → Cloud KMS (Ready, config-only)

The `aws`, `gcp`, and `azure` providers are implemented. They retrieve the
Ed25519 **seed** from a managed secret store at process start and sign locally
with libsodium (the cryptographic primitive stays identical across
environments). Enabling a provider is a configuration change:

### 3.1 AWS Secrets Manager
```bash
KMS_PROVIDER=aws
AWS_KEY_REF_PRODUCTION=pfp/prod/ed25519-seed     # SecretId (b64 seed in SecretString)
AWS_KEY_REF_DEMO=pfp/demo/ed25519-seed
# AWS creds via IAM role / standard boto3 credential chain
```

### 3.2 GCP Secret Manager
```bash
KMS_PROVIDER=gcp
GCP_KEY_REF_PRODUCTION=projects/<p>/secrets/pfp-prod-seed/versions/latest
GCP_KEY_REF_DEMO=projects/<p>/secrets/pfp-demo-seed/versions/latest
# ADC via workload identity / GOOGLE_APPLICATION_CREDENTIALS
```

### 3.3 Azure Key Vault
```bash
KMS_PROVIDER=azure
AZURE_KEY_REF_PRODUCTION=https://<vault>.vault.azure.net#pfp-prod-seed   # vaultUrl#secretName
AZURE_KEY_REF_DEMO=https://<vault>.vault.azure.net#pfp-demo-seed
# Auth via DefaultAzureCredential (managed identity recommended)
```

### 3.4 Rollout & rollback
1. Store the **existing** seed in the chosen secret store (so the
   `public_key_id` is unchanged and all prior proofs keep verifying).
2. Install the provider SDK (`boto3` / `google-cloud-secret-manager` /
   `azure-keyvault-secrets` + `azure-identity`).
3. Set `KMS_PROVIDER` + the `*_KEY_REF_*` vars; redeploy.
4. Verify `GET /api/health` → `signing.provider` matches and
   `signing.ready == true`; smoke-test `POST /api/fea/generate` +
   `GET /api/public/verify/{id}`.
5. **Rollback:** revert `KMS_PROVIDER=local`; the `KMSNotConfigured` error path
   guarantees a misconfigured cloud provider fails fast at boot rather than
   silently falling back.

---

## 4. Migration path → Native HSM signing (Planned)

The strongest model keeps the private key **inside** an HSM/KMS — it never
leaves the secure boundary and signing is performed remotely.

**Required changes (no caller/API impact):**
1. Add a provider class in `core/kms.py` (e.g. `AwsKmsNativeProvider`) with
   `mode = "native"`, `native_sign = True`.
2. Implement `sign(logical_name, message)` to call the remote signing API (e.g.
   AWS KMS `Sign`, GCP KMS `asymmetricSign`, Azure Key Vault sign, or a PKCS#11
   HSM) and return the raw signature bytes. Override `get_signing_key` to raise
   (no exportable seed).
3. Implement `get_public_key_bytes` from the KMS public key.
4. Register the provider in `_PROVIDERS`; set `KMS_PROVIDER` accordingly.

> Note: Ed25519 native signing depends on the KMS/HSM offering an Ed25519 key
> spec. If a deployment standardises on an HSM that only exposes ECDSA P-256,
> introduce it as `fea_version 2.0` with an `algorithm` field already present in
> the signed payload — verifiers branch on `algorithm`. No breaking change to
> existing v1.1 artifacts.

---

## 5. RFC-3161 external time-anchoring readiness (Planned — no code now)

**Current time model.** Each Proof Artifact embeds `iat` (issued-at, UTC) inside
the **signed** payload. This binds the issuer's asserted issuance time to the
signature, but the timestamp's trust derives from the issuer's clock — there is
no independent third-party attestation of *when* the proof existed.

**What RFC-3161 adds.** A trusted Timestamping Authority (TSA) countersigns a
hash of the artifact, producing a TimeStampToken (TST) that independently proves
the artifact existed at/before time *T* — defending against backdating and
strengthening long-term, non-repudiable evidence.

**Integration approach (future).**
1. **Anchor target:** the existing `fea_hash` (SHA-256 of the canonical payload)
   is the natural message-imprint to submit to the TSA — no new hashing needed.
2. **New abstraction:** add a `TimeAnchorProvider` interface (mirroring
   `KMSProvider`) with providers `none` (default, current behaviour), `rfc3161`
   (HTTP TSA via the `MessageImprint`), and optionally `transparency-log`.
3. **Storage:** persist the returned TST **alongside** the artifact as an
   *unsigned, detached* envelope field (e.g. `time_anchor: { type, tsa, token,
   anchored_at }`). It is **not** part of the signed payload, so existing
   signatures and `fea_id` are unchanged → fully backward compatible.
4. **Verification:** extend the verifier to optionally validate the TST against
   the TSA certificate chain and confirm the imprint equals `fea_hash`. Absence
   of a token verifies exactly as today.
5. **API surface:** add an opt-in `anchor: true` flag on
   `POST /api/fea/generate` and surface `time_anchor` in verify responses. No
   change to callers that don't opt in.

**Required changes summary:** new `TimeAnchorProvider` abstraction + config
(`TIME_ANCHOR_PROVIDER`, TSA URL/cert), an additive detached `time_anchor`
envelope field, optional generate/verify flags, and a TSA dependency (e.g.
`rfc3161ng`). **No changes to canonicalization, the signed payload, or existing
proofs.**

**Recommendation:** implement behind the opt-in flag once a TSA vendor is
selected; default off to preserve determinism and zero external dependencies for
the core sign/verify path.

---

## 6. Observability of signing posture

| Surface | Field | Returns |
|---|---|---|
| `GET /api/health` | `signing` | provider, mode, algorithm, `native_sign`, per-logical-key resolution, `ready`, supported providers |
| `GET /api/developer` | `signing` | algorithm, active provider/mode, current capabilities, architecture readiness, planned enhancements |

Neither surface ever returns key material.

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
