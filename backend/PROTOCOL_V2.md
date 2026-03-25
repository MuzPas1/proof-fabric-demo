# Proof Fabric Protocol (PFP) - Verification Protocol v2

## Overview

PFP v2 uses proper Ed25519 message signing instead of signing the SHA-256 hash.
This is cryptographically correct as Ed25519 is designed to sign messages directly.

## Signing Model

### v2 (Current - Correct)
```
canonical_json → Ed25519.sign(message)
```
Ed25519 internally uses SHA-512 as part of its signing algorithm.

### v1 (Legacy - Deprecated)
```
canonical_json → SHA-256 → Ed25519.sign(hash)
```
This double-hashing was unnecessary and non-standard.

## FEA Generation Flow (v2)

```
1. Build FEA structure (without fea_hash)
   {
     "fea_version": "1.0",
     "issuer_id": "...",
     "public_key_id": "...",
     "transaction_summary": {...},
     "parties": {...},
     "metadata_hash": "..." (optional)
   }

2. Canonicalize JSON (sort keys, remove nulls)

3. Compute SHA-256 → fea_hash

4. Add fea_hash to structure

5. Canonicalize FULL structure (including fea_hash)

6. Sign the canonical JSON directly: Ed25519.sign(canonical_json)

7. Prefix signature with "v2:" for version detection
```

## Verification Protocol (v2)

### Step 1: Extract fea_payload
Full payload including `fea_hash` field.

### Step 2: Recompute fea_hash (Integrity Check)
```python
payload_without_hash = {k: v for k, v in fea_payload.items() if k != 'fea_hash'}
canonical_json = canonicalize(payload_without_hash)
computed_hash = SHA256(canonical_json)
```

### Step 3: Compare hashes
```python
assert computed_hash == fea_payload['fea_hash']
```
If mismatch: payload has been tampered.

### Step 4: Canonicalize FULL payload
```python
canonical_full = canonicalize(fea_payload)  # Including fea_hash
```

### Step 5: Verify Ed25519 signature
```python
# Detect version
if signature.startswith("v2:"):
    # v2: verify against canonical message
    raw_sig = signature[3:]
    Ed25519.verify(public_key, canonical_full, raw_sig)
else:
    # v1 legacy: verify against fea_hash
    Ed25519.verify(public_key, fea_payload['fea_hash'], signature)
```

## Signature Format

### v2 Signature
```
v2:<base64_signature>
```
Example: `v2:Cx6fcy7yVMWemQH+sVnEp55h88iz84uv99JlP3xC/Ulwoez1PAnhrpUf8dZUHQQ5aa3UHI61KVHFtEGOFzL/Cg==`

### v1 Signature (Legacy)
```
<base64_signature>
```
No prefix. Example: `AFQDTZoM6ke/urpu1zoeRA3VDA2g57zXvXtOLiqRFHYeqGvuYGItDEpZMewONMBwXUjufsrKBUUPzC13xsY2DA==`

## Backward Compatibility

The system automatically detects signature version:
- `v2:` prefix → message-signed (correct)
- No prefix → hash-signed (legacy v1)

Both versions are verified correctly.

## Example FEA (v2)

### Request
```json
{
  "idempotency_key": "v2_test_001",
  "transaction_id": "txn_v2_001",
  "timestamp": "2024-12-01T10:00:00Z",
  "amount": 100000,
  "currency": "USD",
  "payer_id": "payer_v2_test",
  "payee_id": "payee_v2_test"
}
```

### Response
```json
{
  "fea_id": "72a3ec57-9bd6-4370-a56e-d4d18ec2b7e3",
  "fea_hash": "17613ed7a01aa5366e85c820107194f22860fb461bcf824140d555eda44596f7",
  "signature": "v2:Cx6fcy7yVMWemQH+sVnEp55h88iz84uv99JlP3xC/Ulwoez1PAnhrpUf8dZUHQQ5aa3UHI61KVHFtEGOFzL/Cg==",
  "public_key_id": "key_0c6c7071b3086f1a",
  "fea_payload": {
    "fea_version": "1.0",
    "issuer_id": "pfp-issuer-001",
    "public_key_id": "key_0c6c7071b3086f1a",
    "transaction_summary": {
      "transaction_id": "txn_v2_001",
      "timestamp": "2024-12-01T10:00:00.000Z",
      "amount": 100000,
      "currency": "USD"
    },
    "parties": {
      "payer_hash": "payer_v2_test",
      "payee_hash": "payee_v2_test"
    },
    "fea_hash": "17613ed7a01aa5366e85c820107194f22860fb461bcf824140d555eda44596f7"
  }
}
```

## Independent Verification Example (Python)

```python
import json
import hashlib
import base64
from nacl.signing import VerifyKey

def canonicalize(data):
    """Sort keys recursively, remove nulls"""
    if isinstance(data, dict):
        return {k: canonicalize(v) for k, v in sorted(data.items()) if v is not None}
    return data

def verify_fea(fea_payload, signature, public_key_b64):
    # Step 1: Extract claimed hash
    claimed_hash = fea_payload['fea_hash']
    
    # Step 2: Recompute hash (without fea_hash)
    payload_without_hash = {k: v for k, v in fea_payload.items() if k != 'fea_hash'}
    canonical = json.dumps(canonicalize(payload_without_hash), separators=(',', ':'))
    computed_hash = hashlib.sha256(canonical.encode()).hexdigest()
    
    # Step 3: Verify integrity
    if computed_hash != claimed_hash:
        return False, "Hash mismatch"
    
    # Step 4: Canonicalize full payload
    canonical_full = json.dumps(canonicalize(fea_payload), separators=(',', ':'))
    
    # Step 5: Verify signature
    public_key = base64.b64decode(public_key_b64)
    verify_key = VerifyKey(public_key)
    
    if signature.startswith("v2:"):
        raw_sig = base64.b64decode(signature[3:])
        verify_key.verify(canonical_full.encode(), raw_sig)
    else:
        raw_sig = base64.b64decode(signature)
        verify_key.verify(bytes.fromhex(claimed_hash), raw_sig)
    
    return True, "Valid"
```

## Canonicalization Rules

1. Sort all JSON keys lexicographically (recursive)
2. Remove null/undefined fields
3. Normalize timestamps to ISO 8601 UTC (YYYY-MM-DDTHH:MM:SS.sssZ)
4. Amounts as integers (smallest unit)
5. Currency codes uppercase
6. Encode as UTF-8
7. Use minimal JSON (no whitespace): `separators=(',', ':')`

## Security Properties

| Property | Guarantee |
|----------|-----------|
| Determinism | Same input → same hash + signature |
| Integrity | SHA-256 hash detects any modification |
| Authenticity | Ed25519 signature proves origin |
| Non-repudiation | Only private key holder can sign |
| Independent Verification | Only public key + payload needed |
