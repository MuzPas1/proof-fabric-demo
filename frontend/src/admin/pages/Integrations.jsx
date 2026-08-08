import React, { useEffect, useState } from "react";
import { api } from "../api";
import { PageHeader, Panel, StatusBadge, Empty, Mono, canWrite } from "../ui";
import { useAuth } from "../AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2, Power, PowerOff, RefreshCw, FlaskConical, Copy, Loader2, Activity, Pencil, ShieldCheck, CheckCircle2, XCircle, ChevronDown, ChevronRight, KanbanSquare, CreditCard, FileSignature, GitBranch, MessageSquare, ShoppingCart, Boxes, Settings2, Landmark } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";

const ADAPTERS = ["generic", "jira", "tarabut"];
const AUTH_PROVIDERS = ["hmac_sha256", "hmac_sha1", "rsa_sha256", "api_key", "bearer", "basic", "jwt", "oauth2", "mtls", "custom", "none"];
const EXTERNAL_PROVIDERS = ["jwt", "oauth2", "mtls", "custom"]; // externally configured (no PFP-minted credential)
const HMAC_PROVIDERS = ["hmac_sha256", "hmac_sha1"];
const SIGNATURE_SCHEMES = [
  { v: "plain", label: "Plain (PFP-minted secret)" },
  { v: "cashfree", label: "Cashfree (x-webhook-signature · base64)" },
  { v: "stripe", label: "Stripe (stripe-signature)" },
  { v: "slack", label: "Slack (x-slack-signature)" },
  { v: "docusign", label: "DocuSign Connect (x-docusign-signature-1 · base64)" },
];

// Recommended auth_config for each HMAC signature scheme (vendor-spec derived).
// Used to pre-fill the raw auth_config JSON when a scheme is picked in the Edit
// dialog, so switching an existing integration to (e.g.) DocuSign is one click.
const SCHEME_DEFAULTS = {
  plain: {},
  cashfree: { signature_scheme: "cashfree", signature_header: "x-webhook-signature", signature_encoding: "base64", timestamp_header: "x-webhook-timestamp" },
  stripe: { signature_scheme: "stripe", signature_header: "stripe-signature", signature_encoding: "hex" },
  slack: { signature_scheme: "slack", signature_header: "x-slack-signature", timestamp_header: "x-slack-request-timestamp", signature_prefix: "v0=", signature_encoding: "hex" },
  docusign: { signature_scheme: "docusign", signature_header: "x-docusign-signature-1", signature_encoding: "base64" },
};
const isHmacProvider = (p) => p === "hmac" || HMAC_PROVIDERS.includes(p);

// --- Simple-Mode provider presentation + dynamic connection forms -----------
// Presentation only (icon + accent). Category/adapter/auth come from the backend
// preset — the single source of truth — so the backend stays authoritative.
const PROVIDER_META = {
  jira: { Icon: KanbanSquare, tint: "text-blue-600 bg-blue-50 ring-blue-200" },
  cashfree: { Icon: CreditCard, tint: "text-emerald-600 bg-emerald-50 ring-emerald-200" },
  razorpay: { Icon: CreditCard, tint: "text-indigo-600 bg-indigo-50 ring-indigo-200" },
  stripe: { Icon: CreditCard, tint: "text-violet-600 bg-violet-50 ring-violet-200" },
  docusign: { Icon: FileSignature, tint: "text-amber-600 bg-amber-50 ring-amber-200" },
  github: { Icon: GitBranch, tint: "text-slate-700 bg-slate-100 ring-slate-200" },
  slack: { Icon: MessageSquare, tint: "text-fuchsia-600 bg-fuchsia-50 ring-fuchsia-200" },
  shopify: { Icon: ShoppingCart, tint: "text-green-600 bg-green-50 ring-green-200" },
  tarabut: { Icon: Landmark, tint: "text-cyan-700 bg-cyan-50 ring-cyan-200" },
  generic: { Icon: Boxes, tint: "text-slate-600 bg-slate-100 ring-slate-200" },
};
const providerMeta = (id) => PROVIDER_META[id] || { Icon: Boxes, tint: "text-slate-600 bg-slate-100 ring-slate-200" };

// Friendly labels for the read-only Configuration Summary.
const AUTH_METHOD_LABELS = {
  hmac_sha256: "HMAC-SHA256 signature", hmac_sha1: "HMAC-SHA1 signature",
  api_key: "API key / shared-secret header", bearer: "Bearer token", basic: "HTTP basic",
  jwt: "JWT", oauth2: "OAuth 2.0 bearer", mtls: "Mutual TLS", custom: "Custom",
  rsa_sha256: "RSA digital signature (RS256)",
  none: "None (unauthenticated)",
};
const SCHEME_LABELS = {
  plain: "Plain (over raw body)", cashfree: "Cashfree", stripe: "Stripe",
  slack: "Slack", docusign: "DocuSign Connect",
};

// Provider-specific connection fields shown in Simple Mode. Each maps either to
// an ``auth_config`` key or to the top-level ``secret``. Everything else is
// auto-configured from the preset. Unknown providers fall back to a single
// secret field only when the preset requires one.
const CONNECTION_FIELDS = {
  jira: [
    { key: "site_url", label: "Jira Site URL", placeholder: "https://your-domain.atlassian.net", target: "auth_config" },
    { key: "cloud_id", label: "Cloud ID (optional)", placeholder: "e.g. 11223344-aaaa-…", target: "auth_config", optional: true },
    { key: "secret", label: "Webhook Secret", type: "password", target: "secret", optional: true, full: true,
      placeholder: "Leave blank to have PFP generate one",
      help: "The secret you set on the Jira webhook. Jira signs each delivery with HMAC-SHA256 (X-Hub-Signature: sha256=…). Leave blank and PFP will generate a secret to paste into Jira." },
    { key: "project_filter", label: "Project Filter (optional)", placeholder: "e.g. REL, OPS", target: "auth_config", optional: true },
    { key: "event_filter", label: "Event Filter (optional)", placeholder: "issue_created, status_changed, …", target: "auth_config", optional: true },
  ],
  docusign: [{ key: "secret", label: "DocuSign Connect HMAC secret", type: "password", target: "secret", full: true, placeholder: "Settings → Connect → HMAC Security (secret key)" }],
  stripe: [{ key: "secret", label: "Stripe webhook signing secret (whsec_…)", type: "password", target: "secret", full: true, placeholder: "whsec_…" }],
  cashfree: [{ key: "secret", label: "Cashfree PG secret key", type: "password", target: "secret", full: true, placeholder: "Payments → Developers → Webhooks" }],
  razorpay: [{ key: "secret", label: "Razorpay webhook secret", type: "password", target: "secret", full: true, placeholder: "Settings → Webhooks → Secret" }],
  slack: [{ key: "secret", label: "Slack signing secret", type: "password", target: "secret", full: true, placeholder: "App → Basic Information → Signing Secret" }],
  github: [{ key: "secret", label: "GitHub webhook secret", type: "password", target: "secret", full: true, placeholder: "Repo/Org → Settings → Webhooks → Secret" }],
  shopify: [{ key: "secret", label: "Shopify webhook signing secret", type: "password", target: "secret", full: true, placeholder: "Settings → Notifications → Webhooks" }],
  tarabut: [
    { key: "oauth_client_id", label: "OAuth Client ID", target: "auth_config", full: true,
      placeholder: "Tarabut Dev Portal → App Settings → Client ID",
      help: "Used for outbound OAuth2 (Connect/Consent/Account Information) authentication." },
    { key: "secret", label: "OAuth Client Secret", type: "password", target: "secret", full: true,
      placeholder: "Tarabut Client Secret (stored redacted, never shown again)" },
    { key: "redirect_uri", label: "Redirect URI", target: "auth_config", full: true, optional: true,
      placeholder: "One of the redirect URIs registered on the Tarabut portal (e.g. http://localhost:3000/callback)" },
    { key: "jwks_url", label: "Webhook JWKS URL (optional)", target: "auth_config", optional: true, full: true,
      placeholder: "Tarabut RS256 public-keys / JWKS endpoint",
      help: "Inbound RS256 webhook verification key. Alternatively paste a PEM into auth_config.public_key via Advanced, or set accept_unverified=true to onboard first." },
    { key: "tarabut_region", label: "Region", target: "auth_config", optional: true,
      placeholder: "bahrain" },
  ],
  generic: [],
};
const connectionFields = (preset) => {
  if (!preset) return [];
  if (CONNECTION_FIELDS[preset.id]) return CONNECTION_FIELDS[preset.id];
  return preset.requires_secret
    ? [{ key: "secret", label: preset.secret_label || "Provider secret", type: "password", target: "secret", full: true, placeholder: preset.secret_hint || "stored redacted" }]
    : [];
};
const slugify = (s) => String(s || "").toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 63);

const EMPTY_FORM = {
  name: "", slug: "", slugTouched: false, adapter: "generic", auth_provider: "hmac_sha256",
  default_currency: "USD", auth_config: "", secret: "", sig_scheme: "plain", provider: "",
  requires_secret: false, secret_label: "Provider signing secret", secret_hint: "",
  require_timestamp: false, timestamp_tolerance_seconds: 300, replay_protection: false,
  connection: {},
};

// Renders the issued Proof Artifact for an inbound event: full FEA ID (canonical
// proof identifier), a copy control, and an independent-verify action that opens
// the Auditor Verification page pre-filled with this FEA ID.
function ProofCell({ event }) {
  const id = event.fea_id;
  if (!id) {
    return <span className="font-mono text-[11px] text-slate-400">{event.error || "—"}</span>;
  }
  const copy = () => {
    navigator.clipboard.writeText(id)
      .then(() => toast.success("Full FEA ID copied"))
      .catch(() => toast.error("Copy failed — select and copy manually"));
  };
  return (
    <div className="flex items-center gap-2 min-w-[260px]">
      <span
        className="font-mono text-[11px] text-slate-700 break-all leading-tight"
        title={`FEA ID (Proof Artifact identifier): ${id}`}
        data-testid={`fea-id-${id}`}
      >
        {id}
      </span>
      <button
        type="button"
        onClick={copy}
        className="shrink-0 text-slate-400 hover:text-slate-700"
        title="Copy full FEA ID"
        data-testid={`copy-fea-${id}`}
      >
        <Copy className="h-3.5 w-3.5" />
      </button>
      <a
        href={`/verify?fea_id=${encodeURIComponent(id)}`}
        target="_blank"
        rel="noreferrer"
        className="shrink-0 inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-800"
        title="Independently verify this proof on the Auditor Verification page"
        data-testid={`verify-fea-${id}`}
      >
        <ShieldCheck className="h-3.5 w-3.5" /> Verify
      </a>
    </div>
  );
}

// Parse a stored inbound-event diagnostic (e.g.
// "auth: invalid hmac_sha256 signature [scheme=docusign, header=missing, headers_seen=['content-type']]")
// into readable parts. Auth diagnostics carry a bracketed [scheme=...] block;
// normalize/timestamp/replay/proof errors are shown as a plain message.
function parseDiagnostic(error) {
  if (!error) return null;
  const catMatch = error.match(/^([a-z_]+):/i);
  const out = { category: catMatch ? catMatch[1] : null, raw: error, message: error.trim(), fields: {}, headersSeen: null };
  const schemeIdx = error.indexOf("[scheme=");
  if (schemeIdx >= 0) {
    out.message = error.slice(0, schemeIdx).trim();
    let inside = error.slice(schemeIdx + 1, error.lastIndexOf("]"));
    const hs = inside.match(/headers_seen=\[([^\]]*)\]/);
    if (hs) {
      out.headersSeen = hs[1].split(",").map((s) => s.trim().replace(/^['"]|['"]$/g, "")).filter(Boolean);
      inside = inside.replace(/headers_seen=\[[^\]]*\]/, "");
    }
    inside.split(",").forEach((pair) => {
      const m = pair.match(/\s*([a-z_]+)=(.+)/i);
      if (m) out.fields[m[1]] = m[2].trim().replace(/,\s*$/, "");
    });
  }
  return out;
}

function DiagField({ k, v, tone }) {
  const c = tone === "bad" ? "text-red-700" : tone === "good" ? "text-emerald-700" : "text-slate-800";
  return (
    <span>
      <span className="text-slate-500">{k}: </span>
      <span className={`font-medium ${c}`}>{v}</span>
    </span>
  );
}

const titleCaseWord = (s) => String(s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

// Map a raw inbound diagnostic to a concise, human-readable summary for
// auditors/compliance users. Full technical detail stays available on demand.
const ERROR_KINDS = [
  { re: /^auth:/i, title: "Authentication failed", desc: "The provider signature could not be verified." },
  { re: /^normalize:/i, title: "Event not accepted", desc: "The payload could not be mapped to a business event." },
  { re: /^timestamp:/i, title: "Timestamp rejected", desc: "The event timestamp was missing or outside the allowed window." },
  { re: /^replay:/i, title: "Duplicate event", desc: "This event was already processed (replay protection)." },
  { re: /^proof:/i, title: "Proof generation failed", desc: "The event authenticated but a proof could not be issued." },
];

function summarizeError(error) {
  const diag = parseDiagnostic(error);
  const kind = ERROR_KINDS.find((k) => k.re.test(error || ""));
  const title = kind ? kind.title : (diag?.category ? titleCaseWord(diag.category) : "Rejected");
  let desc = kind ? kind.desc : (diag?.message || error || "");
  if (diag?.fields?.hint) desc = "Wrong signature scheme configured — " + diag.fields.hint;
  return { title, desc, diag };
}

function StatusPill({ status }) {
  const map = {
    accepted: { c: "bg-emerald-50 text-emerald-700 ring-emerald-600/20", label: "Accepted", Icon: CheckCircle2 },
    rejected: { c: "bg-red-50 text-red-700 ring-red-600/20", label: "Rejected", Icon: XCircle },
    test: { c: "bg-amber-50 text-amber-700 ring-amber-600/20", label: "Test", Icon: FlaskConical },
  };
  const s = map[status] || { c: "bg-slate-100 text-slate-600 ring-slate-400/20", label: status || "—", Icon: Activity };
  const I = s.Icon;
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ring-1 ${s.c}`} data-testid={`status-pill-${status}`}>
      <I className="h-3 w-3" />{s.label}
    </span>
  );
}

// Expandable technical diagnostics (parsed fields + received headers + raw
// string). Kept out of the default view so business users see plain summaries.
function RejectionDetails({ error }) {
  const diag = parseDiagnostic(error);
  const headerVal = diag?.fields?.header;
  const headerMissing = headerVal === "missing";
  const copy = () => navigator.clipboard.writeText(error || "").then(() => toast.success("Diagnostic copied")).catch(() => toast.error("Copy failed"));
  return (
    <div className="space-y-2.5 rounded-md bg-slate-50 border border-slate-200 p-3" data-testid="rejection-details">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Technical diagnostic</span>
        <button type="button" onClick={copy} className="ml-auto text-slate-400 hover:text-slate-700" title="Copy raw diagnostic" data-testid="debug-copy-btn"><Copy className="h-3.5 w-3.5" /></button>
      </div>
      {diag && Object.keys(diag.fields).length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]" data-testid="debug-fields">
          {diag.fields.scheme && <DiagField k="scheme" v={diag.fields.scheme} />}
          {diag.fields.enc && <DiagField k="encoding" v={diag.fields.enc} />}
          {headerVal && <DiagField k="signature header" v={headerMissing ? "missing" : "present"} tone={headerMissing ? "bad" : "good"} />}
          {diag.fields.secret && <DiagField k="secret source" v={diag.fields.secret} />}
          {diag.fields.payload_len && <DiagField k="payload length" v={`${diag.fields.payload_len} bytes`} />}
        </div>
      )}
      {diag?.fields?.hint && (
        <div className="text-[11px] text-amber-900 bg-amber-50 border border-amber-300 rounded px-2.5 py-2" data-testid="debug-scheme-hint">
          <span className="font-semibold">Wrong signature scheme configured — </span>{diag.fields.hint}
        </div>
      )}
      {diag?.headersSeen && (
        <div className="text-[11px]" data-testid="debug-headers-seen">
          <div className="text-slate-500 mb-1">Headers received{headerMissing ? " (no signature header matched)" : ""}:</div>
          <div className="flex flex-wrap gap-1">
            {diag.headersSeen.length === 0 ? <span className="text-slate-400">none</span> : diag.headersSeen.map((h, i) => (
              <code key={i} className={`px-1.5 py-0.5 rounded font-mono ${/sign/i.test(h) ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{h}</code>
            ))}
          </div>
        </div>
      )}
      <div className="text-[11px] font-mono text-slate-500 break-all border-t border-slate-200 pt-2" data-testid="rejection-raw">{error}</div>
    </div>
  );
}

// Latest-event health — reflects the MOST RECENT event (never a stale historical
// rejection). Only the badge carries color; the panel stays neutral.
function EventHealthSummary({ events }) {
  const [open, setOpen] = useState(false);
  if (events === null) return null;
  const latest = events[0];
  if (!latest) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 flex items-center gap-2" data-testid="event-health-empty">
        <Activity className="h-4 w-4 text-slate-400" />
        <span className="text-xs text-slate-500">No events received yet.</span>
      </div>
    );
  }
  const when = latest.received_at?.slice(0, 19)?.replace("T", " ");
  const rejected = latest.status === "rejected";
  const sum = rejected ? summarizeError(latest.error) : null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-2" data-testid="event-health">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Latest event</span>
        <StatusPill status={latest.status} />
        <span className="text-sm text-slate-800">
          {latest.status === "accepted" && "Authenticated — proof issued."}
          {latest.status === "test" && "Connectivity test acknowledged."}
          {rejected && (sum?.title || "Rejected")}
        </span>
        <span className="ml-auto text-[11px] text-slate-400">{when} UTC</span>
      </div>
      {rejected && (
        <>
          <div className="text-xs text-slate-600" data-testid="event-health-desc">{sum.desc}</div>
          <button type="button" onClick={() => setOpen((s) => !s)} className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-800" data-testid="event-health-details-toggle">
            {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />} {open ? "Hide" : "View"} technical details
          </button>
          {open && <RejectionDetails error={latest.error} />}
        </>
      )}
      {!rejected && events.some((e) => e.status === "rejected") && (
        <div className="text-[11px] text-slate-400" data-testid="event-health-note">Older rejections exist — use the Rejected filter below to review them.</div>
      )}
    </div>
  );
}

function EventRow({ event }) {
  const [open, setOpen] = useState(false);
  const rejected = event.status === "rejected";
  const sum = rejected ? summarizeError(event.error) : null;
  return (
    <>
      <tr className="hover:bg-slate-50/70" data-testid={`event-row-${event.event_log_id}`}>
        <td className="px-3 py-2 whitespace-nowrap text-slate-500">{event.received_at?.slice(0, 19)?.replace("T", " ")}</td>
        <td className="px-3 py-2"><StatusPill status={event.status} /></td>
        <td className="px-3 py-2 text-slate-700">{event.event_type || "—"}</td>
        <td className="px-3 py-2 font-mono text-[11px] text-slate-600 max-w-[140px] truncate" title={event.external_id || ""}>{event.external_id || "—"}</td>
        <td className="px-3 py-2">
          {rejected ? (
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-slate-700 truncate max-w-[260px]" title={sum.desc}>{sum.title}</span>
              <button type="button" onClick={() => setOpen((s) => !s)} className="shrink-0 inline-flex items-center gap-0.5 text-[11px] font-medium text-blue-600 hover:text-blue-800" data-testid={`event-details-${event.event_log_id}`}>
                {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />} Details
              </button>
            </div>
          ) : (
            <ProofCell event={event} />
          )}
        </td>
      </tr>
      {open && rejected && (
        <tr className="bg-slate-50/40"><td colSpan={5} className="px-3 pb-3 pt-1"><RejectionDetails error={event.error} /></td></tr>
      )}
    </>
  );
}

// Enterprise recent-events table: bordered, filterable (All | Accepted |
// Rejected), badge-based status, human-readable summaries, and per-row
// expandable technical detail. Successes and rejections separate via the filter.
function RecentEventsTable({ events }) {
  const [filter, setFilter] = useState("all");
  if (events === null) return <Empty>Loading…</Empty>;
  const counts = {
    all: events.length,
    accepted: events.filter((e) => e.status === "accepted").length,
    rejected: events.filter((e) => e.status === "rejected").length,
  };
  const filtered = filter === "all" ? events : events.filter((e) => e.status === filter);
  const FilterBtn = ({ id, label }) => (
    <button type="button" onClick={() => setFilter(id)} data-testid={`events-filter-${id}`}
      className={`text-xs px-2.5 py-1 rounded-md border transition-colors ${filter === id ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"}`}>
      {label} <span className={filter === id ? "text-slate-300" : "text-slate-400"}>({counts[id]})</span>
    </button>
  );
  return (
    <div data-testid="recent-events">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mr-1">Recent events</span>
        <FilterBtn id="all" label="All" />
        <FilterBtn id="accepted" label="Accepted" />
        <FilterBtn id="rejected" label="Rejected" />
      </div>
      {filtered.length === 0 ? <Empty>No {filter === "all" ? "" : filter} events</Empty> : (
        <div className="rounded-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-xs" data-testid="integration-events-table">
            <thead>
              <tr className="text-left text-slate-500 bg-slate-50 border-b border-slate-200">
                <th className="px-3 py-2 font-medium">When (UTC)</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">External ID</th>
                <th className="px-3 py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((e) => <EventRow key={e.event_log_id} event={e} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// Connection self-test / Test Webhook Simulator result — per-step outcome list.
function SimSteps({ result }) {
  const tone = { success: "text-emerald-600", failed: "text-red-600", skipped: "text-amber-500" };
  const Icon = { success: CheckCircle2, failed: XCircle, skipped: Activity };
  return (
    <div className="mt-3 space-y-1.5" data-testid="simulator-result">
      {result.steps.map((s) => {
        const I = Icon[s.status] || Activity;
        return (
          <div key={s.key} className="flex items-start gap-2 text-sm" data-testid={`sim-step-${s.key}`}>
            <I className={`h-4 w-4 mt-0.5 shrink-0 ${tone[s.status] || "text-slate-400"}`} />
            <div className="min-w-0">
              <span className="text-slate-800">{s.label}</span>
              {s.status === "skipped" && <span className="ml-1 text-[11px] text-amber-600">(simulated)</span>}
              {s.status === "success" && <span className="ml-1 text-[11px] text-emerald-600">passed</span>}
              {s.detail && (
                <div className="text-[11px] text-slate-500 break-all">
                  {s.key === "proof" && s.status === "success" ? <>Proof <span className="font-mono">{s.detail}</span></> : s.detail}
                </div>
              )}
            </div>
          </div>
        );
      })}
      {result.fea_id && (
        <a href={`/verify?fea_id=${encodeURIComponent(result.fea_id)}`} target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-800 mt-1" data-testid="sim-verify-link">
          <ShieldCheck className="h-3.5 w-3.5" /> View the sample proof
        </a>
      )}
    </div>
  );
}


export default function Integrations() {
  const { user } = useAuth();
  const writable = canWrite(user?.role);
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [presets, setPresets] = useState([]);
  const [credential, setCredential] = useState(null);
  const [selected, setSelected] = useState(null);
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState(null);
  const [testPayload, setTestPayload] = useState(
    `{\n  "type": "invoice.created",\n  "id": "INV-${Date.now()}",\n  "timestamp": "2026-06-10T12:00:00Z",\n  "actor": "system-a",\n  "subject": "account-42",\n  "amount": 25000,\n  "currency": "USD"\n}`
  );
  const [testResult, setTestResult] = useState(null);
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [editBusy, setEditBusy] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [simResult, setSimResult] = useState(null);
  const [simBusy, setSimBusy] = useState(false);

  const load = async () => {
    try { const d = await api.listIntegrations(); setItems(d.integrations || []); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed to load integrations"); setItems([]); }
  };
  const loadPresets = async () => {
    try { const d = await api.listIntegrationPresets(); setPresets(d.presets || []); } catch { setPresets([]); }
  };
  useEffect(() => { load(); loadPresets(); }, []);

  const applyPreset = (id) => {
    const p = presets.find((x) => x.id === id) || {};
    const cfg = p.auth_config && Object.keys(p.auth_config).length ? JSON.stringify(p.auth_config, null, 2) : "";
    const scheme = (p.auth_config && p.auth_config.signature_scheme) || "plain";
    setForm((f) => ({
      ...EMPTY_FORM,
      name: f.name,
      slug: f.slugTouched ? f.slug : (f.name ? slugify(f.name) : ""),
      slugTouched: f.slugTouched,
      provider: id,
      adapter: p.adapter || "generic",
      auth_provider: p.auth_provider || "hmac_sha256",
      auth_config: cfg,
      requires_secret: !!p.requires_secret,
      secret_label: p.secret_label || "Provider signing secret",
      secret_hint: p.secret_hint || "",
      require_timestamp: !!p.require_timestamp,
      timestamp_tolerance_seconds: p.timestamp_tolerance_seconds || 300,
      replay_protection: !!p.replay_protection,
      sig_scheme: scheme,
    }));
    setAdvancedOpen(false);
  };
  const activePreset = presets.find((x) => x.id === form.provider);
  const connFields = connectionFields(activePreset);
  // Signature scheme currently in effect (preset config, or the generic override).
  const effectiveScheme = (() => {
    try {
      const cfg = form.auth_config.trim() ? JSON.parse(form.auth_config) : {};
      return cfg.signature_scheme || (form.provider === "generic" ? form.sig_scheme : "plain");
    } catch { return form.sig_scheme; }
  })();

  const setConn = (key, value) => setForm((f) => ({ ...f, connection: { ...f.connection, [key]: value } }));

  const create = async () => {
    setBusy(true); setCredential(null);
    let auth_config = {};
    if (form.auth_config.trim()) {
      try { auth_config = JSON.parse(form.auth_config); }
      catch { toast.error("Advanced auth config is not valid JSON"); setBusy(false); return; }
    }
    // Overlay Simple-Mode connection fields onto the preset config.
    let secret = "";
    connFields.forEach((fld) => {
      const v = (form.connection[fld.key] || "").trim();
      if (!v) return;
      if (fld.target === "secret") secret = v;
      else auth_config[fld.key] = v;
    });
    if (!secret && form.secret.trim()) secret = form.secret.trim();
    // Generic provider: apply the chosen signature scheme.
    if (form.provider === "generic" && HMAC_PROVIDERS.includes(form.auth_provider) && form.sig_scheme && form.sig_scheme !== "plain") {
      auth_config.signature_scheme = form.sig_scheme;
    }
    const body = {
      name: form.name, slug: form.slug, adapter: form.adapter, auth_provider: form.auth_provider,
      default_currency: form.default_currency, auth_config,
      require_timestamp: form.require_timestamp, replay_protection: form.replay_protection,
      timestamp_tolerance_seconds: form.timestamp_tolerance_seconds || 300,
    };
    if (secret) body.secret = secret;
    try {
      const r = await api.createIntegration(body);
      if (r.credential) setCredential({ slug: r.slug, credential: r.credential, url: r.inbound_url || `/api/ingest/${r.slug}`, provider: activePreset?.label || form.provider });
      toast.success(r.credential ? "Integration created — secret generated" : "Integration created");
      setForm(EMPTY_FORM); setAdvancedOpen(false);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Create failed"); }
    finally { setBusy(false); }
  };

  const toggle = async (it) => {
    try {
      if (it.enabled) await api.disableIntegration(it.integration_id);
      else await api.enableIntegration(it.integration_id);
      toast.success(it.enabled ? "Disabled" : "Enabled"); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Action failed"); }
  };

  const rotate = async (it) => {
    try {
      const r = await api.rotateIntegrationSecret(it.integration_id);
      if (r.credential) setCredential({ slug: it.slug, credential: r.credential, url: `/api/ingest/${it.slug}` });
      toast.success("Secret rotated");
    } catch (e) { toast.error(e?.response?.data?.detail || "Rotate failed"); }
  };

  const remove = (it) => { setDeleteTarget(it); };
  const doDelete = async () => {
    const it = deleteTarget;
    if (!it) return;
    setDeleteBusy(true);
    try {
      await api.deleteIntegration(it.integration_id);
      toast.success("Integration deleted — existing proofs & audit logs are preserved");
      if (selected?.integration_id === it.integration_id) setSelected(null);
      setDeleteTarget(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Delete failed"); }
    finally { setDeleteBusy(false); }
  };

  const runSimulate = async (it) => {
    setSimBusy(true);
    if (selected?.integration_id === it.integration_id) setSimResult(null);
    try {
      const r = await api.simulateIntegration(it.integration_id);
      if (selected?.integration_id === it.integration_id) setSimResult(r);
      if (r.ok) toast.success("Connection validated — sample proof generated");
      else {
        const failed = (r.steps || []).find((s) => s.status === "failed");
        toast.error(failed ? `Validation failed at ${failed.label}: ${failed.detail || ""}` : "Validation failed");
      }
      if (selected?.integration_id === it.integration_id) loadStatsEvents(it);
    } catch (e) { toast.error(e?.response?.data?.detail || "Validation failed"); }
    finally { setSimBusy(false); }
  };

  const loadStatsEvents = async (it) => {
    try { setStats(await api.integrationStats(it.integration_id)); } catch { /* noop */ }
    try { const e = await api.integrationEvents(it.integration_id); setEvents(e.events || []); } catch { setEvents([]); }
  };

  const openDetails = async (it) => {
    setSelected(it); setStats(null); setEvents(null); setTestResult(null); setSimResult(null);
    loadStatsEvents(it);
  };

  const runTest = async (issue) => {
    let payload;
    try { payload = JSON.parse(testPayload); }
    catch { toast.error("Payload is not valid JSON"); return; }
    try {
      const r = await api.testIntegration(selected.integration_id, payload, issue);
      setTestResult(r);
      toast.success(issue ? `Test event issued${r.fea_id ? ` (proof ${r.fea_id.slice(0, 8)}…)` : ""}` : "Dry-run OK");
      if (issue) loadStatsEvents(selected); // refresh counters/events WITHOUT clearing the result
    } catch (e) { toast.error(e?.response?.data?.detail || "Test failed"); }
  };

  const copy = (v) => { navigator.clipboard.writeText(v); toast.success("Copied"); };

  const openEdit = async (it) => {
    try {
      const full = await api.getIntegration(it.integration_id);
      setEditForm({
        name: full.name || "",
        description: full.description || "",
        auth_config: full.auth_config && Object.keys(full.auth_config).length ? JSON.stringify(full.auth_config, null, 2) : "",
        secret: "",
        require_timestamp: !!full.require_timestamp,
        replay_protection: !!full.replay_protection,
        timestamp_tolerance_seconds: full.timestamp_tolerance_seconds || 300,
        has_external_secret: !!full.has_external_secret,
        has_hmac_secret: !!full.has_hmac_secret,
        has_credential: !!full.has_credential,
        auth_provider: full.auth_provider,
        signature_scheme: full.signature_scheme,
      });
      setEditing(it);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to load integration"); }
  };

  const applyEditScheme = (scheme) => {
    const cfg = SCHEME_DEFAULTS[scheme] || {};
    setEditForm((f) => ({
      ...f,
      signature_scheme: scheme,
      auth_config: Object.keys(cfg).length ? JSON.stringify(cfg, null, 2) : "",
    }));
  };

  const saveEdit = async () => {
    setEditBusy(true);
    const body = {
      name: editForm.name,
      description: editForm.description,
      require_timestamp: editForm.require_timestamp,
      replay_protection: editForm.replay_protection,
      timestamp_tolerance_seconds: editForm.timestamp_tolerance_seconds || 300,
    };
    if (editForm.auth_config.trim()) {
      try { body.auth_config = JSON.parse(editForm.auth_config); }
      catch { toast.error("Auth config is not valid JSON"); setEditBusy(false); return; }
    }
    const secretReplaced = !!editForm.secret.trim();
    if (secretReplaced) body.secret = editForm.secret.trim();
    try {
      await api.updateIntegration(editing.integration_id, body);
      toast.success(secretReplaced ? "Integration updated — secret replaced" : "Integration updated");
      setEditing(null); setEditForm(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Update failed"); }
    finally { setEditBusy(false); }
  };

  return (
    <div data-testid="integrations-page">
      <PageHeader title="Inbound Integrations"
        description="Configure external systems that submit verifiable business events for Proof Artifact generation." />

      {credential && (
        <Panel title="Webhook secret — copy it now" className="mb-4">
          <div className="p-4 space-y-3" data-testid="integration-credential">
            <div className="flex items-start gap-2 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-3 py-2">
              <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
              <span>
                <b>Secret stored and active.</b> Shown only once — copy it now and paste it into{" "}
                {credential.provider ? <b>{credential.provider}</b> : "your provider"}&rsquo;s webhook <b>Secret</b> field.
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Mono>{credential.credential}</Mono>
              <Button size="sm" variant="outline" className="h-7" onClick={() => copy(credential.credential)} data-testid="credential-copy-btn"><Copy className="h-3.5 w-3.5" /></Button>
            </div>
            <div className="text-xs text-slate-500">Inbound URL: <Mono>{credential.url}</Mono></div>
            <div className="text-[11px] text-slate-400">
              You won&rsquo;t be able to view this secret again. Use &ldquo;Rotate secret&rdquo; on the integration to generate a fresh one.
            </div>
          </div>
        </Panel>
      )}

      {writable && (
        <Panel title="Connect a provider" className="mb-4">
          <div className="p-4 space-y-5" data-testid="integration-connect">
            {/* Step 1 — choose the system to connect */}
            <div>
              <Label>Choose the system you want to connect</Label>
              <div className="mt-2 grid grid-cols-2 md:grid-cols-3 gap-2" data-testid="integration-provider">
                {presets.map((p) => {
                  const meta = providerMeta(p.id);
                  const Icon = meta.Icon;
                  const selected = form.provider === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => applyPreset(p.id)}
                      data-testid={`provider-card-${p.id}`}
                      aria-pressed={selected}
                      className={`text-left rounded-lg border p-3 transition-colors ${selected ? "border-slate-900 ring-1 ring-slate-900 bg-slate-50" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/60"}`}
                    >
                      <div className="flex items-center gap-2.5">
                        <span className={`inline-flex h-8 w-8 items-center justify-center rounded-md ring-1 ${meta.tint}`}>
                          <Icon className="h-4 w-4" />
                        </span>
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-slate-900 truncate">{p.label}</div>
                          <div className="text-[11px] text-slate-500 capitalize truncate">{String(p.category || "").replace(/-/g, " ")}</div>
                        </div>
                        {selected && <CheckCircle2 className="ml-auto h-4 w-4 text-slate-900 shrink-0" />}
                      </div>
                    </button>
                  );
                })}
              </div>
              {!form.provider && <div className="mt-2 text-xs text-slate-400">Pick a provider to see its recommended, ready-to-use configuration.</div>}
            </div>

            {activePreset && (
              <>
                {activePreset.description && (
                  <div className="text-xs text-slate-500" data-testid="integration-provider-note">
                    {activePreset.description}
                    {activePreset.docs_url && (
                      <> · <a href={activePreset.docs_url} target="_blank" rel="noreferrer" className="text-blue-600 underline">Vendor webhook spec</a></>
                    )}
                  </div>
                )}

                {/* Step 2 — connection details only */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Name</Label>
                    <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value, slug: form.slugTouched ? form.slug : slugify(e.target.value) })}
                      placeholder={`${activePreset.label} — Production`} className="mt-1" data-testid="integration-name" />
                  </div>
                  <div>
                    <Label>Slug (used in the inbound URL)</Label>
                    <Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value, slugTouched: true })}
                      placeholder="acme-jira" className="mt-1" data-testid="integration-slug" />
                  </div>
                  {connFields.map((fld) => (
                    <div key={fld.key} className={fld.full || fld.help ? "col-span-2" : ""}>
                      <Label>{fld.label}</Label>
                      <Input type={fld.type || "text"} value={form.connection[fld.key] || ""}
                        onChange={(e) => setConn(fld.key, e.target.value)}
                        placeholder={fld.placeholder} className="mt-1"
                        autoComplete={fld.type === "password" ? "new-password" : "off"}
                        data-testid={`integration-conn-${fld.key}`} />
                      {fld.help && <div className="text-[11px] text-slate-500 mt-1">{fld.help}</div>}
                    </div>
                  ))}
                  {connFields.length === 0 && (
                    <div className="col-span-2 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded px-3 py-2">
                      No connection secret to enter — PFP will generate a signing secret and show it once after you create this integration.
                    </div>
                  )}
                </div>

                {/* Advanced configuration — collapsed by default */}
                <div className="border-t border-slate-100 pt-3">
                  <button type="button" onClick={() => setAdvancedOpen((o) => !o)} data-testid="integration-advanced-toggle"
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900">
                    <Settings2 className="h-4 w-4" /> Advanced configuration
                    <ChevronDown className={`h-4 w-4 transition-transform ${advancedOpen ? "rotate-180" : ""}`} />
                  </button>
                  <div className="text-[11px] text-slate-400 mt-1">Recommended defaults are already applied. Only change these if you need to.</div>
                  {advancedOpen && (
                    <div className="mt-3 grid grid-cols-2 gap-3" data-testid="integration-advanced">
                      <div>
                        <Label>Adapter</Label>
                        <Select value={form.adapter} onValueChange={(v) => setForm({ ...form, adapter: v })}>
                          <SelectTrigger className="mt-1" data-testid="integration-adapter"><SelectValue /></SelectTrigger>
                          <SelectContent>{ADAPTERS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Authentication provider</Label>
                        <Select value={form.auth_provider} onValueChange={(v) => setForm({ ...form, auth_provider: v })}>
                          <SelectTrigger className="mt-1" data-testid="integration-auth"><SelectValue /></SelectTrigger>
                          <SelectContent>{AUTH_PROVIDERS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                      {isHmacProvider(form.auth_provider) && (
                        <div>
                          <Label>Signature scheme</Label>
                          <Select value={form.sig_scheme} onValueChange={(v) => setForm({ ...form, sig_scheme: v })}>
                            <SelectTrigger className="mt-1" data-testid="integration-sig-scheme"><SelectValue /></SelectTrigger>
                            <SelectContent>{SIGNATURE_SCHEMES.map((s) => <SelectItem key={s.v} value={s.v}>{s.label}</SelectItem>)}</SelectContent>
                          </Select>
                        </div>
                      )}
                      <div>
                        <Label>Default currency</Label>
                        <Input value={form.default_currency} onChange={(e) => setForm({ ...form, default_currency: e.target.value.toUpperCase().slice(0, 3) })}
                          className="mt-1" data-testid="integration-currency" />
                      </div>
                      <div className="col-span-2">
                        <Label>Auth config (JSON — review &amp; override)</Label>
                        <textarea value={form.auth_config} onChange={(e) => setForm({ ...form, auth_config: e.target.value })}
                          rows={5} className="mt-1 w-full font-mono text-xs border border-slate-200 rounded p-2" data-testid="integration-auth-config" />
                      </div>
                      <div>
                        <Label>Provider secret (optional override)</Label>
                        <Input type="password" value={form.secret} onChange={(e) => setForm({ ...form, secret: e.target.value })}
                          placeholder="Overrides the connection secret above" className="mt-1" data-testid="integration-secret" autoComplete="new-password" />
                      </div>
                      <div className="col-span-2 flex items-center gap-6 flex-wrap">
                        <label className="flex items-center gap-2 text-sm text-slate-600">
                          <input type="checkbox" checked={form.require_timestamp} data-testid="integration-require-timestamp"
                            onChange={(e) => setForm({ ...form, require_timestamp: e.target.checked })} /> Timestamp validation
                        </label>
                        <label className="flex items-center gap-2 text-sm text-slate-600">
                          <input type="checkbox" checked={form.replay_protection} data-testid="integration-replay-protection"
                            onChange={(e) => setForm({ ...form, replay_protection: e.target.checked })} /> Replay protection
                        </label>
                        {form.require_timestamp && (
                          <label className="flex items-center gap-2 text-sm text-slate-600">
                            Tolerance (s)
                            <Input type="number" min={1} value={form.timestamp_tolerance_seconds}
                              onChange={(e) => setForm({ ...form, timestamp_tolerance_seconds: parseInt(e.target.value || "300", 10) })}
                              className="h-8 w-24" data-testid="integration-timestamp-tolerance" />
                          </label>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Configuration summary — read-only confidence check */}
                <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3" data-testid="integration-config-summary">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Configuration summary</div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1.5 text-xs">
                    <div><span className="text-slate-500">Provider: </span><span className="font-medium text-slate-800">{activePreset.label}</span></div>
                    <div><span className="text-slate-500">Category: </span><span className="font-medium text-slate-800 capitalize">{String(activePreset.category || "").replace(/-/g, " ")}</span></div>
                    <div><span className="text-slate-500">Authentication: </span><span className="font-medium text-slate-800">{AUTH_METHOD_LABELS[form.auth_provider] || form.auth_provider}</span></div>
                    {isHmacProvider(form.auth_provider) && (
                      <div><span className="text-slate-500">Signature scheme: </span><span className="font-medium text-slate-800">{SCHEME_LABELS[effectiveScheme] || effectiveScheme}</span></div>
                    )}
                    <div><span className="text-slate-500">Adapter: </span><span className="font-medium text-slate-800">{form.adapter}</span></div>
                  </div>
                  <div className="mt-2.5 flex items-center gap-5 text-xs border-t border-slate-200 pt-2">
                    <span className="text-slate-500">Security</span>
                    <span className={`inline-flex items-center gap-1 ${form.replay_protection ? "text-emerald-700" : "text-slate-400"}`} data-testid="summary-replay">
                      {form.replay_protection ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />} Replay protection
                    </span>
                    <span className={`inline-flex items-center gap-1 ${form.require_timestamp ? "text-emerald-700" : "text-slate-400"}`} data-testid="summary-timestamp">
                      {form.require_timestamp ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />} Timestamp validation
                    </span>
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button onClick={create} disabled={busy || !form.name.trim() || !form.slug.trim()}
                    className="bg-slate-900 hover:bg-slate-800" data-testid="integration-create">
                    {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Plus className="h-4 w-4 mr-1.5" />} Create integration
                  </Button>
                </div>
              </>
            )}
          </div>
        </Panel>
      )}

      <Panel>
        {items === null ? <Empty>Loading…</Empty> : items.length === 0 ? <Empty>No integrations configured</Empty> : (
          <table className="w-full text-sm" data-testid="integrations-table">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                <th className="px-4 py-2.5 font-medium">Name / Slug</th>
                <th className="px-4 py-2.5 font-medium">Adapter</th>
                <th className="px-4 py-2.5 font-medium">Auth</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((it) => (
                <tr key={it.integration_id} data-testid={`integration-row-${it.slug}`}>
                  <td className="px-4 py-2.5">
                    <div className="text-slate-800">{it.name}</div>
                    <Mono>/api/ingest/{it.slug}</Mono>
                  </td>
                  <td className="px-4 py-2.5"><Mono>{it.adapter}</Mono></td>
                  <td className="px-4 py-2.5"><Mono>{it.auth_provider}</Mono></td>
                  <td className="px-4 py-2.5"><StatusBadge status={it.status} /></td>
                  <td className="px-4 py-2.5 text-right space-x-1.5 whitespace-nowrap">
                    <Button variant="outline" size="sm" className="h-7" onClick={() => openDetails(it)}
                      data-testid={`integration-details-${it.slug}`}><Activity className="h-3.5 w-3.5" /></Button>
                    {writable && (<>
                      <Button variant="outline" size="sm" className="h-7" onClick={() => runSimulate(it)} disabled={simBusy}
                        title="Validate connection (send a signed sample event)" data-testid={`integration-validate-${it.slug}`}>
                        <ShieldCheck className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="outline" size="sm" className="h-7" onClick={() => toggle(it)}
                        data-testid={`integration-toggle-${it.slug}`}>
                        {it.enabled ? <PowerOff className="h-3.5 w-3.5" /> : <Power className="h-3.5 w-3.5" />}
                      </Button>
                      <Button variant="outline" size="sm" className="h-7" onClick={() => openEdit(it)}
                        data-testid={`integration-edit-${it.slug}`}><Pencil className="h-3.5 w-3.5" /></Button>
                      <Button variant="outline" size="sm" className="h-7" onClick={() => rotate(it)}
                        data-testid={`integration-rotate-${it.slug}`}><RefreshCw className="h-3.5 w-3.5" /></Button>
                      <Button variant="outline" size="sm" className="h-7 text-red-600 border-red-200 hover:bg-red-50"
                        onClick={() => remove(it)} data-testid={`integration-delete-${it.slug}`}><Trash2 className="h-3.5 w-3.5" /></Button>
                    </>)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {selected && (
        <Panel title={`Monitoring & Test — ${selected.name}`} className="mt-4">
          <div className="p-4 space-y-4" data-testid="integration-detail-panel">
            {stats && (
              <div className="grid grid-cols-4 gap-3 text-sm">
                <div><div className="text-xs text-slate-500">Health</div><StatusBadge status={stats.health === "healthy" ? "active" : "suspended"} /></div>
                <div><div className="text-xs text-slate-500">Received</div><div className="font-semibold" data-testid="stat-received">{stats.total_received}</div></div>
                <div><div className="text-xs text-slate-500">Accepted</div><div className="font-semibold text-emerald-700">{stats.total_accepted}</div></div>
                <div><div className="text-xs text-slate-500">Rejected</div><div className="font-semibold text-red-700">{stats.total_rejected}</div></div>
              </div>
            )}

            <EventHealthSummary events={events} />

            {writable && (
              <div className="rounded-lg border border-slate-200 p-3" data-testid="integration-simulator">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div>
                    <div className="text-sm font-medium text-slate-800">Test webhook simulator</div>
                    <div className="text-xs text-slate-500">Generate a signed sample event and run the full pipeline — no external system needed.</div>
                  </div>
                  <Button size="sm" onClick={() => runSimulate(selected)} disabled={simBusy}
                    className="bg-slate-900 hover:bg-slate-800" data-testid="integration-simulate-btn">
                    {simBusy ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5 mr-1.5" />} Validate connection
                  </Button>
                </div>
                {simResult && (
                  <>
                    <div className={`mt-3 text-sm font-medium ${simResult.ok ? "text-emerald-700" : "text-red-700"}`} data-testid="simulator-headline">
                      {simResult.ok ? "✅ Connection successful" : "❌ Validation failed"}
                    </div>
                    <SimSteps result={simResult} />
                  </>
                )}
              </div>
            )}

            {writable && (
              <div>
                <Label>Test payload (JSON)</Label>
                <textarea value={testPayload} onChange={(e) => setTestPayload(e.target.value)} rows={8}
                  className="mt-1 w-full font-mono text-xs border border-slate-200 rounded p-2" data-testid="integration-test-payload" />
                <div className="flex gap-2 mt-2">
                  <Button variant="outline" size="sm" onClick={() => runTest(false)} data-testid="integration-test-dryrun">
                    <FlaskConical className="h-3.5 w-3.5 mr-1" /> Dry run
                  </Button>
                  <Button size="sm" className="bg-slate-900 hover:bg-slate-800" onClick={() => runTest(true)} data-testid="integration-test-issue">
                    Issue test proof
                  </Button>
                </div>
              </div>
            )}

            {testResult && (
              <pre className="text-xs bg-slate-50 p-3 overflow-auto max-h-64" data-testid="integration-test-result">{JSON.stringify(testResult, null, 2)}</pre>
            )}

            <RecentEventsTable events={events} />
          </div>
        </Panel>
      )}

      {editing && editForm && (
        <Dialog open onOpenChange={(o) => { if (!o) { setEditing(null); setEditForm(null); } }}>
          <DialogContent className="text-slate-900 bg-white max-w-lg" data-testid="integration-edit-dialog">
            <DialogHeader>
              <DialogTitle>Edit integration — {editing.name}</DialogTitle>
              <DialogDescription>Update settings or replace the signing secret. The current secret is never shown.</DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="text-xs text-slate-500">
                <Mono>/api/ingest/{editing.slug}</Mono> · auth <Mono>{editForm.auth_provider}</Mono>
                {editForm.signature_scheme ? <> · scheme <Mono>{editForm.signature_scheme}</Mono></> : null}
              </div>
              <div>
                <Label>Name</Label>
                <Input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="mt-1" data-testid="edit-name" />
              </div>
              <div>
                <Label>Description</Label>
                <Input value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="mt-1" data-testid="edit-description" />
              </div>
              <div>
                <Label className="flex items-center gap-1.5">
                  {editForm.has_credential ? "Replace secret" : "Set secret"}{" "}
                  {editForm.has_external_secret ? (
                    <span className="inline-flex items-center gap-1 text-emerald-600"><CheckCircle2 className="h-3.5 w-3.5" /> Secret stored (shown only once at creation)</span>
                  ) : editForm.has_hmac_secret ? (
                    <span className="inline-flex items-center gap-1 text-emerald-600"><CheckCircle2 className="h-3.5 w-3.5" /> PFP-generated secret stored (shown only once)</span>
                  ) : editForm.has_credential ? (
                    <span className="inline-flex items-center gap-1 text-emerald-600"><CheckCircle2 className="h-3.5 w-3.5" /> Credential stored (shown only once)</span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-amber-600"><XCircle className="h-3.5 w-3.5" /> No secret set</span>
                  )}
                </Label>
                <Input type="password" value={editForm.secret} onChange={(e) => setEditForm({ ...editForm, secret: e.target.value })}
                  placeholder={editForm.has_credential ? "Enter a new secret to replace the current one" : "Enter a signing secret"}
                  className="mt-1" data-testid="edit-secret" autoComplete="new-password" />
                <div className="text-xs text-slate-500 mt-1">
                  For security the current secret is never shown. Leave blank to keep it unchanged
                  {editForm.has_credential ? ", or use “Rotate secret” on the integration to generate a fresh one." : "."}
                </div>
              </div>
              {isHmacProvider(editForm.auth_provider) && (
                <div>
                  <Label>Signature scheme</Label>
                  <Select value={editForm.signature_scheme || "plain"} onValueChange={applyEditScheme}>
                    <SelectTrigger className="mt-1" data-testid="edit-sig-scheme"><SelectValue /></SelectTrigger>
                    <SelectContent>{SIGNATURE_SCHEMES.map((s) => <SelectItem key={s.v} value={s.v}>{s.label}</SelectItem>)}</SelectContent>
                  </Select>
                  <div className="text-xs text-slate-500 mt-1">
                    Picking a scheme pre-fills the recommended header + encoding below. For DocuSign, also set the HMAC secret above to match your DocuSign Connect secret.
                  </div>
                </div>
              )}
              <div>
                <Label>Auth config (JSON — review &amp; override)</Label>
                <textarea value={editForm.auth_config} onChange={(e) => setEditForm({ ...editForm, auth_config: e.target.value })}
                  rows={5} className="mt-1 w-full font-mono text-xs border border-slate-200 rounded p-2" data-testid="edit-auth-config" />
              </div>
              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input type="checkbox" checked={editForm.require_timestamp} data-testid="edit-require-timestamp"
                    onChange={(e) => setEditForm({ ...editForm, require_timestamp: e.target.checked })} /> Require timestamp
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input type="checkbox" checked={editForm.replay_protection} data-testid="edit-replay-protection"
                    onChange={(e) => setEditForm({ ...editForm, replay_protection: e.target.checked })} /> Replay protection
                </label>
                {editForm.require_timestamp && (
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    Tolerance (s)
                    <Input type="number" min={1} value={editForm.timestamp_tolerance_seconds}
                      onChange={(e) => setEditForm({ ...editForm, timestamp_tolerance_seconds: parseInt(e.target.value || "300", 10) })}
                      className="h-8 w-24" data-testid="edit-tolerance" />
                  </label>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => { setEditing(null); setEditForm(null); }} data-testid="edit-cancel">Cancel</Button>
              <Button className="bg-slate-900 hover:bg-slate-800" onClick={saveEdit} disabled={editBusy || !editForm.name.trim()} data-testid="edit-save">
                {editBusy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : null} Save changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {deleteTarget && (
        <Dialog open onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}>
          <DialogContent className="text-slate-900 bg-white max-w-md" data-testid="integration-delete-dialog">
            <DialogHeader>
              <DialogTitle>Delete integration</DialogTitle>
              <DialogDescription>Are you sure you want to delete this integration?</DialogDescription>
            </DialogHeader>
            <div className="space-y-3 text-sm">
              <div className="rounded-md bg-slate-50 border border-slate-200 p-3 space-y-1">
                <div><span className="text-slate-500">Integration: </span><span className="font-medium">{deleteTarget.name}</span></div>
                <div><span className="text-slate-500">Endpoint: </span><Mono>/api/ingest/{deleteTarget.slug}</Mono></div>
              </div>
              <div className="text-slate-600">
                <div className="mb-1">Deleting this integration will:</div>
                <ul className="list-disc pl-5 space-y-0.5">
                  <li>Stop accepting new inbound events</li>
                  <li>Preserve existing Proof Artifacts</li>
                  <li>Preserve audit logs</li>
                  <li>Not invalidate previously verified proofs</li>
                </ul>
              </div>
              <div className="text-xs text-red-600 font-medium">This action cannot be undone.</div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={deleteBusy} data-testid="delete-cancel">Cancel</Button>
              <Button className="bg-red-600 hover:bg-red-700 text-white" onClick={doDelete} disabled={deleteBusy} data-testid="delete-confirm">
                {deleteBusy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Trash2 className="h-4 w-4 mr-1.5" />} Delete integration
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
