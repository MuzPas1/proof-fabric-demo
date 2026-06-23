import React, { useEffect, useState } from "react";
import { api } from "../api";
import { PageHeader, Panel, Empty, Mono } from "../ui";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, Loader2, Copy, Mail } from "lucide-react";
import { toast } from "sonner";

export default function Evaluations() {
  const [items, setItems] = useState(null);
  const [filter, setFilter] = useState("pending");
  const [busy, setBusy] = useState(null);
  const [approved, setApproved] = useState(null); // {evaluator_email, temporary_password, expires_at}

  const load = (status = filter) =>
    api.listEvaluations(status === "all" ? undefined : status)
      .then((d) => setItems(d.requests || []))
      .catch(() => setItems([]));

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const approve = async (id) => {
    setBusy(id);
    try {
      const res = await api.approveEvaluation(id, 30);
      setApproved(res);
      toast.success("Evaluator account provisioned", { position: "bottom-right" });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Approve failed");
    } finally { setBusy(null); }
  };

  const reject = async (id) => {
    setBusy(id);
    try {
      await api.rejectEvaluation(id, "Not approved");
      toast.success("Request rejected");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Reject failed");
    } finally { setBusy(null); }
  };

  const StatusPill = ({ s }) => {
    const m = {
      pending: "bg-amber-50 text-amber-700 border-amber-200",
      approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
      rejected: "bg-slate-100 text-slate-500 border-slate-200",
    };
    return <span className={`text-xs rounded-full border px-2 py-0.5 ${m[s] || m.rejected}`}>{s}</span>;
  };

  return (
    <div data-testid="evaluations-page">
      <PageHeader
        title="Enterprise Evaluations"
        description="Review Enterprise Evaluation Center requests and provision time-boxed evaluator access."
        actions={
          <div className="flex items-center gap-1.5">
            {["pending", "approved", "rejected", "all"].map((s) => (
              <Button key={s} size="sm" variant={filter === s ? "default" : "outline"}
                className={filter === s ? "" : "text-slate-700 border-slate-300 hover:bg-slate-100"}
                onClick={() => setFilter(s)} data-testid={`eval-filter-${s}`}>
                {s[0].toUpperCase() + s.slice(1)}
              </Button>
            ))}
          </div>
        }
      />

      {approved && (
        <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 p-4" data-testid="eval-credentials">
          <div className="flex items-center gap-2 text-emerald-800 text-sm font-medium">
            <CheckCircle2 className="h-4 w-4" /> Evaluator provisioned — share these one-time credentials securely
          </div>
          <div className="mt-2 text-sm text-slate-700 space-y-1">
            <div className="flex items-center gap-2"><Mail className="h-3.5 w-3.5 text-slate-400" /> <Mono>{approved.evaluator_email}</Mono></div>
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-xs uppercase tracking-wide">Temp password</span>
              <Mono>{approved.temporary_password}</Mono>
              <button onClick={() => { navigator.clipboard.writeText(approved.temporary_password); toast.success("Copied"); }}
                className="text-slate-400 hover:text-slate-700" data-testid="copy-temp-password"><Copy className="h-3.5 w-3.5" /></button>
            </div>
            <div className="text-xs text-slate-500">Access expires: {String(approved.expires_at).slice(0, 10)}</div>
          </div>
          <button onClick={() => setApproved(null)} className="mt-2 text-xs text-slate-500 underline">Dismiss</button>
        </div>
      )}

      <Panel>
        {items === null ? <Empty>Loading…</Empty> : items.length === 0 ? <Empty>No requests</Empty> : (
          <table className="w-full text-sm" data-testid="evaluations-table">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                <th className="px-4 py-2.5 font-medium">Requested</th>
                <th className="px-4 py-2.5 font-medium">Name / Company</th>
                <th className="px-4 py-2.5 font-medium">Email</th>
                <th className="px-4 py-2.5 font-medium">Industry</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((r) => (
                <tr key={r.request_id} data-testid={`eval-row-${r.request_id}`}>
                  <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">{String(r.created_at).slice(0, 10)}</td>
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-slate-800">{r.name}</div>
                    <div className="text-xs text-slate-500">{r.company}</div>
                  </td>
                  <td className="px-4 py-2.5 text-slate-600">{r.business_email}</td>
                  <td className="px-4 py-2.5 text-slate-600">{r.industry}</td>
                  <td className="px-4 py-2.5"><StatusPill s={r.status} /></td>
                  <td className="px-4 py-2.5 text-right">
                    {r.status === "pending" ? (
                      <div className="flex items-center gap-1.5 justify-end">
                        <Button size="sm" onClick={() => approve(r.request_id)} disabled={busy === r.request_id}
                          data-testid={`eval-approve-${r.request_id}`}>
                          {busy === r.request_id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <><CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Approve</>}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => reject(r.request_id)} disabled={busy === r.request_id}
                          data-testid={`eval-reject-${r.request_id}`}>
                          <XCircle className="h-3.5 w-3.5 mr-1" /> Reject
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400">{r.reviewed_by ? `by ${r.reviewed_by}` : "—"}</span>
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
