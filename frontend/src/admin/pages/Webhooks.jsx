import React, { useState } from "react";
import { api } from "../api";
import { PageHeader, Panel, StatusBadge, Empty, Mono } from "../ui";
import TenantConnect from "../TenantConnect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Send, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Webhooks() {
  const [conn, setConn] = useState(null);
  const [subs, setSubs] = useState(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastTest, setLastTest] = useState(null);

  const load = async (apiKey) => {
    try { const d = await api.listWebhooks(apiKey); setSubs(d.subscriptions || []); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed to load webhooks"); setSubs([]); }
  };
  const onConnect = (tenantId, apiKey) => { setConn({ tenantId, apiKey }); load(apiKey); };

  const create = async () => {
    setBusy(true);
    try {
      await api.subscribeWebhook(conn.apiKey, url.trim(), ["fea.generated"]);
      toast.success("Webhook created"); setUrl(""); load(conn.apiKey);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to create"); }
    finally { setBusy(false); }
  };

  const test = async (id) => {
    try { const r = await api.testWebhook(conn.apiKey, id); setLastTest(r); toast.success("Test sent"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Test failed"); }
  };

  const del = async (id) => {
    try { await api.deleteWebhook(conn.apiKey, id); toast.success("Deleted"); load(conn.apiKey); }
    catch (e) { toast.error(e?.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div data-testid="webhooks-page">
      <PageHeader title="Webhooks" description="Per-tenant event subscriptions with HMAC-signed delivery (fea.generated)." />
      <TenantConnect onConnect={onConnect} />

      {conn && (
        <>
          <Panel title="New subscription" className="mb-4">
            <div className="p-4 flex items-end gap-3">
              <div className="flex-1">
                <Label>Callback URL</Label>
                <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-system.com/pfp-hook"
                  className="mt-1" data-testid="webhook-url" />
              </div>
              <Button onClick={create} disabled={busy || !url.trim()} className="bg-slate-900 hover:bg-slate-800"
                data-testid="webhook-create">
                {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Plus className="h-4 w-4 mr-1.5" />} Subscribe
              </Button>
            </div>
          </Panel>

          <Panel>
            {subs === null ? <Empty>Loading…</Empty> : subs.length === 0 ? <Empty>No webhooks for this tenant</Empty> : (
              <table className="w-full text-sm" data-testid="webhooks-table">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                    <th className="px-4 py-2.5 font-medium">URL</th>
                    <th className="px-4 py-2.5 font-medium">Events</th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                    <th className="px-4 py-2.5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {subs.map((w) => (
                    <tr key={w.webhook_id} data-testid={`webhook-row-${w.webhook_id}`}>
                      <td className="px-4 py-2.5 text-slate-800 break-all">{w.url}</td>
                      <td className="px-4 py-2.5"><Mono>{(w.events || []).join(", ")}</Mono></td>
                      <td className="px-4 py-2.5"><StatusBadge status={w.status} /></td>
                      <td className="px-4 py-2.5 text-right space-x-2">
                        <Button variant="outline" size="sm" className="h-7" onClick={() => test(w.webhook_id)}
                          data-testid={`webhook-test-${w.webhook_id}`}><Send className="h-3.5 w-3.5 mr-1" />Test</Button>
                        <Button variant="outline" size="sm" className="h-7 text-red-600 border-red-200 hover:bg-red-50"
                          onClick={() => del(w.webhook_id)} data-testid={`webhook-delete-${w.webhook_id}`}>
                          <Trash2 className="h-3.5 w-3.5" /></Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          {lastTest && (
            <Panel title="Last test delivery" className="mt-4">
              <pre className="text-xs bg-slate-50 p-3 overflow-auto" data-testid="webhook-test-result">{JSON.stringify(lastTest, null, 2)}</pre>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
