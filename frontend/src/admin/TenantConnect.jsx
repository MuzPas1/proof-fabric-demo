import React, { useEffect, useState } from "react";
import { api, tenantKeys } from "./api";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Mono } from "./ui";
import { Link2, ShieldQuestion } from "lucide-react";
import { toast } from "sonner";

/**
 * Data-plane connection. The control plane (JWT) cannot read tenant FEAs or
 * webhooks — those require the tenant's API key. This binds a tenant's key
 * (created via the dashboard, pasted, or the dev sandbox key) for the session.
 * Because the key is tenant-scoped server-side, this enforces tenant isolation.
 */
export default function TenantConnect({ onConnect }) {
  const [tenants, setTenants] = useState([]);
  const [tid, setTid] = useState("");
  const [pasteKey, setPasteKey] = useState("");

  useEffect(() => { api.listTenants().then((d) => setTenants(d.tenants || [])).catch(() => {}); }, []);

  const connect = (tenantId, apiKey) => {
    tenantKeys.set(tenantId, apiKey);
    onConnect(tenantId, apiKey);
    toast.success(`Connected to tenant ${tenantId}`);
  };

  const onSelect = (v) => {
    setTid(v);
    const existing = tenantKeys.get(v);
    if (existing) connect(v, existing);
  };

  const useSandbox = async () => {
    try {
      const cfg = await api.config();
      if (cfg.test_api_key) connect("default", cfg.test_api_key);
      else toast.error("Sandbox key not available (production mode)");
    } catch { toast.error("Could not load sandbox key"); }
  };

  const known = tid && tenantKeys.get(tid);

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4" data-testid="tenant-connect">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-900 mb-3">
        <Link2 className="h-4 w-4 text-slate-500" /> Data-plane connection (tenant API key)
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-64">
          <Select value={tid} onValueChange={onSelect}>
            <SelectTrigger data-testid="connect-tenant-select"><SelectValue placeholder="Select tenant" /></SelectTrigger>
            <SelectContent>
              {tenants.map((t) => (
                <SelectItem key={t.tenant_id} value={t.tenant_id}>
                  {t.name} ({t.tenant_id}){tenantKeys.get(t.tenant_id) ? " ✓" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {tid && !known && (
          <>
            <Input value={pasteKey} onChange={(e) => setPasteKey(e.target.value)}
              placeholder="Paste tenant API key (pfp_live_… / pfp_sandbox_…)"
              className="w-80" data-testid="connect-paste-key" />
            <Button variant="outline" onClick={() => pasteKey && connect(tid, pasteKey.trim())}
              data-testid="connect-use-key">Connect</Button>
          </>
        )}
        <Button variant="outline" onClick={useSandbox} data-testid="connect-sandbox">Use sandbox (default)</Button>
      </div>
      {known ? (
        <div className="text-xs text-emerald-700 mt-2">Connected to <Mono>{tid}</Mono> — data below is scoped to this tenant only.</div>
      ) : (
        <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-2">
          <ShieldQuestion className="h-3.5 w-3.5" /> No key bound. Create one in API Keys, paste one, or use the dev sandbox.
        </div>
      )}
    </div>
  );
}
