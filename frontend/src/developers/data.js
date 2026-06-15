// Developer Portal data + canonical resource URLs.
// All backend resources are served under /api on whichever domain is attached.
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const DOCS = `${API}/resources/docs`;
export const SDK = `${API}/resources/sdks`;

// Canonical, human-facing URLs used inside copy-paste snippets and links.
export const DEMO_BASE = "https://demo.pfprotocol.com";
export const PRODUCTION_WEBSITE = "https://pfprotocol.com";
export const ADMIN_PORTAL = "https://demo.pfprotocol.com/admin/login";
export const DEVELOPER_PORTAL = "https://demo.pfprotocol.com/developers";

export const NAV_SECTIONS = [
  { id: "why", label: "Why PFP" },
  { id: "playground", label: "Try It Live" },
  { id: "get-started", label: "Quick Start" },
  { id: "sdks", label: "SDKs" },
  { id: "use-cases", label: "Use Cases" },
  { id: "status", label: "Status" },
];

// 60-second value proposition lifecycle (industry-agnostic).
export const LIFECYCLE = [
  { label: "Event", desc: "Any business or system event" },
  { label: "Proof Generation", desc: "Canonicalize · hash · Ed25519 sign" },
  { label: "Proof Artifact", desc: "Portable, tamper-evident evidence" },
  { label: "Independent Verification", desc: "Verify with only the public key" },
  { label: "Trust", desc: "No need to trust the issuer" },
];

// 5-step onboarding journey (maps to interactive sections).
export const ONBOARDING = [
  { n: 1, title: "Generate Sandbox Key", desc: "One click — a real, scoped sandbox credential.", target: "playground" },
  { n: 2, title: "Generate First Proof", desc: "Sign a live Proof Artifact through the API.", target: "playground" },
  { n: 3, title: "Verify Proof", desc: "Independently verify it with the public key.", target: "playground" },
  { n: 4, title: "Explore SDKs", desc: "Copy a working example in your language.", target: "sdks" },
  { n: 5, title: "Begin Integration", desc: "Wire idempotency, webhooks & batch issuance.", target: "resources" },
];

// Industries — PFP is general-purpose proof infrastructure.
export const INDUSTRIES = [
  { icon: "Landmark", label: "Financial Services", desc: "Transaction & settlement evidence" },
  { icon: "BrainCircuit", label: "AI Governance", desc: "Model decisions & inference provenance" },
  { icon: "GraduationCap", label: "Education", desc: "Credentials, transcripts & attestations" },
  { icon: "Signal", label: "Telecom", desc: "Usage records & consent evidence" },
  { icon: "ScrollText", label: "Compliance", desc: "Audit-ready, tamper-evident records" },
  { icon: "Building2", label: "Government", desc: "Public registries & verifiable filings" },
  { icon: "HeartPulse", label: "Healthcare", desc: "Consent, custody & event integrity" },
  { icon: "Truck", label: "Supply Chain", desc: "Provenance & chain-of-custody proof" },
];

// Core platform capabilities (for technical & non-technical evaluators).
export const CAPABILITIES = [
  { icon: "FileSignature", label: "Proof Generation", desc: "Deterministic canonicalization + Ed25519 signing." },
  { icon: "ShieldCheck", label: "Proof Verification", desc: "Validate hash, timestamp & signature in milliseconds." },
  { icon: "Fingerprint", label: "Tamper-Evident Evidence", desc: "Any change to the data breaks verification." },
  { icon: "Globe", label: "Independent Validation", desc: "Anyone can verify with only the public key." },
  { icon: "Boxes", label: "Multi-Tenant Architecture", desc: "Tenant-isolated keys, data & audit trails." },
  { icon: "Plug", label: "SDK & API Integration", desc: "First-party SDKs for Python, JS, Java & .NET." },
];

// 5-step "First API call" journey — code snippets (key is injected at render).
export const buildSteps = (apiKey) => {
  const key = apiKey || "$PFP_API_KEY";
  return [
    {
      key: "credentials",
      title: "Obtain a sandbox key",
      minutes: "1 min",
      desc: "Click \u201cGenerate Sandbox Key\u201d above, or pull one from the API. The key is a real, scoped, short-lived sandbox credential.",
      lang: "bash",
      code: `# Generate a sandbox key (no auth, rate-limited)
curl -X POST ${DEMO_BASE}/api/demo/sandbox-key

# Export it for the next steps
export PFP_API_KEY="${apiKey || "pfp_sandbox_xxxxxxxxxxxxxxxx"}"`,
    },
    {
      key: "generate",
      title: "Generate your first Proof Artifact",
      minutes: "1 min",
      desc: "Submit any event. PFP canonicalizes it, hashes it, and returns an Ed25519-signed Proof Artifact.",
      lang: "bash",
      code: `curl -X POST ${DEMO_BASE}/api/fea/generate \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${key}" \\
  -d '{
    "idempotency_key": "demo-001",
    "transaction_id": "EVT-1001",
    "timestamp": "2026-06-15T10:00:00Z",
    "amount": 245000,
    "currency": "USD",
    "payer_id": "sha256:7b9c",
    "payee_id": "sha256:a14d"
  }'

# \u2192 { "fea_id": "\u2026", "signature": "\u2026", "signature_version": "v2" }`,
    },
    {
      key: "verify",
      title: "Verify a Proof Artifact",
      minutes: "1 min",
      desc: "Anyone can verify a proof with only the public key \u2014 no auth, no contacting the issuer. Verification is deterministic and offline-capable.",
      lang: "bash",
      code: `curl ${DEMO_BASE}/api/public/verify/<PROOF_ID>

# \u2192 { "signature_valid": true, "signature_version": "v2", ... }`,
    },
    {
      key: "sdk",
      title: "Integrate using an SDK",
      minutes: "1 min",
      desc: "Use a first-party SDK to generate and independently verify proofs in your language. All four SDKs produce byte-identical canonicalization.",
      lang: "javascript",
      code: `// JavaScript (Node 18+)
import { PfpClient, verify } from "@pfp/sdk";

const pfp = new PfpClient({ baseUrl: "${DEMO_BASE}", apiKey: "${key}" });
const proof = await pfp.generate({ transactionId: "EVT-1001", amount: 245000, currency: "USD" });

// Independent, offline verification with the public key:
const ok = verify(proof, proof.publicKey);   // \u2192 true`,
    },
    {
      key: "review",
      title: "Review verification results",
      minutes: "1 min",
      desc: "Inspect signature validity, key status, canonical payload hash and the full evidence chain in the public verifier UI or via the API response.",
      lang: "bash",
      code: `# Open the branded public verifier
${DEMO_BASE}/verify

# Or read structured results directly from the verify response:
#   signature_valid \u00b7 signature_version \u00b7 fea_hash \u00b7 created_at`,
    },
  ];
};

// Per-language quick examples (key injected at render).
export const buildSdkExamples = (apiKey) => {
  const key = apiKey || "YOUR_SANDBOX_KEY";
  return [
    {
      id: "python",
      name: "Python",
      lang: "python",
      code: `import requests

API = "${DEMO_BASE}/api"
KEY = "${key}"

# Generate a Proof Artifact
proof = requests.post(f"{API}/fea/generate",
    headers={"X-API-Key": KEY},
    json={
        "idempotency_key": "py-001",
        "transaction_id": "EVT-1001",
        "timestamp": "2026-06-15T10:00:00Z",
        "amount": 245000, "currency": "USD",
        "payer_id": "sha256:7b9c", "payee_id": "sha256:a14d",
    }).json()

# Independently verify with only the public key
ok = requests.get(f"{API}/public/verify/{proof['fea_id']}").json()
print(ok["signature_valid"])  # True`,
    },
    {
      id: "javascript",
      name: "JavaScript",
      lang: "javascript",
      code: `const API = "${DEMO_BASE}/api";
const KEY = "${key}";

// Generate a Proof Artifact
const proof = await fetch(\`\${API}/fea/generate\`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": KEY },
  body: JSON.stringify({
    idempotency_key: "js-001",
    transaction_id: "EVT-1001",
    timestamp: "2026-06-15T10:00:00Z",
    amount: 245000, currency: "USD",
    payer_id: "sha256:7b9c", payee_id: "sha256:a14d",
  }),
}).then(r => r.json());

// Independently verify with only the public key
const ok = await fetch(\`\${API}/public/verify/\${proof.fea_id}\`).then(r => r.json());
console.log(ok.signature_valid); // true`,
    },
    {
      id: "java",
      name: "Java",
      lang: "java",
      code: `import java.net.http.*;
import java.net.URI;

String API = "${DEMO_BASE}/api";
String KEY = "${key}";
HttpClient http = HttpClient.newHttpClient();

// Generate a Proof Artifact
String body = """
  {"idempotency_key":"jv-001","transaction_id":"EVT-1001",
   "timestamp":"2026-06-15T10:00:00Z","amount":245000,"currency":"USD",
   "payer_id":"sha256:7b9c","payee_id":"sha256:a14d"}""";

HttpResponse<String> res = http.send(HttpRequest.newBuilder()
    .uri(URI.create(API + "/fea/generate"))
    .header("Content-Type", "application/json")
    .header("X-API-Key", KEY)
    .POST(HttpRequest.BodyPublishers.ofString(body)).build(),
    HttpResponse.BodyHandlers.ofString());
System.out.println(res.body());`,
    },
    {
      id: "dotnet",
      name: ".NET",
      lang: "csharp",
      code: `using System.Net.Http;
using System.Text;

var api = "${DEMO_BASE}/api";
var key = "${key}";
using var http = new HttpClient();
http.DefaultRequestHeaders.Add("X-API-Key", key);

// Generate a Proof Artifact
var json = """
  {"idempotency_key":"net-001","transaction_id":"EVT-1001",
   "timestamp":"2026-06-15T10:00:00Z","amount":245000,"currency":"USD",
   "payer_id":"sha256:7b9c","payee_id":"sha256:a14d"}""";

var res = await http.PostAsync($"{api}/fea/generate",
    new StringContent(json, Encoding.UTF8, "application/json"));
Console.WriteLine(await res.Content.ReadAsStringAsync());`,
    },
  ];
};

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
  { id: "java", name: "Java", icon: "Coffee", install: "Maven \u00b7 com.pfprotocol:pfp-sdk:2.0.0", dep: "JDK 17+", source: `${SDK}/java/pom.xml` },
  { id: "dotnet", name: ".NET", icon: "Hash", install: "dotnet add package Pfp.Sdk", dep: ".NET 8 \u00b7 BouncyCastle", source: `${SDK}/dotnet/PfpVerifier.cs` },
];

// Live platform status — 5 evaluator-facing checks.
export const PLATFORM_STATUS = [
  { id: "api", label: "API Status", detail: "Data + control plane", check: "health" },
  { id: "docs", label: "Documentation Status", detail: "Swagger \u00b7 ReDoc \u00b7 OpenAPI", check: "docs" },
  { id: "sdks", label: "SDK Availability", detail: "Python \u00b7 JS \u00b7 Java \u00b7 .NET", check: "static" },
  { id: "verification", label: "Verification Engine", detail: "Ed25519 \u00b7 deterministic", check: "health" },
  { id: "demo", label: "Demo Environment", detail: "demo.pfprotocol.com", check: "health" },
];
