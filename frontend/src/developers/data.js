// Developer Portal data + canonical resource URLs.
// All backend resources are served under /api on whichever domain is attached.
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const DOCS = `${API}/resources/docs`;
export const SDK = `${API}/resources/sdks`;

// Canonical, human-facing base used inside copy-paste snippets.
export const DEMO_BASE = "https://demo.pfprotocol.com";
export const PRODUCTION_WEBSITE = "https://pfprotocol.com";

export const NAV_SECTIONS = [
  { id: "get-started", label: "Quick Start" },
  { id: "resources", label: "Resources" },
  { id: "sdks", label: "SDKs" },
  { id: "status", label: "Status" },
];

// 5-step "First API Call in 15 Minutes" / Get Started journey.
export const STEPS = [
  {
    key: "credentials",
    title: "Obtain API credentials",
    minutes: "2 min",
    desc: "Pull a sandbox key from the public config endpoint (development only). For production, provision a scoped key from the Admin control plane.",
    lang: "bash",
    code: `# Fetch a sandbox API key (non-production only)
curl ${DEMO_BASE}/api/config

# Copy the returned "test_api_key" value
export PFP_API_KEY="pfp_test_xxxxxxxxxxxxxxxx"`,
  },
  {
    key: "generate",
    title: "Generate your first Proof Artifact",
    minutes: "4 min",
    desc: "Submit a transaction. PFP canonicalizes it, hashes it, and returns an Ed25519-signed Financial Evidence Artifact (FEA).",
    lang: "bash",
    code: `curl -X POST ${DEMO_BASE}/api/fea/generate \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: $PFP_API_KEY" \\
  -d '{
    "idempotency_key": "demo-001",
    "transaction_id": "TXN-1001",
    "timestamp": "2026-06-15T10:00:00Z",
    "amount": 245000,
    "currency": "INR",
    "payer_id": "sha256:7b9c",
    "payee_id": "sha256:a14d"
  }'

# → { "fea_id": "…", "signature": "…", "signature_version": "v2" }`,
  },
  {
    key: "verify",
    title: "Verify a Proof Artifact",
    minutes: "3 min",
    desc: "Anyone can verify a proof with only the public key — no auth, no contacting the issuer. Verification is deterministic and offline-capable.",
    lang: "bash",
    code: `curl ${DEMO_BASE}/api/public/verify/<FEA_ID>

# → { "signature_valid": true, "key_status": "active", ... }`,
  },
  {
    key: "sdk",
    title: "Integrate using an SDK",
    minutes: "4 min",
    desc: "Use a first-party SDK to generate and independently verify proofs in your language of choice. All four SDKs produce byte-identical canonicalization.",
    lang: "javascript",
    code: `// JavaScript (Node 18+)
import { PfpClient, verify } from "@pfp/sdk";

const pfp = new PfpClient({ baseUrl: "${DEMO_BASE}", apiKey: process.env.PFP_API_KEY });
const fea = await pfp.generate({ transactionId: "TXN-1001", amount: 245000, currency: "INR" });

// Independent, offline verification with the public key:
const ok = verify(fea, fea.publicKey);   // → true`,
  },
  {
    key: "review",
    title: "Review verification results",
    minutes: "2 min",
    desc: "Inspect signature validity, key status, canonical payload hash and the full evidence chain in the public verifier UI or via the API response.",
    lang: "bash",
    code: `# Open the branded public verifier
${DEMO_BASE}/verify

# Or read structured results directly from the verify response:
#   signature_valid · key_status · canonical_payload_hash · signed_at`,
  },
];

export const RESOURCES = [
  { id: "swagger", icon: "Code", title: "Swagger UI", desc: "Interactive, try-it-out API explorer for every endpoint.", href: `${API}/docs`, external: true },
  { id: "redoc", icon: "BookOpen", title: "ReDoc", desc: "Clean, three-panel reference rendering of the OpenAPI spec.", href: `${API}/redoc`, external: true },
  { id: "openapi", icon: "FileJson", title: "OpenAPI Specification", desc: "Machine-readable OpenAPI 3.1 JSON for codegen & tooling.", href: `${API}/openapi.json`, external: true },
  { id: "api-reference", icon: "FileText", title: "API Reference", desc: "All routes grouped by category, auth schemes & status codes.", href: `${DOCS}/API_REFERENCE.md`, external: true },
  { id: "auth-guide", icon: "Key", title: "Authentication Guide", desc: "API keys (data plane) vs JWT + RBAC (control plane).", href: `${DOCS}/DEVELOPER_GUIDE.md`, external: true },
  { id: "quickstart", icon: "Rocket", title: "Quick Start", desc: "Integrate end-to-end in under 30 minutes.", href: `${DOCS}/QUICKSTART.md`, external: true },
  { id: "integration-guide", icon: "Plug", title: "Integration Guide", desc: "Idempotency, webhooks, batch issuance & best practices.", href: `${DOCS}/INTEGRATION_GUIDE.md`, external: true },
  { id: "architecture", icon: "Network", title: "Architecture Overview", desc: "System design, trust domains & data model.", href: `${DOCS}/ARCHITECTURE.md`, external: true },
  { id: "developer-index", icon: "Boxes", title: "Developer Resources (JSON)", desc: "Live index of every doc, spec, SDK & collection.", href: `${API}/developer`, external: true },
];

export const SDKS = [
  { id: "python", name: "Python", icon: "Code", install: "pip install pfp-sdk", dep: "PyNaCl", source: `${SDK}/python/pyproject.toml` },
  { id: "javascript", name: "JavaScript", icon: "Code", install: "npm install @pfp/sdk", dep: "Native crypto (no deps)", source: `${SDK}/javascript/index.js` },
  { id: "java", name: "Java", icon: "Coffee", install: "Maven · com.pfprotocol:pfp-sdk:2.0.0", dep: "JDK 17+", source: `${SDK}/java/pom.xml` },
  { id: "dotnet", name: ".NET", icon: "Hash", install: "dotnet add package Pfp.Sdk", dep: ".NET 8 · BouncyCastle", source: `${SDK}/dotnet/PfpVerifier.cs` },
];

export const PLATFORM_STATUS = [
  { id: "live-platform", label: "Live Platform", detail: "demo.pfprotocol.com", live: true },
  { id: "multi-tenant", label: "Multi-Tenant Architecture", detail: "Tenant-isolated", live: true },
  { id: "crypto-engine", label: "Cryptographic Verification Engine", detail: "Ed25519 · deterministic", live: true },
  { id: "production-apis", label: "Production APIs", detail: "Data + control plane", live: true },
  { id: "sdks", label: "SDK Availability", detail: "Python · JS · Java · .NET", live: true },
  { id: "docs", label: "Documentation Status", detail: "Complete & published", live: true },
];
