import React, { useEffect, useState } from "react";
import { api } from "../api";
import { PageHeader, Panel, Empty, Mono } from "../ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShieldCheck, ShieldX, Loader2 } from "lucide-react";

export default function Audit() {
  const [entries, setEntries] = useState(null);
  const [action, setAction] = useState("");
  const [chain, setChain] = useState(null);
  const [verifying, setVerifying] = useState(false);

  const load = (params = {}) => api.audit({ limit: 100, ...params }).then((d) => setEntries(d.entries || [])).catch(() => setEntries([]));
  useEffect(() => { load(); }, []);

  const verify = async () => {
    setVerifying(true);
    try { setChain(await api.auditVerify()); } finally { setVerifying(false); }
  };

  return (
    <div data-testid="audit-page">
      <PageHeader title="Audit Log" description="Immutable, hash-chained record of every control-plane action."
        actions={
          <Button onClick={verify} disabled={verifying} variant="outline" data-testid="verify-chain-btn">
            {verifying ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <ShieldCheck className="h-4 w-4 mr-1.5" />} Verify Chain
          </Button>
        } />

      {chain && (
        <div className={`mb-4 flex items-center gap-2 text-sm rounded-md border px-3 py-2 ${
          chain.intact ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-red-50 border-red-200 text-red-700"}`}
          data-testid="chain-result">
          {chain.intact ? <ShieldCheck className="h-4 w-4" /> : <ShieldX className="h-4 w-4" />}
          {chain.intact ? `Hash chain intact — ${chain.checked} entries verified` : `CHAIN BROKEN at ${chain.broken_at}`}
        </div>
      )}

      <div className="flex items-center gap-2 mb-3">
        <Input value={action} onChange={(e) => setAction(e.target.value)} placeholder="Filter by action (e.g. key.revoked)"
          className="w-72" data-testid="audit-filter-action" />
        <Button variant="outline" onClick={() => load(action ? { action } : {})} data-testid="audit-filter-apply">Apply</Button>
        {action && <Button variant="ghost" onClick={() => { setAction(""); load(); }}>Clear</Button>}
      </div>

      <Panel>
        {entries === null ? <Empty>Loading…</Empty> : entries.length === 0 ? <Empty>No audit entries</Empty> : (
          <table className="w-full text-sm" data-testid="audit-table">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                <th className="px-4 py-2.5 font-medium">Timestamp</th>
                <th className="px-4 py-2.5 font-medium">Action</th>
                <th className="px-4 py-2.5 font-medium">Actor</th>
                <th className="px-4 py-2.5 font-medium">Tenant</th>
                <th className="px-4 py-2.5 font-medium">Target</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map((e) => (
                <tr key={e.audit_id} data-testid={`audit-row-${e.audit_id}`}>
                  <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">{String(e.created_at).slice(0, 19).replace("T", " ")}</td>
                  <td className="px-4 py-2.5 font-medium text-slate-800">{e.action}</td>
                  <td className="px-4 py-2.5 text-slate-600">{e.actor}</td>
                  <td className="px-4 py-2.5"><Mono>{e.tenant_id}</Mono></td>
                  <td className="px-4 py-2.5"><Mono>{e.target ? String(e.target).slice(0, 20) : "—"}</Mono></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
