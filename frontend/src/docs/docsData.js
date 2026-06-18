// Documentation Portal — data layer & canonical resource map.
// The Documentation Portal (/docs) is the structured knowledge base. It does NOT
// duplicate the interactive Developer Portal (/developers) or the API reference
// (/api/docs) — it links to them and renders the long-form Markdown docs.
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
  swagger: `${API}/docs`,
  redoc: `${API}/redoc`,
  openapi: `${API}/openapi.json`,
};

// Top-of-portal nav (every major journey is reachable from the docs).
export const TOP_NAV = [
  { label: "Website", href: CANONICAL.website, external: true },
  { label: "Demo", href: CANONICAL.demo, external: true },
  { label: "Developers", href: CANONICAL.developers, external: false },
  { label: "Admin", href: CANONICAL.admin, external: true },
  { label: "API Docs", href: CANONICAL.swagger, external: true },
];

// Information architecture. Adding a future category = appending an object here;
// no structural changes required (version-ready, extensible).
// item.type: 'doc' (Markdown file) | 'page' (native React) | 'releases' | 'link'
export const DOC_TREE = [
  {
    id: "getting-started",
    label: "Getting Started",
    icon: "Rocket",
    blurb: "Understand PFP in 5 minutes.",
    items: [
      { slug: "overview", title: "Overview", file: "README.md", type: "doc" },
      { slug: "quickstart", title: "Quickstart", file: "QUICKSTART.md", type: "doc" },
      { slug: "master-index", title: "Master Index", file: "PFP_MASTER_INDEX.md", type: "doc" },
    ],
  },
  {
    id: "developer",
    label: "Developer Documentation",
    icon: "Code",
    blurb: "Guides for integrating PFP.",
    items: [
      { slug: "developer-guide", title: "Developer Guide", file: "DEVELOPER_GUIDE.md", type: "doc" },
      { slug: "api-reference", title: "API Reference", file: "API_REFERENCE.md", type: "doc" },
      { slug: "integration-guide", title: "Integration Guide", file: "INTEGRATION_GUIDE.md", type: "doc" },
      { slug: "lnk-developers", title: "Developer Portal", href: CANONICAL.developers, type: "link", internal: true },
      { slug: "lnk-swagger", title: "Swagger UI", href: CANONICAL.swagger, type: "link" },
      { slug: "lnk-redoc", title: "ReDoc", href: CANONICAL.redoc, type: "link" },
      { slug: "lnk-openapi", title: "OpenAPI JSON", href: CANONICAL.openapi, type: "link" },
    ],
  },
  {
    id: "architecture",
    label: "Architecture",
    icon: "Network",
    blurb: "Platform design for architects & reviewers.",
    items: [
      { slug: "architecture", title: "Architecture Overview", file: "ARCHITECTURE.md", type: "doc" },
      { slug: "cryptographic-architecture", title: "Cryptographic Architecture", file: "CRYPTOGRAPHIC_ARCHITECTURE.md", type: "doc" },
      { slug: "crypto-agility", title: "Crypto Agility, Federated Keys & BYOS", file: "CRYPTO_AGILITY.md", type: "doc" },
      { slug: "canonicalization-spec", title: "Canonicalization Spec", file: "CANONICALIZATION_SPEC.md", type: "doc" },
    ],
  },
  {
    id: "security",
    label: "Security & Trust",
    icon: "ShieldCheck",
    blurb: "Trust model, signing & key management.",
    items: [
      { slug: "trust-overview", title: "Trust Overview", type: "page" },
      { slug: "security-architecture", title: "Security Architecture", file: "SECURITY_ARCHITECTURE.md", type: "doc" },
      { slug: "crypto-agility-sec", title: "Crypto Agility, Federated Keys & BYOS", file: "CRYPTO_AGILITY.md", type: "doc" },
      { slug: "verification-audit", title: "Verification Audit", file: "PFP_VERIFICATION_AUDIT.md", type: "doc" },
      { slug: "kms-migration", title: "KMS / HSM Migration Guide", file: "KMS_MIGRATION_GUIDE.md", type: "doc" },
      { slug: "threat-model", title: "Threat Model", file: "THREAT_MODEL.md", type: "doc" },
      { slug: "disaster-recovery", title: "Disaster Recovery", file: "DISASTER_RECOVERY.md", type: "doc" },
      { slug: "operations-runbook", title: "Operations Runbook", file: "OPERATIONS_RUNBOOK.md", type: "doc" },
      { slug: "key-rotation", title: "Key Rotation Guide", file: "KEY_ROTATION_GUIDE.md", type: "doc" },
    ],
  },
  {
    id: "sdks",
    label: "SDKs & Tools",
    icon: "Boxes",
    blurb: "First-party SDKs & integration tooling.",
    items: [
      { slug: "lnk-sdk-python", title: "Python SDK", href: `${SDK_RES}/python/pyproject.toml`, type: "link" },
      { slug: "lnk-sdk-javascript", title: "JavaScript SDK", href: `${SDK_RES}/javascript/index.js`, type: "link" },
      { slug: "lnk-sdk-java", title: "Java SDK", href: `${SDK_RES}/java/pom.xml`, type: "link" },
      { slug: "lnk-sdk-dotnet", title: ".NET SDK", href: `${SDK_RES}/dotnet/PfpVerifier.cs`, type: "link" },
      { slug: "lnk-postman", title: "Postman Collection", href: `${DOCS_RES}/postman_collection.json`, type: "link" },
      { slug: "lnk-openapi-sdk", title: "OpenAPI Specification", href: CANONICAL.openapi, type: "link" },
    ],
  },
  {
    id: "use-cases",
    label: "Industry Use Cases",
    icon: "Boxes",
    blurb: "How PFP applies across industries.",
    items: [
      { slug: "use-case-change-release", title: "Change & Release Management", file: "USE_CASE_CHANGE_RELEASE.md", type: "doc" },
    ],
  },
  {
    id: "deployment",
    label: "Deployment & Operations",
    icon: "ServerCog",
    blurb: "Deployment readiness & operational posture.",
    items: [
      { slug: "pilot-deployment", title: "Pilot Deployment Guide", file: "PILOT_DEPLOYMENT_GUIDE.md", type: "doc" },
      { slug: "product-readiness", title: "Product Readiness Assessment", file: "PRODUCT_READINESS_ASSESSMENT_V2.md", type: "doc" },
    ],
  },
  {
    id: "governance",
    label: "Governance & Compliance",
    icon: "Scale",
    blurb: "Audit, governance & compliance guidance.",
    items: [
      { slug: "verification-audit", title: "Verification Audit", file: "PFP_VERIFICATION_AUDIT.md", type: "doc" },
      { slug: "product-readiness", title: "Product Readiness Assessment", file: "PRODUCT_READINESS_ASSESSMENT_V2.md", type: "doc" },
    ],
  },
  {
    id: "api-specs",
    label: "API Specifications",
    icon: "FileJson",
    blurb: "Machine-readable specs & explorers.",
    items: [
      { slug: "lnk-openapi-json", title: "openapi.json", href: CANONICAL.openapi, type: "link" },
      { slug: "lnk-openapi-yaml", title: "openapi.yaml", href: `${DOCS_RES}/openapi.yaml`, type: "link" },
      { slug: "lnk-swagger-2", title: "Swagger UI", href: CANONICAL.swagger, type: "link" },
      { slug: "lnk-redoc-2", title: "ReDoc", href: CANONICAL.redoc, type: "link" },
    ],
  },
  {
    id: "releases",
    label: "Release Notes",
    icon: "Tag",
    blurb: "What changed, by version.",
    items: [
      { slug: "releases", title: "Release Notes", type: "releases" },
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
  // Aliases for files referenced in docs but surfaced under a different slug.
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
        out.push({ slug: it.slug, title: it.title, file: it.file, category: cat.label });
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
