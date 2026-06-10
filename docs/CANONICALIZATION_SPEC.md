# PFP — Canonicalization Specification (PFP-JCS v1)

This document specifies the **exact** deterministic JSON canonicalization used
by PFP for hashing and signing. Any conforming implementation produces
byte-identical output, enabling independent cross-language verification.

> Reference implementation: `backend/crypto/canonicalize.py`.
> Verified ports: `sdks/python`, `sdks/javascript`, `sdks/java`, `sdks/dotnet`.

## Algorithm

Given a JSON value, produce a UTF-8 byte string as follows.

### 1. Objects
- Remove every member whose value is `null` (recursively, at all depths).
- Sort remaining members by key using **lexicographic (code-point) ordering**.
- Emit `{` `"key":value` pairs joined by `,` `}` with **no whitespace**.

### 2. Arrays
- Drop `null` elements.
- Normalize each remaining element.
- Emit `[` elements joined by `,` `]` with no whitespace.

### 3. Numbers
- A number equal to a whole value collapses to an **integer** representation
  (`100.0` → `100`).
- Non-whole numbers are emitted in their plain decimal form (no exponent).
- Integers are emitted verbatim.

### 4. Strings
- A string matching the regex `^\d{4}-\d{2}-\d{2}T` is treated as a timestamp
  and **normalized** (see §5).
- All other strings are emitted as-is, JSON-escaped per RFC 8259. Non-ASCII
  characters are **not** escaped (`ensure_ascii=false`); only control chars,
  `"`, and `\` are escaped.

### 5. Timestamp normalization
- Parse the ISO-8601 timestamp (assume UTC if no offset present).
- Emit in the form `YYYY-MM-DDTHH:MM:SS.mmmZ` — **millisecond precision, UTC,
  trailing `Z`**.
- Example: `2026-06-10T14:23:00Z` → `2026-06-10T14:23:00.000Z`.

### 6. Booleans / null
- `true` / `false` verbatim. Top-level `null` is `null` (but null members are
  dropped per §1).

## Hashing
`fea_hash` / `proof_id` = `SHA-256( canonical_json )` as a lowercase hex string,
where `canonical_json` is the canonicalization of the payload **excluding** the
`fea_hash` (resp. `proof_id`) and `signature` fields.

## Signing (Ed25519)
The signed message is the canonical JSON of the **full** payload (including
`fea_hash` / `proof_id`) prefixed with a domain separator:

| Format | Domain prefix |
|---|---|
| FEA (v1.0 / v1.1) | `PFP_V2::` |
| Downloadable artifact (v1) | `PFP_ARTIFACT_V1::` |

`signature = base64( Ed25519.sign(domain_prefix + canonical_json) )`.

## Verification
1. Recompute `fea_hash` from canonical(payload − `fea_hash`); constant-time
   compare with the claimed value.
2. Recompute canonical(full payload); prepend the domain prefix.
3. Verify the Ed25519 signature with the issuer public key resolved by
   `public_key_id` from `GET /api/public/keys`.

## Relationship to RFC 8785 (JCS)
PFP-JCS is RFC-8785-*like* but intentionally differs in two places, documented
here for integrators:
- **Whole-number floats collapse to integers** (RFC 8785 preserves the JSON
  number token). PFP payloads use integer minor units for amounts, so this is a
  non-issue in practice, but custom payloads must follow §3.
- **Timestamps are normalized** to millisecond UTC (§5).

A future `fea_version: "2.0"` may adopt strict RFC 8785; the version field in
the signed payload allows verifiers to select the correct ruleset.
