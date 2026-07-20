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
import { Plus, Trash2, Power, PowerOff, RefreshCw, FlaskConical, Copy, Loader2, Activity } from "lucide-react";
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
];

export default function Integrations() {
  const { user } = useAuth();
  const writable = canWrite(user?.role);
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", adapter: "generic", auth_provider: "hmac_sha256", default_currency: "USD", auth_config: "", secret: "", sig_scheme: "plain", require_timestamp: false, replay_protection: false });
  const [credential, setCredential] = useState(null);
  const [selected, setSelected] = useState(null);
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState(null);
  const [testPayload, setTestPayload] = useState(
    `{\n  "type": "invoice.created",\n  "id": "INV-${Date.now()}",\n  "timestamp": "2026-06-10T12:00:00Z",\n  "actor": "system-a",\n  "subject": "account-42",\n  "amount": 25000,\n  "currency": "USD"\n}`
  );
  const [testResult, setTestResult] = useState(null);

  const load = async () => {
    try { const d = await api.listIntegrations(); setItems(d.integrations || []); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed to load integrations"); setItems([]); }
  };
  useEffect(() => { load(); }, []);

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
    };
    if (form.secret.trim()) body.secret = form.secret.trim();
    try {
      const r = await api.createIntegration(body);
      if (r.credential) setCredential({ slug: r.slug, credential: r.credential, url: r.inbound_url });
      toast.success(r.credential ? "Integration created" : `Integration created (external ${form.auth_provider} auth)`);
      setForm({ name: "", slug: "", adapter: "generic", auth_provider: "hmac_sha256", default_currency: "USD", auth_config: "", secret: "", sig_scheme: "plain", require_timestamp: false, replay_protection: false });
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
            <div className="col-span-2 flex items-center gap-6">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={form.require_timestamp} data-testid="integration-require-timestamp"
                  onChange={(e) => setForm({ ...form, require_timestamp: e.target.checked })} /> Require timestamp
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={form.replay_protection} data-testid="integration-replay-protection"
                  onChange={(e) => setForm({ ...form, replay_protection: e.target.checked })} /> Replay protection
              </label>
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
                    <th className="py-1.5">When</th><th>Type</th><th>External ID</th><th>Status</th><th>Proof</th>
                  </tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {events.map((e) => (
                      <tr key={e.event_log_id}>
                        <td className="py-1.5">{e.received_at?.slice(0, 19)}</td>
                        <td>{e.event_type || "—"}</td>
                        <td>{e.external_id || "—"}</td>
                        <td>{e.status}</td>
                        <td><Mono>{e.fea_id ? e.fea_id.slice(0, 8) : (e.error || "—")}</Mono></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}
