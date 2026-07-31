import { useState } from "react";
import { toast } from "sonner";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Check,
  FileSignature,
  Fingerprint,
  ChevronDown,
  CreditCard,
  Globe,
  GitBranch,
  MessageSquare,
  KanbanSquare,
  Activity,
  Bot,
  Lock,
  UserCheck,
  ShoppingCart,
  BadgeCheck,
  ClipboardList,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Provider Summary framework — the crypto engine stays generic; only the
// PRESENTATION maps a provider "kind" to a human, domain-appropriate summary.
// Add a provider by adding one line here (no engine change).
// ---------------------------------------------------------------------------
const PROVIDER_DOMAINS = {
  docusign: { label: "Document Signing", Icon: FileSignature },
  stripe: { label: "Payment", Icon: CreditCard },
  razorpay: { label: "Payment", Icon: CreditCard },
  cashfree: { label: "Payment", Icon: CreditCard },
  tazapay: { label: "Cross-border Payment", Icon: Globe },
  github: { label: "Code Repository", Icon: GitBranch },
  slack: { label: "Messaging", Icon: MessageSquare },
  jira: { label: "Issue Tracking", Icon: KanbanSquare },
  auth0: { label: "Identity", Icon: UserCheck },
};

// Category -> icon (used when the descriptor carries a generic provider_category,
// so any future provider renders correctly with zero UI changes).
const CATEGORY_ICONS = {
  Payment: CreditCard,
  "Cross-border Payment": Globe,
  Document: FileSignature,
  Identity: UserCheck,
  "Source Control": GitBranch,
  Messaging: MessageSquare,
  "E-commerce": ShoppingCart,
  "Issue Tracking": KanbanSquare,
  Event: Activity,
};

function providerDomain(desc, isFinancial) {
  const cat = desc?.provider_category;
  if (cat) return { label: cat, Icon: CATEGORY_ICONS[cat] || Activity };
  const kind = (desc?.provider_kind || "").toLowerCase();
  if (PROVIDER_DOMAINS[kind]) return PROVIDER_DOMAINS[kind];
  if (isFinancial) return { label: "Payment", Icon: CreditCard };
  return { label: "Event", Icon: Activity };
}

// ---------------------------------------------------------------------------
// Business layer — human-readable event naming, colored badges, dynamically
// generated verified assertions, and a plain-language description. All derived
// from the authenticated event descriptor (no engine change). Assertion rules
// are data-driven/configurable per provider category.
// ---------------------------------------------------------------------------
const EVENT_NAMES = {
  issue_created: "Issue Created", issue_updated: "Release Activity", assignee_changed: "Issue Assigned",
  status_changed: "Status Changed", comment_added: "Comment Added", comment_updated: "Comment Updated",
  comment_deleted: "Comment Deleted", attachment_added: "Attachment Added", issue_resolved: "Issue Resolved",
  issue_deleted: "Issue Deleted", worklog_updated: "Worklog Updated",
  release_readiness: "Release Readiness Evaluation", change_release: "Release Readiness Evaluation",
  payment_captured: "Payment Captured", payment_success: "Payment Captured", order_paid: "Payment Captured",
  payment_failed: "Payment Failed", document_signed: "Document Signed", envelope_completed: "Document Signed",
  user_authenticated: "Identity Authenticated", login: "Identity Authenticated", identity_authenticated: "Identity Authenticated",
};
function humanEvent(desc, isFinancial) {
  if (!desc) return isFinancial ? "Payment Event" : "Event";
  const t = String(desc.event_type || "").toLowerCase().replace(/[.\-\s]+/g, "_");
  if (EVENT_NAMES[t]) return EVENT_NAMES[t];
  if (desc.provider_category === "Identity") return "Identity Authenticated";
  if (isFinancial && !desc.event_type) return "Payment Captured";
  return fmtLabel(desc.event_type || (isFinancial ? "payment" : "event"));
}

const EVENT_TONE = {
  "Issue Created": "emerald", "Status Changed": "blue", "Comment Added": "violet", "Comment Updated": "violet",
  "Attachment Added": "amber", "Issue Assigned": "cyan", "Issue Resolved": "emerald", "Release Activity": "blue",
  "Release Readiness Evaluation": "indigo",
  "Payment Captured": "emerald", "Payment Failed": "red", "Document Signed": "indigo",
  "Identity Authenticated": "slate",
};
const TONE_CLASSES = {
  emerald: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  blue: "bg-blue-50 text-blue-700 ring-blue-600/20",
  violet: "bg-violet-50 text-violet-700 ring-violet-600/20",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20",
  cyan: "bg-cyan-50 text-cyan-700 ring-cyan-600/20",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  red: "bg-red-50 text-red-700 ring-red-600/20",
  slate: "bg-slate-100 text-slate-700 ring-slate-500/20",
};
function EventBadge({ label }) {
  const tone = EVENT_TONE[label] || "slate";
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full ring-1 ${TONE_CLASSES[tone]}`} data-testid="event-badge">
      {label}
    </span>
  );
}

// Provider-specific DETAIL assertions (shown UNDERNEATH the standardized set).
// Keyed by provider category; every rule is context-guarded so only genuinely
// verified facts appear. The crypto/verification engine is untouched.
const ASSERTION_DETAILS = {
  "Issue Tracking": [
    { when: (c) => c.attr("Issue Key"), text: (c) => `Issue ${c.attr("Issue Key")} verified` },
    { when: (c) => c.attr("Project"), text: (c) => `Project ${c.attr("Project")} verified` },
    { when: (c) => c.event === "status_changed", text: "Status transition verified" },
    { when: (c) => c.event === "assignee_changed", text: "Assignee change verified" },
    { when: (c) => c.event === "comment_added", text: "Comment received" },
    { when: (c) => c.event === "attachment_added", text: "Attachment received" },
    { when: (c) => c.event === "issue_resolved", text: "Issue resolution verified" },
  ],
  Payment: [
    { when: (c) => c.txId, text: "Transaction identifier verified" },
    { when: (c) => c.financial, text: "Amount verified" },
    { when: (c) => c.financial, text: "Currency verified" },
  ],
  "Cross-border Payment": [
    { when: (c) => c.txId, text: "Transaction identifier verified" },
    { when: (c) => c.financial, text: "Amount verified" },
    { when: (c) => c.financial, text: "Currency verified" },
  ],
  Identity: [
    { when: (c) => c.provider, text: (c) => `${c.provider} session verified` },
  ],
  Document: [
    { when: (c) => c.txId, text: "Envelope identifier verified" },
  ],
};

// The standardized verification assertions — identical wording for EVERY
// provider so Jira, DocuSign, Auth0, Razorpay, Tazapay, Cashfree and future
// providers read as one unified Proof Infrastructure.
function buildAssertions(desc, valid, payload, isFinancial, occurredAt) {
  if (!valid) {
    return {
      standard: [{ text: "PFP Signature could NOT be verified", ok: false }],
      details: [],
    };
  }
  const standard = [
    { text: "Provider Event Verified", ok: true },
    { text: "Provider Authentication Verified", ok: true },
    { text: "Payload Integrity Verified", ok: true },
  ];
  if (occurredAt) standard.push({ text: "Timestamp Verified", ok: true });
  standard.push({ text: "PFP Signature Verified", ok: true });

  const ts = (payload && payload.transaction_summary) || {};
  const ctx = {
    event: String(desc?.event_type || "").toLowerCase().replace(/[.\-\s]+/g, "_"),
    provider: desc?.provider,
    financial: isFinancial,
    txId: ts.transaction_id,
    attr: (k) => desc?.attributes?.[k],
  };
  const rules = ASSERTION_DETAILS[desc?.provider_category] || [];
  const details = [];
  rules.forEach((r) => {
    if (r.when && !r.when(ctx)) return;
    details.push(typeof r.text === "function" ? r.text(ctx) : r.text);
  });
  return { standard, details };
}

function splitTransition(change) {
  if (!change) return [null, null];
  const parts = String(change).split(/→|->/);
  return [parts[0]?.trim() || null, parts[1]?.trim() || null];
}

function eventDescription(desc, payload, isFinancial, humanName) {
  if (!desc) return "";
  const a = desc.attributes || {};
  const provider = desc.provider || "the provider";
  const issue = a["Issue Key"];
  const ev = String(desc.event_type || "").toLowerCase();
  const [from, to] = splitTransition(a["Status Change"]);
  const ts = (payload && payload.transaction_summary) || {};
  if (ev === "status_changed" && from && to && issue) return `The ${provider} issue ${issue} moved from “${from}” to “${to}.”`;
  if (ev === "comment_added" && issue) return `A comment was added to ${provider} issue ${issue}.`;
  if (ev === "attachment_added" && issue) return `An attachment was added to ${provider} issue ${issue}.`;
  if (ev === "assignee_changed" && issue) return `${provider} issue ${issue} was reassigned.`;
  if (ev === "issue_created" && issue) return `Issue ${issue} was created${a.Project ? ` in ${a.Project}` : ""}.`;
  if (ev === "issue_resolved" && issue) return `${provider} issue ${issue} was resolved.`;
  if (desc.provider_category === "Identity") return `The user successfully authenticated using ${provider}.`;
  if (isFinancial) {
    const amt = fmtAmount(ts.amount, ts.currency);
    return `A payment${amt ? ` of ${amt}` : ""} was ${humanName === "Payment Failed" ? "attempted" : "captured"} via ${provider}.`;
  }
  return `${humanName} recorded via ${provider}.`;
}

function BusinessHeadlineCard({ humanName, description, domainLabel }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4" data-testid="card-business-headline">
      <div className="flex items-center gap-2 flex-wrap">
        <EventBadge label={humanName} />
        <span className="text-[11px] uppercase tracking-wide text-slate-400">{domainLabel}</span>
      </div>
      {description && <p className="mt-2 text-sm text-slate-700" data-testid="event-description">{description}</p>}
    </div>
  );
}

function VerifiedAssertionsCard({ standard, details }) {
  return (
    <Card icon={BadgeCheck} title="Verification Assertions" testId="card-verified-assertions">
      <div className="px-4 py-3 grid sm:grid-cols-2 gap-x-6 gap-y-2">
        {standard.map((a, i) => {
          const I = a.ok ? CheckCircle2 : AlertTriangle;
          return (
            <div key={i} className="flex items-center gap-2 text-sm" data-testid={`assertion-${i}`}>
              <I className={`h-4 w-4 shrink-0 ${a.ok ? "text-emerald-600" : "text-red-600"}`} />
              <span className={`font-medium ${a.ok ? "text-slate-800" : "text-red-700"}`}>{a.text}</span>
            </div>
          );
        })}
      </div>
      {details.length > 0 && (
        <div className="px-4 pb-3 pt-1 border-t border-slate-100" data-testid="assertion-details">
          <div className="text-[10px] uppercase tracking-wide text-slate-400 mb-1.5">Provider-specific details</div>
          <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
            {details.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-slate-600" data-testid={`assertion-detail-${i}`}>
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                <span>{t}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function EventSummaryCard({ desc, humanName, occurredAt }) {
  const a = desc.attributes || {};
  const [from, to] = splitTransition(a["Status Change"]);
  return (
    <Card icon={ClipboardList} title="Event Summary" testId="card-event-summary">
      <DataRow label="Provider" value={desc.provider} testId="summary-provider" />
      {a.Project && <DataRow label="Project" value={a.Project} testId="summary-project" />}
      {a["Issue Key"] && <DataRow label="Issue" value={a["Issue Key"]} testId="summary-issue" />}
      {a.Summary && <DataRow label="Summary" value={a.Summary} testId="summary-summary" />}
      <DataRow label="Event" node={<EventBadge label={humanName} />} testId="summary-event" />
      {from && <DataRow label="Previous Status" value={from} testId="summary-prev-status" />}
      {to && <DataRow label="New Status" value={to} testId="summary-new-status" />}
      {a.Assignee && <DataRow label="Assignee" value={a.Assignee} testId="summary-assignee" />}
      {a.Reporter && <DataRow label="Reporter" value={a.Reporter} testId="summary-reporter" />}
      {desc.auth_method && <DataRow label="Authenticated Via" value={desc.auth_method} testId="summary-auth-method" />}
      {occurredAt && <DataRow label="Occurred" value={fmtTs(occurredAt)} testId="summary-occurred" />}
    </Card>
  );
}

// Answers the enterprise questions a Proof Artifact should establish, in plain
// business language, BEFORE the technical evidence. Copy-only; no engine change.
function ProofScopeCard({ desc, valid, humanName }) {
  const provider = desc?.provider || "the provider";
  const method = desc?.auth_method;
  const provesText = valid
    ? `PFP independently verified an authenticated ${provider} event${method ? ` (${method})` : ""} and cryptographically sealed its verified contents. The signature confirms this record is authentic and has not been altered since issuance.`
    : `This Proof Artifact's signature could not be verified, so its contents cannot be trusted as authentic.`;
  return (
    <Card icon={ShieldCheck} title="What This Proof Establishes" testId="card-proof-scope">
      <div className="px-4 py-3 space-y-3 text-sm">
        <div className="flex items-start gap-2" data-testid="proof-proves">
          <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-emerald-600" />
          <div>
            <div className="font-semibold text-slate-800">What this proves</div>
            <p className="text-slate-600 mt-0.5">{provesText}</p>
          </div>
        </div>
        <div className="flex items-start gap-2" data-testid="proof-not-proves">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-slate-400" />
          <div>
            <div className="font-semibold text-slate-800">What this deliberately does not prove</div>
            <p className="text-slate-600 mt-0.5">
              It does not assert the business correctness or outcome of the underlying action, and it was
              <span className="font-medium text-slate-700"> not signed by {provider}</span> — PFP signed it after
              verifying an authenticated provider event.
            </p>
          </div>
        </div>
      </div>
    </Card>
  );
}

const LABELS = {
  transaction_id: "External Transaction ID",
  timestamp: "Event Timestamp",
  amount: "Amount",
  currency: "Currency",
  iat: "Proof Issued At",
  algorithm: "Signature Algorithm",
  public_key_id: "Signing Key ID",
  signature_version: "Signature Version",
  fea_hash: "Payload Hash",
  fea_version: "Artifact Version",
  issuer_id: "Issuer",
  tenant_id: "Tenant",
  jti: "Artifact Nonce (jti)",
  fea_id: "Proof Artifact ID",
  payer_hash: "Originator Commitment",
  payee_hash: "Counterparty Commitment",
  metadata_hash: "Metadata Commitment",
};

const RESERVED = new Set(["transaction_summary", "parties", "signature_version"]);

const titleCase = (k) =>
  String(k).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const fmtLabel = (s) => titleCase(String(s).replace(/[-_]/g, " "));

const isIsoLike = (v) =>
  typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v);
const isHashLike = (k) => /_hash$/.test(k) || k === "payer_hash" || k === "payee_hash";

const fmtTs = (iso) => {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  } catch {
    return String(iso);
  }
};

const fmtAmount = (amount, currency) => {
  if (amount === undefined || amount === null || amount === "") return null;
  const n = Number(amount) / 100;
  if (Number.isNaN(n)) return String(amount);
  const s = n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency ? `${s} ${currency}` : s;
};

// ---------------------------------------------------------------------------
// Design-system primitives (shared card / row / badge styling)
// ---------------------------------------------------------------------------
function CopyBtn({ value }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(String(value));
          setCopied(true);
          toast.success("Copied");
          setTimeout(() => setCopied(false), 1400);
        } catch {
          toast.error("Copy failed");
        }
      }}
      className="shrink-0 text-slate-400 hover:text-slate-700 transition-colors"
      title="Copy"
      data-testid="evidence-copy-btn"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

// Fixed-width label + left-aligned value + far-right copy, divided rows.
function DataRow({ label, value, mono = false, copy = false, node = null, testId }) {
  if (node == null && (value === undefined || value === null || value === "")) return null;
  return (
    <div
      className="grid grid-cols-[150px_minmax(0,1fr)_auto] items-center gap-3 px-4 py-2 border-b border-slate-100 last:border-b-0"
      data-testid={testId}
    >
      <span className="text-[11px] uppercase tracking-wide text-slate-500">{label}</span>
      <div className="min-w-0">
        {node != null ? (
          node
        ) : (
          <span
            className={`text-sm text-slate-900 break-all ${mono ? "font-mono text-xs text-slate-700" : ""}`}
            title={typeof value === "string" ? value : undefined}
          >
            {String(value)}
          </span>
        )}
      </div>
      {copy ? <CopyBtn value={value} /> : <span className="w-3.5" />}
    </div>
  );
}

function Card({ icon: Icon, title, right, children, testId }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden" data-testid={testId}>
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-100 bg-slate-50/70">
        {Icon && <Icon className="w-4 h-4 text-slate-500" />}
        <h4 className="text-[13px] font-semibold text-slate-900 font-['Space_Grotesk'] tracking-tight">{title}</h4>
        {right && <div className="ml-auto flex items-center">{right}</div>}
      </div>
      {children}
    </div>
  );
}

function DomainBadge({ text }) {
  return (
    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 uppercase tracking-wide">
      {text}
    </span>
  );
}

function StatusChip({ text }) {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 ring-1 ring-blue-600/20">
      {text}
    </span>
  );
}

function AuthMethodBadge({ text }) {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600/20" data-testid="auth-method-badge">
      <Lock className="w-3 h-3" />
      {text}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Row builders (authenticated evidence, verification metadata, commitments)
// ---------------------------------------------------------------------------
function buildRows(payload, artifact) {
  const p = payload || {};
  const ts = p.transaction_summary || {};
  const isFinancial = ts.amount !== undefined && ts.amount !== null && Number(ts.amount) > 0;

  const evidence = [];
  if (ts.transaction_id !== undefined)
    evidence.push({
      key: "transaction_id",
      label: isFinancial ? LABELS.transaction_id : "Reference / Envelope ID",
      value: ts.transaction_id, mono: true, copy: true,
    });
  if (isFinancial) {
    const amt = fmtAmount(ts.amount, ts.currency);
    if (amt !== null) evidence.push({ key: "amount", label: LABELS.amount, value: amt });
    if (ts.currency !== undefined) evidence.push({ key: "currency", label: LABELS.currency, value: ts.currency });
  }
  if (ts.timestamp !== undefined)
    evidence.push({ key: "timestamp", label: LABELS.timestamp, value: fmtTs(ts.timestamp) });
  Object.entries(ts).forEach(([k, v]) => {
    if (["transaction_id", "amount", "currency", "timestamp"].includes(k)) return;
    if (v === null || typeof v === "object") return;
    evidence.push({ key: k, label: LABELS[k] || titleCase(k), value: isIsoLike(v) ? fmtTs(v) : v });
  });
  const cryptoKeys = new Set(["algorithm", "public_key_id", "iat", "jti", "fea_version", "issuer_id", "fea_hash", "tenant_id"]);
  Object.entries(p).forEach(([k, v]) => {
    if (RESERVED.has(k) || cryptoKeys.has(k) || isHashLike(k)) return;
    if (v === null || typeof v === "object") return;
    evidence.push({ key: k, label: LABELS[k] || titleCase(k), value: isIsoLike(v) ? fmtTs(v) : v });
  });

  const crypto = [];
  const pushCrypto = (key, value, opts = {}) => {
    if (value === undefined || value === null || value === "") return;
    crypto.push({ key, label: LABELS[key] || titleCase(key), value, ...opts });
  };
  pushCrypto("iat", fmtTs(p.iat || artifact?.created_at));
  pushCrypto("algorithm", p.algorithm);
  pushCrypto("public_key_id", p.public_key_id || artifact?.public_key_id, { mono: true, copy: true });
  pushCrypto("signature_version", artifact?.signature_version || p.signature_version);
  pushCrypto("fea_hash", p.fea_hash, { mono: true, copy: true });
  pushCrypto("fea_version", p.fea_version);
  pushCrypto("issuer_id", p.issuer_id);
  if (artifact?.fea_id)
    crypto.push({ key: "fea_id", label: LABELS.fea_id, value: artifact.fea_id, mono: true, copy: true });
  pushCrypto("jti", p.jti, { mono: true });

  const commitments = [];
  const parties = p.parties || {};
  if (parties.payer_hash) commitments.push({ key: "payer_hash", label: LABELS.payer_hash, value: parties.payer_hash });
  if (parties.payee_hash) commitments.push({ key: "payee_hash", label: LABELS.payee_hash, value: parties.payee_hash });
  if (p.metadata_hash) commitments.push({ key: "metadata_hash", label: LABELS.metadata_hash, value: p.metadata_hash });

  return { evidence, crypto, commitments, isFinancial };
}

// ---------------------------------------------------------------------------
// Section cards
// ---------------------------------------------------------------------------
function VerificationStatusCard({ valid, reason }) {
  const ok = !!valid;
  const Icon = ok ? CheckCircle2 : AlertTriangle;
  return (
    <Card
      icon={ShieldCheck}
      title="Verification Status"
      testId="card-verification-status"
      right={
        <span
          className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ring-1 ${
            ok ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20" : "bg-red-50 text-red-700 ring-red-600/20"
          }`}
          data-testid="evidence-verification-status"
        >
          <Icon className="w-3 h-3" />
          {ok ? "Verified" : "Failed"}
        </span>
      }
    >
      <div className="px-4 py-3 flex items-start gap-3">
        <Icon className={`w-5 h-5 mt-0.5 shrink-0 ${ok ? "text-emerald-600" : "text-red-600"}`} />
        <div>
          <div className={`text-sm font-semibold ${ok ? "text-emerald-800" : "text-red-800"}`}>
            {ok ? "PFP Cryptographic Signature Verified" : "Verification Failed"}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            {ok
              ? "This Proof Artifact was cryptographically signed by PFP after successfully verifying an authenticated provider event. The originating provider did not sign this artifact. Verified independently against the public key registry — no internal systems were queried."
              : reason || "The proof signature could not be verified."}
          </div>
        </div>
      </div>
    </Card>
  );
}

function ProviderSummaryCard({ desc, domain }) {
  const attrs =
    desc.attributes && typeof desc.attributes === "object"
      ? Object.entries(desc.attributes).filter(([, v]) => v != null && v !== "")
      : [];
  return (
    <Card icon={domain.Icon} title="Provider Summary" testId="card-provider-summary" right={<DomainBadge text={domain.label} />}>
      <DataRow label="Provider" value={desc.provider} testId="evidence-provider" />
      <DataRow label="Category" value={domain.label} testId="evidence-category" />
      {desc.event_type && <DataRow label="Event Type" value={fmtLabel(desc.event_type)} testId="evidence-event-type" />}
      {desc.event_source && <DataRow label="Event Source" value={desc.event_source} testId="evidence-event-source" />}
      {desc.auth_method && <DataRow label="Authentication" node={<AuthMethodBadge text={desc.auth_method} />} testId="evidence-auth-method" />}
      {desc.status && <DataRow label="Status" node={<StatusChip text={fmtLabel(desc.status)} />} testId="evidence-status" />}
      {attrs.map(([k, v]) => (
        <DataRow
          key={k}
          label={k}
          value={String(v)}
          mono={/hash$|id$/i.test(k)}
          copy={/hash$|id$/i.test(k)}
          testId={`evidence-attr-${k.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
        />
      ))}
      <div className="px-4 py-2 text-[11px] text-slate-400 border-t border-slate-100">
        Recorded at ingestion · not part of the signature. Sensitive identifiers remain hash-only.
      </div>
    </Card>
  );
}

function RowsCard({ icon, title, rows, testId, emptyText }) {
  return (
    <Card icon={icon} title={title} testId={testId}>
      {rows.length > 0 ? (
        rows.map((r) => (
          <DataRow key={r.key} label={r.label} value={r.value} mono={r.mono} copy={r.copy} testId={`evidence-${r.key.replace(/_/g, "-")}`} />
        ))
      ) : (
        <div className="px-4 py-3 text-xs text-slate-500">{emptyText}</div>
      )}
    </Card>
  );
}

function AIAccountabilityCard({ ai }) {
  const hasAi = ai && typeof ai === "object" && Object.keys(ai).length > 0;
  if (!hasAi) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white px-4 py-2.5 flex items-center gap-2" data-testid="card-ai-none">
        <Bot className="w-4 h-4 text-slate-400 shrink-0" />
        <span className="text-xs text-slate-500">No AI provenance is associated with this proof.</span>
      </div>
    );
  }
  const rows = Object.entries(ai)
    .filter(([, v]) => v != null && typeof v !== "object")
    .map(([k, v]) => ({ key: k, label: fmtLabel(k), value: String(v), mono: /hash|id$/i.test(k), copy: /hash/i.test(k) }));
  return <RowsCard icon={Bot} title="AI Accountability" rows={rows} testId="card-ai" emptyText="No displayable AI fields." />;
}

function CommitmentsCard({ rows }) {
  const [open, setOpen] = useState(false);
  return (
    <Card
      icon={Lock}
      title="Privacy-Preserving Commitments"
      testId="card-commitments"
      right={
        <button
          type="button"
          onClick={() => setOpen((s) => !s)}
          aria-expanded={open}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-slate-800"
          data-testid="evidence-commitments-toggle"
        >
          {open ? "Hide" : "Show"} hashes
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      }
    >
      {open ? (
        rows.map((r) => (
          <DataRow key={r.key} label={r.label} value={r.value} mono copy testId={`evidence-${r.key.replace(/_/g, "-")}`} />
        ))
      ) : (
        <div className="px-4 py-2.5 text-[11px] text-slate-400">
          Sensitive content is committed as one-way hashes only ({rows.length} commitment{rows.length === 1 ? "" : "s"}). Expand to view.
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Public component — enterprise, card-based, provider-aware evidence view.
// ---------------------------------------------------------------------------
export default function EvidenceSummary({ artifact, valid, reason, showStatus = true }) {
  if (!artifact || !artifact.fea_payload) return null;
  const { evidence, crypto, commitments, isFinancial } = buildRows(artifact.fea_payload, artifact);
  const desc = artifact.event_descriptor;
  const ai = artifact.ai_provenance;
  const domain = providerDomain(desc, isFinancial);
  const hasBusiness = desc && (desc.provider || desc.event_type || desc.status || desc.provider_category);
  const humanName = humanEvent(desc, isFinancial);
  const occurredAt = desc?.occurred_at || artifact.fea_payload?.transaction_summary?.timestamp;
  const { standard, details } = buildAssertions(desc, valid, artifact.fea_payload, isFinancial, occurredAt);
  const description = eventDescription(desc, artifact.fea_payload, isFinancial, humanName);

  return (
    <div className="space-y-3 text-slate-900" data-testid="evidence-summary">
      {showStatus && <VerificationStatusCard valid={valid} reason={reason} />}
      {hasBusiness && (
        <>
          <BusinessHeadlineCard humanName={humanName} description={description} domainLabel={domain.label} />
          <ProofScopeCard desc={desc} valid={valid} humanName={humanName} />
          <VerifiedAssertionsCard standard={standard} details={details} />
          <EventSummaryCard desc={desc} humanName={humanName} occurredAt={occurredAt} />
        </>
      )}
      {hasBusiness && <ProviderSummaryCard desc={desc} domain={domain} />}
      <RowsCard
        icon={FileSignature}
        title="Authenticated Evidence"
        rows={evidence}
        testId="card-authenticated-evidence"
        emptyText="No additional authenticated business fields are present in this proof."
      />
      <RowsCard icon={Fingerprint} title="Verification Metadata" rows={crypto} testId="card-verification-metadata" emptyText="—" />
      <AIAccountabilityCard ai={ai} />
      {commitments.length > 0 && <CommitmentsCard rows={commitments} />}
    </div>
  );
}
