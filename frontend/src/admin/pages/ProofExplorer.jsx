import React, { useState } from "react";
import { api } from "../api";
import { PageHeader, Panel, Empty, Mono } from "../ui";
import TenantConnect from "../TenantConnect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Search } from "lucide-react";
import { toast } from "sonner";

export default function ProofExplorer() {
  const [conn, setConn] = useState(null); // { tenantId, apiKey }
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [query, setQuery] = useState("");
  const [detail, setDetail] = useState(null);
  const limit = 25;

  const load = async (apiKey, skipVal = 0) => {
    try {
      const d = await api.listFeas(apiKey, limit, skipVal);
      setItems(d.items || []); setTotal(d.total || 0); setSkip(skipVal);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to load FEAs"); setItems([]); }
  };

  const onConnect = (tenantId, apiKey) => { setConn({ tenantId, apiKey }); load(apiKey, 0); };

  const openDetail = async (id) => {
    try { setDetail(await api.getFea(conn.apiKey, id)); }
    catch (e) { toast.error(e?.response?.data?.detail || "Not found"); }
  };

  const filtered = (items || []).filter((i) =>
    !query || (i.transaction_id || "").toLowerCase().includes(query.toLowerCase()) || i.fea_id.includes(query));

  return (
    <div data-testid="proof-explorer-page">
      <PageHeader title="Proof Explorer" description="Browse issued FEAs for a tenant. Server-side tenant filtering enforces isolation." />
      <TenantConnect onConnect={onConnect} />

      {conn && (
        <>
          <div className="flex items-center justify-between mb-3">
            <div className="relative w-72">
              <Search className="h-4 w-4 absolute left-2.5 top-2.5 text-slate-400" />
              <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search transaction / FEA id"
                className="pl-8" data-testid="proof-search" />
            </div>
            <div className="text-xs text-slate-500">{total} total · tenant <Mono>{conn.tenantId}</Mono></div>
          </div>

          <Panel>
            {items === null ? <Empty>Loading…</Empty> : filtered.length === 0 ? <Empty>No FEAs for this tenant</Empty> : (
              <table className="w-full text-sm" data-testid="proofs-table">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                    <th className="px-4 py-2.5 font-medium">FEA ID</th>
                    <th className="px-4 py-2.5 font-medium">Transaction</th>
                    <th className="px-4 py-2.5 font-medium">Key ID</th>
                    <th className="px-4 py-2.5 font-medium">Created</th>
                    <th className="px-4 py-2.5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filtered.map((i) => (
                    <tr key={i.fea_id} data-testid={`proof-row-${i.fea_id}`}>
                      <td className="px-4 py-2.5"><Mono>{i.fea_id.slice(0, 18)}…</Mono></td>
                      <td className="px-4 py-2.5 text-slate-800">{i.transaction_id || "—"}</td>
                      <td className="px-4 py-2.5"><Mono>{i.public_key_id}</Mono></td>
                      <td className="px-4 py-2.5 text-slate-500">{String(i.created_at).slice(0, 19).replace("T", " ")}</td>
                      <td className="px-4 py-2.5 text-right">
                        <Button variant="outline" size="sm" className="h-7" onClick={() => openDetail(i.fea_id)}
                          data-testid={`view-proof-${i.fea_id}`}>View</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          {total > limit && (
            <div className="flex items-center justify-end gap-2 mt-3">
              <Button variant="outline" size="sm" disabled={skip === 0} onClick={() => load(conn.apiKey, Math.max(0, skip - limit))}>Prev</Button>
              <span className="text-xs text-slate-500">{skip + 1}–{Math.min(skip + limit, total)} of {total}</span>
              <Button variant="outline" size="sm" disabled={skip + limit >= total} onClick={() => load(conn.apiKey, skip + limit)}>Next</Button>
            </div>
          )}
        </>
      )}

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>FEA detail</DialogTitle>
            <DialogDescription>Signed Proof Artifact (read-only).</DialogDescription>
          </DialogHeader>
          {detail && (
            <pre className="text-xs bg-slate-50 border border-slate-200 rounded-md p-3 overflow-auto max-h-[60vh]"
              data-testid="proof-detail-json">{JSON.stringify(detail, null, 2)}</pre>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
