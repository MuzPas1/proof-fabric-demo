import React from "react";
import { CodeBlock } from "./CodeBlock";
import { SectionHeader } from "./GetStarted";
import { DEMO_BASE } from "./data";

const CURL_VERIFY = `# Verify any FEA by id — public, no auth required
curl ${DEMO_BASE}/api/public/verify/<FEA_ID>

# Response
# {
#   "signature_valid": true,
#   "key_status": "active",
#   "canonical_payload_hash": "sha256:…",
#   "signature_version": "v2"
# }`;

const SDK_VERIFY = `// Independent, offline verification (JavaScript SDK)
import { verify } from "@pfp/sdk";

// 'fea' is the artifact you received; verify with only its public key.
const result = verify(fea, fea.publicKey);

console.log(result.signatureValid);  // true  → proof is authentic & untampered
console.log(result.keyStatus);       // "active"`;

export const VerificationExamples = () => (
  <section id="verification" className="scroll-mt-20 bg-white" data-testid="dev-verification-examples">
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
      <SectionHeader
        eyebrow="Verification"
        title="Verification examples"
        subtitle="Proofs are verifiable by anyone with the public key — over the API or fully offline with an SDK."
      />
      <div className="mt-10 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 font-['Space_Grotesk']">Verify via API</h3>
          <CodeBlock code={CURL_VERIFY} lang="bash" testid="verify-api" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-900 font-['Space_Grotesk']">Verify offline with an SDK</h3>
          <CodeBlock code={SDK_VERIFY} lang="javascript" testid="verify-sdk" />
        </div>
      </div>
    </div>
  </section>
);
