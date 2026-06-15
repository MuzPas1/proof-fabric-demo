# Proof Fabric Protocol (PFP) — Official SDKs

Production SDKs for integrating PFP and performing **independent, offline
verification** of Proof Artifacts (signed, content-addressed proofs; stored
under the `fea` / `fea_id` contract names). All four SDKs implement the
**identical** canonicalization
(`PFP-JCS`, see [`docs/CANONICALIZATION_SPEC.md`](../docs/CANONICALIZATION_SPEC.md))
so a proof signed by the server verifies byte-identically in any language.

| Language | Path | Verification dependency | Status |
|---|---|---|---|
| Python | [`python/`](python) | PyNaCl | ✅ Verified against live API |
| JavaScript (Node 18+) | [`javascript/`](javascript) | none (built-in `crypto`) | ✅ Verified against live API |
| Java (JDK 17+) | [`java/`](java) | jackson-databind (native Ed25519) | ✅ Source-complete |
| .NET (8.0) | [`dotnet/`](dotnet) | BouncyCastle | ✅ Source-complete |

## Capabilities

Each SDK provides:
- **Proof generation** (`generate_fea`, `batch_generate`) — authenticated.
- **Verification** — both server-side (`verify_fea`) and **independent local**
  (`verify_local`) using only the issuer's public key.
- **Key retrieval** (`public_keys`).
- **Webhook subscription** (`subscribe_webhook`).
- **Batch** support.

## Quick start (Python)

```python
from pfp_sdk import PFPClient
pfp = PFPClient("https://api.pfprotocol.com", api_key="pfp_live_...")

fea = pfp.generate_fea(
    idempotency_key="idem-001", transaction_id="TXN-001",
    timestamp="2026-06-10T12:00:00Z", amount=250000, currency="INR",
    payer_id="sha256:...", payee_id="sha256:...")

# Independent verification — no trust in the PFP server required:
keys = pfp.public_keys()["keys"]
pub = next(k["public_key"] for k in keys if k["public_key_id"] == fea["public_key_id"])
assert pfp.verify_local(fea["fea_payload"], fea["signature"], pub)["valid"]
```

## Quick start (JavaScript)

```js
const { PFPClient } = require("@pfp/sdk");
const pfp = new PFPClient("https://api.pfprotocol.com", "pfp_live_...");
const fea = await pfp.generateFea({ idempotency_key, transaction_id, timestamp, amount, currency, payer_id, payee_id });
const { keys } = await pfp.publicKeys();
const pub = keys.find(k => k.public_key_id === fea.public_key_id).public_key;
console.log(PFPClient.verifyLocal(fea.fea_payload, fea.signature, pub)); // { valid: true }
```

## Quick start (Java)

```java
var result = PfpVerifier.verifyFea(feaPayloadJson, signatureB64, publicKeyB64);
System.out.println(result.valid());
```

## Quick start (.NET)

```csharp
var result = PfpVerifier.VerifyFea(feaPayloadJson, signatureB64, publicKeyB64);
Console.WriteLine(result.Valid);
```
