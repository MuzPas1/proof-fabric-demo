# PFP — Key Rotation Guide

Regular signing-key rotation (e.g., 90-day cadence) limits blast radius if a key
is ever exposed. PFP's registry keeps retired keys so historical FEAs remain
verifiable forever.

## Key states
| State | New issuance | Verification |
|---|---|---|
| `active` | ✅ signs | ✅ |
| `retired` | ❌ | ✅ (history) |
| `revoked` | ❌ | ❌ (fails immediately) |

## Scheduled rotation (planned)
1. **Trigger rotation** (admin, `keys:manage`):
   ```
   POST /api/admin/keys/rotate   (Authorization: Bearer <admin JWT>)
   ```
   Response includes `new_public_key_id`, `new_public_key_b64`, and
   `new_private_seed_b64` (**shown once**). The previous active key is retired
   and the new public key is registered as active.
2. **Deploy the new private seed** to your KMS/secret store:
   - `local` dev: set `PRIVATE_KEY=<new_private_seed_b64>`.
   - `aws`/`gcp`/`azure`: update the secret referenced by
     `<PROVIDER>_KEY_REF_PRODUCTION` to the new seed.
3. **Restart** the service (rolling) so new issuance uses the new key.
4. **Verify**: generate a test FEA; confirm its `public_key_id` equals
   `new_public_key_id`; verify it with an SDK.
5. **Announce** the new active `kid` to integrators (optional; the public key
   registry is authoritative and queryable at `GET /api/public/keys`).

## Emergency rotation (compromise)
1. **Revoke** the compromised key immediately (verify-time effect, no restart):
   ```
   POST /api/admin/keys/revoke?public_key_id=<kid>
   ```
2. Rotate (steps above) to a fresh key.
3. Identify FEAs signed by the revoked key (`GET /api/fea` per tenant, filter by
   `public_key_id`) and **re-issue** the ones still required.
4. Notify verifiers that the revoked `kid` must be rejected.
5. Record the incident; confirm `GET /api/admin/audit/verify` is intact.

## In-flight FEAs during rotation
- FEAs already signed by the now-retired key continue to verify (the public key
  stays in the registry with `retired` status).
- Only FEAs signed by a **revoked** key fail — that is the intended consequence
  of revocation.

## Audit
Every `keys/create|rotate|retire|revoke` writes a hash-chained audit entry
(`action: key.rotated`, etc.) attributable to the admin actor.
