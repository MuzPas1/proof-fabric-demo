// Documentation Portal — data layer & canonical resource map.
// Information governance: every item is tagged with an `audience`:
//   'public'     -> served to anyone (product / value / verification / limited examples)
//   'enterprise' -> gated behind Enterprise Evaluation access (server-enforced)
// INTERNAL-only materials (runbooks, DR, key rotation, pilot/readiness) are NOT
// listed here and are not externally serveable.
const BACKEND = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND}/api`;
export const DOCS_RES = `${API}/resources/docs`;
export const SDK_RES = `${API}/resources/sdks`;

export const CANONICAL = {
  website: "https://pfprotocol.com",
  demo: "https://demo.pfprotocol.com",
  admin: "https://demo.pfprotocol.com/admin/login",
  developers: "/developers",
  docs: "/docs",
  evaluation: "/evaluation",
  swagger: `${API}/docs`,        // public Swagger UI (curated public spec)
  redoc: `${API}/redoc`,         // public ReDoc (curated public spec)
  openapiPublic: `${API}/openapi-public.json`,
  openapi: `${API}/openapi.json`, // FULL spec — enterprise-gated
};

// Top-of-portal nav (every major journey is reachable from the docs).
export const TOP_NAV = [
  { label: "Website", href: CANONICAL.website, external: true },
  { label: "Demo", href: CANONICAL.demo, external: true },
  { label: "Developers", href: CANONICAL.developers, external: false },
  { label: "Enterprise Access", href: CANONICAL.evaluation, external: false },
  { label: "API Docs", href: CANONICAL.swagger, external: true },
];

// item.type: 'doc' (Markdown) | 'page' (native React) | 'releases' | 'link'
// item.audience: 'public' | 'enterprise'
export const DOC_TREE = [
  {
    id: "getting-started",
    label: "Getting Started",
    icon: "Rocket",
    blurb: "Understand PFP in 5 minutes.",
    items: [
      { slug: "overview", title: "Overview", file: "README.md", type: "doc", audience: "public" },
      { slug: "quickstart", title: "Quickstart", file: "QUICKSTART.md", type: "doc", audience: "public" },
    ],
  },
  {
    id: "use-cases",
    label: "Product & Use Cases",
    icon: "Boxes",
    blurb: "What PFP does and where it applies.",
    items: [
      { slug: "use-case-change-release", title: "Release Readiness Evaluation", file: "USE_CASE_CHANGE_RELEASE.md", type: "doc", audience: "public" },
    ],
  },
  {
    id: "developer",
    label: "Developer Documentation",
    icon: "Code",
    blurb: "Guides for integrating PFP.",
    items: [
      { slug: "developer-guide", title: "Developer Guide", file: "DEVELOPER_GUIDE.md", type: "doc", audience: "enterprise" },
      { slug: "api-reference", title: "API Reference", file: "API_REFERENCE.md", type: "doc", audience: "enterprise" },
      { slug: "integration-guide", title: "Integration Guide", file: "INTEGRATION_GUIDE.md", type: "doc", audience: "enterprise" },
      { slug: "lnk-developers", title: "Developer Portal", href: CANONICAL.developers, type: "link", internal: true, audience: "public" },
      { slug: "lnk-swagger", title: "Public API (Swagger)", href: CANONICAL.swagger, type: "link", audience: "public" },
      { slug: "lnk-redoc", title: "Public API (ReDoc)", href: CANONICAL.redoc, type: "link", audience: "public" },
    ],
  },
  {
    id: "architecture",
    label: "Architecture",
    icon: "Network",
    blurb: "Platform design for architects & reviewers.",
    items: [
      { slug: "architecture", title: "Architecture Overview", file: "ARCHITECTURE.md", type: "doc", audience: "enterprise" },
      { slug: "cryptographic-architecture", title: "Cryptographic Architecture", file: "CRYPTOGRAPHIC_ARCHITECTURE.md", type: "doc", audience: "enterprise" },
      { slug: "crypto-agility", title: "Crypto Agility, Federated Keys & BYOS", file: "CRYPTO_AGILITY.md", type: "doc", audience: "enterprise" },
      { slug: "canonicalization-spec", title: "Canonicalization Spec", file: "CANONICALIZATION_SPEC.md", type: "doc", audience: "enterprise" },
    ],
  },
  {
    id: "security",
    label: "Security & Trust",
    icon: "ShieldCheck",
    blurb: "Trust model, signing & key management.",
    items: [
      { slug: "trust-overview", title: "Trust Overview", type: "page", audience: "public" },
      { slug: "security-architecture", title: "Security Architecture", file: "SECURITY_ARCHITECTURE.md", type: "doc", audience: "enterprise" },
      { slug: "crypto-agility-sec", title: "Crypto Agility, Federated Keys & BYOS", file: "CRYPTO_AGILITY.md", type: "doc", audience: "enterprise" },
      { slug: "threat-model", title: "Threat Model", file: "THREAT_MODEL.md", type: "doc", audience: "enterprise" },
      { slug: "kms-migration", title: "KMS / HSM Migration Guide", file: "KMS_MIGRATION_GUIDE.md", type: "doc", audience: "enterprise" },
      { slug: "verification-audit", title: "Verification Audit", file: "PFP_VERIFICATION_AUDIT.md", type: "doc", audience: "enterprise" },
    ],
  },
  {
    id: "sdks",
    label: "SDKs & Tools",
    icon: "Boxes",
    blurb: "First-party SDKs & integration tooling.",
    items: [
      { slug: "lnk-sdk-python", title: "Python SDK", href: `${SDK_RES}/python/pyproject.toml`, type: "link", audience: "enterprise" },
      { slug: "lnk-sdk-javascript", title: "JavaScript SDK", href: `${SDK_RES}/javascript/index.js`, type: "link", audience: "enterprise" },
      { slug: "lnk-sdk-java", title: "Java SDK", href: `${SDK_RES}/java/pom.xml`, type: "link", audience: "enterprise" },
      { slug: "lnk-sdk-dotnet", title: ".NET SDK", href: `${SDK_RES}/dotnet/PfpVerifier.cs`, type: "link", audience: "enterprise" },
      { slug: "lnk-postman", title: "Postman Collection", href: `${DOCS_RES}/postman_collection.json`, type: "link", audience: "enterprise" },
    ],
  },
  {
    id: "api-specs",
    label: "API Specifications",
    icon: "FileJson",
    blurb: "Machine-readable specs & explorers.",
    items: [
      { slug: "lnk-swagger-2", title: "Public Swagger UI", href: CANONICAL.swagger, type: "link", audience: "public" },
      { slug: "lnk-redoc-2", title: "Public ReDoc", href: CANONICAL.redoc, type: "link", audience: "public" },
      { slug: "lnk-openapi-public", title: "Public OpenAPI (JSON)", href: CANONICAL.openapiPublic, type: "link", audience: "public" },
      { slug: "lnk-openapi-json", title: "Full OpenAPI (JSON)", href: CANONICAL.openapi, type: "link", audience: "enterprise" },
      { slug: "lnk-openapi-yaml", title: "Full OpenAPI (YAML)", href: `${DOCS_RES}/openapi.yaml`, type: "link", audience: "enterprise" },
    ],
  },
  {
    id: "releases",
    label: "Release Notes",
    icon: "Tag",
    blurb: "What changed, by version.",
    items: [
      { slug: "releases", title: "Release Notes", type: "releases", audience: "public" },
    ],
  },
];

// slug -> item resolver (first match wins; duplicate slugs resolve identically).
export const SLUG_MAP = (() => {
  const m = {};
  for (const cat of DOC_TREE) {
    for (const it of cat.items) {
      if (!m[it.slug]) m[it.slug] = { ...it, categoryId: cat.id, categoryLabel: cat.label };
    }
  }
  return m;
})();

// filename (lowercased) -> slug, for rewriting in-doc Markdown cross-links.
export const FILE_TO_SLUG = (() => {
  const m = {};
  for (const cat of DOC_TREE) {
    for (const it of cat.items) {
      if (it.file && !m[it.file.toLowerCase()]) m[it.file.toLowerCase()] = it.slug;
    }
  }
  m["readme.md"] = "overview";
  m["release_notes.md"] = "releases";
  return m;
})();

// Distinct Markdown docs for the search index (dedup by file).
export const SEARCHABLE_DOCS = (() => {
  const seen = new Set();
  const out = [];
  for (const cat of DOC_TREE) {
    for (const it of cat.items) {
      if (it.type === "doc" && it.file && !seen.has(it.file)) {
        seen.add(it.file);
        out.push({ slug: it.slug, title: it.title, file: it.file, category: cat.label, audience: it.audience });
      }
    }
  }
  return out;
})();

export const CATEGORIES = DOC_TREE.map((c) => c.label);

// Consistent heading slugifier (shared by renderer, TOC and search anchors).
export const slugify = (text) =>
  String(text)
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
