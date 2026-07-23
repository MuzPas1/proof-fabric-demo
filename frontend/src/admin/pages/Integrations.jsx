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
import { Plus, Trash2, Power, PowerOff, RefreshCw, FlaskConical, Copy, Loader2, Activity, Pencil, ShieldCheck, Bug, CheckCircle2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";

const ADAPTERS = ["generic"];
const AUTH_PROVIDERS = ["hmac_sha256", "hmac_sha1", "api_key", "bearer", "basic", "jwt", "oauth2", "mtls", "custom", "none"];
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

// "Debug last rejection" — surfaces the most recent REJECTED inbound event's
// diagnostic so operators can self-diagnose provider auth failures (e.g.
// DocuSign) without server-log access. Non-sensitive: header NAMES only, never
// secrets or signature values.
function DebugLastRejection({ events }) {
  if (events === null) return null;
  const rej = events.find((e) => e.status === "rejected");
  if (!rej) {
    return (
      <div className="rounded-md border border-emerald-200 bg-emerald-50/60 px-3 py-2.5 flex items-center gap-2" data-testid="debug-last-rejection-none">
        <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
        <span className="text-xs text-emerald-800">No recent rejections — the latest inbound events authenticated and normalized successfully.</span>
      </div>
    );
  }
  const diag = parseDiagnostic(rej.error);
  const headerVal = diag?.fields?.header;
  const headerMissing = headerVal === "missing";
  const copy = () =>
    navigator.clipboard.writeText(rej.error || "").then(() => toast.success("Diagnostic copied")).catch(() => toast.error("Copy failed"));
  return (
    <div className="rounded-md border border-red-200 bg-red-50/50 p-3 space-y-2.5" data-testid="debug-last-rejection">
      <div className="flex items-center gap-2">
        <Bug className="h-4 w-4 text-red-600 shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-wide text-red-700">Debug last rejection</span>
        {diag?.category && (
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-red-100 text-red-700 uppercase">{diag.category}</span>
        )}
        <span className="ml-auto text-[11px] text-slate-500">{rej.received_at?.slice(0, 19)?.replace("T", " ")} UTC</span>
        <button type="button" onClick={copy} className="text-slate-400 hover:text-slate-700" title="Copy raw diagnostic" data-testid="debug-copy-btn">
          <Copy className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="text-xs text-slate-800" data-testid="debug-message">{diag?.message || rej.error}</div>
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
            {diag.headersSeen.length === 0 ? (
              <span className="text-slate-400">none</span>
            ) : (
              diag.headersSeen.map((h, i) => (
                <code key={i} className={`px-1.5 py-0.5 rounded font-mono ${/sign/i.test(h) ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{h}</code>
              ))
            )}
          </div>
        </div>
      )}
      {headerMissing && (
        <div className="text-[11px] text-slate-600 border-t border-red-200/60 pt-2">
          The provider did not send the configured signature header. Compare the received headers above with your provider's spec and adjust the integration's <span className="font-medium">signature scheme / header</span>. If no signature-like header appears at all, an upstream proxy/gateway may be stripping it.
        </div>
      )}
    </div>
  );
}


export default function Integrations() {
  const { user } = useAuth();
  const writable = canWrite(user?.role);
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", adapter: "generic", auth_provider: "hmac_sha256", default_currency: "USD", auth_config: "", secret: "", sig_scheme: "plain", provider: "generic", requires_secret: false, secret_label: "Provider signing secret", secret_hint: "", require_timestamp: false, timestamp_tolerance_seconds: 300, replay_protection: false });
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
    setForm((f) => ({
      ...f,
      provider: id,
      auth_provider: p.auth_provider || "hmac_sha256",
      auth_config: cfg,
      requires_secret: !!p.requires_secret,
      secret_label: p.secret_label || "Provider signing secret",
      secret_hint: p.secret_hint || "",
      require_timestamp: !!p.require_timestamp,
      timestamp_tolerance_seconds: p.timestamp_tolerance_seconds || 300,
      replay_protection: !!p.replay_protection,
      secret: "",
      sig_scheme: "plain",
    }));
  };
  const activePreset = presets.find((x) => x.id === form.provider);

  const create = async () => {
    setBusy(true); setCredential(null);
    let auth_config = {};
    if (form.auth_config.trim()) {
      try { auth_config = JSON.parse(form.auth_config); }
      catch { toast.error("Advanced auth config is not valid JSON"); setBusy(false); return; }
    }
    if (HMAC_PROVIDERS.includes(form.auth_provider) && form.sig_scheme && form.sig_scheme !== "plain") {
      auth_config.signature_scheme = form.sig_scheme;
    }
    const body = {
      name: form.name, slug: form.slug, adapter: form.adapter, auth_provider: form.auth_provider,
      default_currency: form.default_currency, auth_config,
      require_timestamp: form.require_timestamp, replay_protection: form.replay_protection,
      timestamp_tolerance_seconds: form.timestamp_tolerance_seconds || 300,
    };
    if (form.secret.trim()) body.secret = form.secret.trim();
    try {
      const r = await api.createIntegration(body);
      if (r.credential) setCredential({ slug: r.slug, credential: r.credential, url: r.inbound_url });
      toast.success(r.credential ? "Integration created" : `Integration created (${form.provider !== "generic" ? form.provider : "external"} auth)`);
      setForm({ name: "", slug: "", adapter: "generic", auth_provider: "hmac_sha256", default_currency: "USD", auth_config: "", secret: "", sig_scheme: "plain", provider: "generic", requires_secret: false, secret_label: "Provider signing secret", secret_hint: "", require_timestamp: false, timestamp_tolerance_seconds: 300, replay_protection: false });
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

  const remove = async (it) => {
    try { await api.deleteIntegration(it.integration_id); toast.success("Deleted"); if (selected?.integration_id === it.integration_id) setSelected(null); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Delete failed"); }
  };

  const loadStatsEvents = async (it) => {
    try { setStats(await api.integrationStats(it.integration_id)); } catch { /* noop */ }
    try { const e = await api.integrationEvents(it.integration_id); setEvents(e.events || []); } catch { setEvents([]); }
  };

  const openDetails = async (it) => {
    setSelected(it); setStats(null); setEvents(null); setTestResult(null);
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
        <Panel title="Credential — shown once" className="mb-4">
          <div className="p-4 space-y-2" data-testid="integration-credential">
            <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              Store this credential now — it cannot be retrieved again.
            </div>
            <div className="flex items-center gap-2">
              <Mono>{credential.credential}</Mono>
              <Button size="sm" variant="outline" className="h-7" onClick={() => copy(credential.credential)}><Copy className="h-3.5 w-3.5" /></Button>
            </div>
            <div className="text-xs text-slate-500">Inbound URL: <Mono>{credential.url}</Mono></div>
          </div>
        </Panel>
      )}

      {writable && (
        <Panel title="New integration" className="mb-4">
          <div className="p-4 grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <Label>Provider preset</Label>
              <Select value={form.provider} onValueChange={applyPreset}>
                <SelectTrigger className="mt-1" data-testid="integration-provider"><SelectValue placeholder="Select a provider" /></SelectTrigger>
                <SelectContent>{presets.map((p) => <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>)}</SelectContent>
              </Select>
              {activePreset && form.provider !== "generic" && (
                <div className="mt-1.5 text-xs text-slate-500" data-testid="integration-provider-note">
                  {activePreset.description}
                  {activePreset.docs_url && (
                    <> · <a href={activePreset.docs_url} target="_blank" rel="noreferrer" className="text-blue-600 underline">Vendor signing spec</a></>
                  )}
                </div>
              )}
            </div>
            <div>
              <Label>Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Acme ERP" className="mt-1" data-testid="integration-name" />
            </div>
            <div>
              <Label>Slug (used in the inbound URL)</Label>
              <Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })}
                placeholder="acme-erp" className="mt-1" data-testid="integration-slug" />
            </div>
            <div>
              <Label>Adapter</Label>
              <Select value={form.adapter} onValueChange={(v) => setForm({ ...form, adapter: v })}>
                <SelectTrigger className="mt-1" data-testid="integration-adapter"><SelectValue /></SelectTrigger>
                <SelectContent>{ADAPTERS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            {form.provider === "generic" ? (<>
            <div>
              <Label>Auth provider</Label>
              <Select value={form.auth_provider} onValueChange={(v) => setForm({ ...form, auth_provider: v })}>
                <SelectTrigger className="mt-1" data-testid="integration-auth"><SelectValue /></SelectTrigger>
                <SelectContent>{AUTH_PROVIDERS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            {HMAC_PROVIDERS.includes(form.auth_provider) && (
              <>
                <div>
                  <Label>Signature scheme</Label>
                  <Select value={form.sig_scheme} onValueChange={(v) => setForm({ ...form, sig_scheme: v })}>
                    <SelectTrigger className="mt-1" data-testid="integration-sig-scheme"><SelectValue /></SelectTrigger>
                    <SelectContent>{SIGNATURE_SCHEMES.map((s) => <SelectItem key={s.v} value={s.v}>{s.label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                {form.sig_scheme !== "plain" && (
                  <div>
                    <Label>Provider signing secret</Label>
                    <Input type="password" value={form.secret} onChange={(e) => setForm({ ...form, secret: e.target.value })}
                      placeholder="e.g. Cashfree PG secret key" className="mt-1" data-testid="integration-hmac-secret" />
                  </div>
                )}
              </>
            )}
            {EXTERNAL_PROVIDERS.includes(form.auth_provider) && (
              <div className="col-span-2 grid grid-cols-2 gap-3">
                <div>
                  <Label>Advanced auth config (JSON)</Label>
                  <textarea value={form.auth_config} onChange={(e) => setForm({ ...form, auth_config: e.target.value })}
                    rows={4} placeholder='{"jwks_url":"https://idp/.well-known/jwks.json","issuer":"...","audience":"..."}'
                    className="mt-1 w-full font-mono text-xs border border-slate-200 rounded p-2" data-testid="integration-auth-config" />
                </div>
                <div>
                  <Label>Provider secret (optional — JWT HS / OAuth client secret)</Label>
                  <Input type="password" value={form.secret} onChange={(e) => setForm({ ...form, secret: e.target.value })}
                    placeholder="stored redacted" className="mt-1" data-testid="integration-secret" />
                </div>
              </div>
            )}
            </>) : (<>
            <div>
              <Label>Auth provider (recommended)</Label>
              <Input value={form.auth_provider} disabled className="mt-1 font-mono text-xs" data-testid="integration-auth-readonly" />
            </div>
            {form.requires_secret && (
              <div>
                <Label>{form.secret_label}</Label>
                <Input type="password" value={form.secret} onChange={(e) => setForm({ ...form, secret: e.target.value })}
                  placeholder={form.secret_hint || "stored redacted"} className="mt-1" data-testid="integration-hmac-secret" />
              </div>
            )}
            <div className="col-span-2">
              <Label>Recommended auth config (JSON — review &amp; override)</Label>
              <textarea value={form.auth_config} onChange={(e) => setForm({ ...form, auth_config: e.target.value })}
                rows={5} className="mt-1 w-full font-mono text-xs border border-slate-200 rounded p-2" data-testid="integration-auth-config" />
            </div>
            </>)}
            <div className="col-span-2 flex items-center gap-6">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={form.require_timestamp} data-testid="integration-require-timestamp"
                  onChange={(e) => setForm({ ...form, require_timestamp: e.target.checked })} /> Require timestamp
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
            <div className="col-span-2 flex justify-end">
              <Button onClick={create} disabled={busy || !form.name.trim() || !form.slug.trim()}
                className="bg-slate-900 hover:bg-slate-800" data-testid="integration-create">
                {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Plus className="h-4 w-4 mr-1.5" />} Create integration
              </Button>
            </div>
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

            <DebugLastRejection events={events} />

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

            <div>
              <div className="text-xs text-slate-500 mb-1">Recent events</div>
              {events === null ? <Empty>Loading…</Empty> : events.length === 0 ? <Empty>No events yet</Empty> : (
                <table className="w-full text-xs" data-testid="integration-events-table">
                  <thead><tr className="text-left text-slate-400 border-b border-slate-200">
                    <th className="py-1.5">When</th><th>Type</th><th>External ID</th><th>Status</th><th>Proof (FEA ID)</th>
                  </tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {events.map((e) => (
                      <tr key={e.event_log_id}>
                        <td className="py-1.5">{e.received_at?.slice(0, 19)}</td>
                        <td>{e.event_type || "—"}</td>
                        <td>{e.external_id || "—"}</td>
                        <td>{e.status}</td>
                        <td className="py-1.5"><ProofCell event={e} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
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
                <Label>
                  Replace external secret{" "}
                  <span className={editForm.has_external_secret ? "text-emerald-600" : "text-amber-600"}>
                    {editForm.has_external_secret ? "(a secret is currently set)" : (editForm.has_hmac_secret ? "(uses a PFP-minted secret)" : "(no secret set)")}
                  </span>
                </Label>
                <Input type="password" value={editForm.secret} onChange={(e) => setEditForm({ ...editForm, secret: e.target.value })}
                  placeholder={editForm.has_external_secret ? "Enter new secret to replace the current one" : "Enter external signing secret"}
                  className="mt-1" data-testid="edit-secret" autoComplete="new-password" />
                <div className="text-xs text-slate-500 mt-1">
                  For security the current secret is never shown. Leave blank to keep it unchanged.
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
    </div>
  );
}
