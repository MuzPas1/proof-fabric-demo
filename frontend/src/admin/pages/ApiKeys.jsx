import React, { useEffect, useState } from "react";
import { api, tenantKeys } from "../api";
import { PageHeader, Panel, StatusBadge, Empty, Mono } from "../ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Plus, Loader2, Copy, Check } from "lucide-react";
import { toast } from "sonner";

export default function ApiKeys() {
  const [keys, setKeys] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", tenant_id: "", customer_id: "", expires_in_days: "" });
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = () => api.listApiKeys().then((d) => setKeys(d.keys || [])).catch(() => setKeys([]));
  useEffect(() => {
    load();
    api.listTenants().then((d) => setTenants(d.tenants || [])).catch(() => {});
  }, []);

  const create = async () => {
    setBusy(true);
    try {
      const body = { name: form.name.trim() };
      if (form.tenant_id) body.tenant_id = form.tenant_id;
      if (form.customer_id) body.customer_id = form.customer_id.trim();
      if (form.expires_in_days) body.expires_in_days = parseInt(form.expires_in_days, 10);
      const res = await api.createApiKey(body);
      tenantKeys.set(res.tenant_id, res.api_key); // remember raw key for data-plane modules
      setCreated(res);
      toast.success("API key created");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to create key");
    } finally { setBusy(false); }
  };

  const revoke = async (keyId) => {
    try {
      await api.revokeApiKey(keyId);
      toast.success("API key revoked");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to revoke"); }
  };

  const closeDialog = () => {
    setOpen(false); setCreated(null); setCopied(false);
    setForm({ name: "", tenant_id: "", customer_id: "", expires_in_days: "" });
  };

  return (
    <div data-testid="api-keys-page">
      <PageHeader title="API Keys" description="Data-plane credentials. Tenant-scoped, hashed at rest (shown once)."
        actions={
          <Dialog open={open} onOpenChange={(o) => (o ? setOpen(true) : closeDialog())}>
            <DialogTrigger asChild>
              <Button className="bg-slate-900 hover:bg-slate-800" data-testid="create-key-open">
                <Plus className="h-4 w-4 mr-1.5" /> New API Key
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>{created ? "API key created" : "Create API key"}</DialogTitle>
                <DialogDescription>
                  {created ? "Copy the key now — it is shown only once." : "Tenant-scoped data-plane credential."}
                </DialogDescription>
              </DialogHeader>
              {created ? (
                <div className="py-2 space-y-3">
                  <p className="text-sm text-slate-600">Copy this key now — it will not be shown again.</p>
                  <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-md p-2">
                    <code className="text-xs text-slate-800 break-all flex-1" data-testid="created-key-value">{created.api_key}</code>
                    <button onClick={() => { navigator.clipboard.writeText(created.api_key); setCopied(true); }}
                      className="text-slate-500 hover:text-slate-900">
                      {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
                    </button>
                  </div>
                  <div className="text-xs text-slate-500">
                    Tenant: <Mono>{created.tenant_id}</Mono> · scopes: {created.scopes.join(", ")}
                    {created.expires_at && <> · expires {String(created.expires_at).slice(0, 10)}</>}
                  </div>
                  <DialogFooter><Button onClick={closeDialog} variant="outline" data-testid="created-key-done">Done</Button></DialogFooter>
                </div>
              ) : (
                <div className="space-y-3 py-2">
                  <div><Label>Name</Label>
                    <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="acme-prod" className="mt-1" data-testid="create-key-name" /></div>
                  <div><Label>Tenant</Label>
                    <Select value={form.tenant_id} onValueChange={(v) => setForm({ ...form, tenant_id: v })}>
                      <SelectTrigger className="mt-1" data-testid="create-key-tenant"><SelectValue placeholder="Select tenant" /></SelectTrigger>
                      <SelectContent>
                        {tenants.map((t) => <SelectItem key={t.tenant_id} value={t.tenant_id}>{t.name} ({t.tenant_id})</SelectItem>)}
                      </SelectContent>
                    </Select></div>
                  <div className="grid grid-cols-2 gap-3">
                    <div><Label>Customer ID</Label>
                      <Input value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
                        placeholder="optional" className="mt-1" /></div>
                    <div><Label>Expires (days)</Label>
                      <Input type="number" value={form.expires_in_days} onChange={(e) => setForm({ ...form, expires_in_days: e.target.value })}
                        placeholder="optional" className="mt-1" /></div>
                  </div>
                  <DialogFooter>
                    <Button onClick={create} disabled={busy || !form.name.trim()}
                      className="bg-slate-900 hover:bg-slate-800" data-testid="create-key-submit">
                      {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Create
                    </Button>
                  </DialogFooter>
                </div>
              )}
            </DialogContent>
          </Dialog>
        } />

      <Panel>
        {keys === null ? <Empty>Loading…</Empty> : keys.length === 0 ? <Empty>No API keys</Empty> : (
          <table className="w-full text-sm" data-testid="api-keys-table">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Tenant</th>
                <th className="px-4 py-2.5 font-medium">Prefix</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Expires</th>
                <th className="px-4 py-2.5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {keys.map((k) => (
                <tr key={k.key_id} data-testid={`key-row-${k.key_id}`}>
                  <td className="px-4 py-2.5 text-slate-800">{k.name}</td>
                  <td className="px-4 py-2.5"><Mono>{k.tenant_id}</Mono></td>
                  <td className="px-4 py-2.5"><Mono>{k.prefix}…</Mono></td>
                  <td className="px-4 py-2.5"><StatusBadge status={k.status} /></td>
                  <td className="px-4 py-2.5 text-slate-500">{k.expires_at ? String(k.expires_at).slice(0, 10) : "—"}</td>
                  <td className="px-4 py-2.5 text-right">
                    {k.status === "active" && (
                      <Button variant="outline" size="sm" onClick={() => revoke(k.key_id)}
                        className="text-red-600 border-red-200 hover:bg-red-50 h-7"
                        data-testid={`revoke-key-${k.key_id}`}>Revoke</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
