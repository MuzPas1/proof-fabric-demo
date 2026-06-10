# PFP — Cryptographic Architecture

## 1. Primitives
| Purpose | Primitive | Library |
|---|---|---|
| Signature | Ed25519 | PyNaCl (libsodium) |
| Hash / content addressing | SHA-256 | hashlib |
| Canonical form | PFP-JCS v1 | `crypto/canonicalize.py` |
| Constant-time compare | `hmac.compare_digest` | stdlib |

## 2. Signed FEA payload (v1.1)
```jsonc
{
  "fea_version": "1.1",
  "algorithm": "Ed25519",        // explicit — algorithm-confusion defense
  "issuer_id": "pfp-issuer-001",
  "tenant_id": "default",        // cryptographically bound owner
  "public_key_id": "key_…",
  "iat": "2026-06-10T16:00:07.094Z",   // issuance time (PFP signed at)
  "jti": "…uuid…",                      // unique proof nonce
  "transaction_summary": { "transaction_id", "timestamp", "amount", "currency" },
  "parties": { "payer_hash", "payee_hash" },
  "metadata_hash": "…",          // optional; raw metadata never stored
  "fea_hash": "…"                // SHA-256 of canonical(payload − fea_hash)
}
```
`iat`, `jti`, `tenant_id`, and `algorithm` are **inside the signature**, closing
the gaps identified in the prior assessment (§5.4): issuance-time proof, unique
nonce, tenant attribution, explicit algorithm binding.

## 3. Signing
```
canonical = PFP-JCS(payload_including_fea_hash)
signature = base64( Ed25519.sign("PFP_V2::" + canonical) )
```
Signing key material is resolved via the KMS abstraction (`production` logical
key). Domain separation prevents cross-protocol signature reuse.

## 4. Verification (independent)
1. `recompute = SHA-256(PFP-JCS(payload − fea_hash))`; constant-time compare to
   `fea_hash`.
2. Resolve public key by `public_key_id`; reject if `revoked`.
3. `Ed25519.verify("PFP_V2::" + PFP-JCS(payload), signature, pubkey)`.

The four SDKs implement steps 1–3 with no server dependency.

## 5. Versioning policy
- Supported `fea_version`: `1.0`, `1.1`. The version selects the verification
  ruleset. New fields are additive within a major version.
- Legacy v1 (hash-signed, no domain prefix) is **rejected by default**
  (`ACCEPT_LEGACY_V1=false`).

## 6. Key lifecycle & rotation
- States: `active`, `retired`, `revoked`.
- `active` → signs new FEAs; `retired` → still verifies; `revoked` → fails.
- Rotation (`POST /api/admin/keys/rotate`): generate keypair → register public
  key (active) → retire previous active → return new seed once for KMS upload →
  redeploy/restart so issuance uses the new key. In-flight historical FEAs keep
  verifying against the retired key.
- Demo trust domain uses a **separate** key in an isolated registry.

## 7. Time anchoring (abstraction)
The signed `iat` provides issuer-asserted issuance time. For neutral,
third-party time attestation the platform defines an anchoring abstraction
(future work, interface documented here):
- **RFC-3161 TSA**: submit `SHA-256(canonical)` to a Time-Stamping Authority,
  store the returned token alongside the FEA.
- **Blockchain / transparency log**: periodically publish a Merkle root of newly
  issued `fea_hash` values to an append-only public log; store the inclusion
  proof. Both are pluggable behind a single `AnchorProvider` interface.

## 8. Known cryptographic considerations
- PFP-JCS diverges from RFC 8785 on whole-number floats and timestamp
  normalization (documented in `CANONICALIZATION_SPEC.md`). A future
  `fea_version: "2.0"` may adopt strict RFC 8785.
- Signing currently uses software Ed25519 via the KMS abstraction; an HSM-backed
  provider can be added behind the same interface without changing the protocol.
