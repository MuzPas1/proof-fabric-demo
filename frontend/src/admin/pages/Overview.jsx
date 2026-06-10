import React, { useEffect, useState } from "react";
import { api, sumMetric } from "../api";
import { PageHeader, StatCard, Panel, Empty } from "../ui";
import { CheckCircle2, XCircle, ShieldCheck } from "lucide-react";

export default function Overview() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [tenants, keys, audit, chain, health, metrics] = await Promise.all([
          api.listTenants(), api.listApiKeys(), api.audit({ limit: 8 }),
          api.auditVerify(), api.health(), api.metricsRaw(),
        ]);
        setData({
          tenants: tenants.total ?? (tenants.tenants || []).length,
          activeKeys: (keys.keys || []).filter((k) => k.status === "active").length,
          totalKeys: (keys.keys || []).length,
          recent: audit.entries || [],
          chain,
          health,
          feasGenerated: sumMetric(metrics, "pfp_fea_generated_total"),
          verified: sumMetric(metrics, "pfp_fea_verified_total"),
          auditEvents: sumMetric(metrics, "pfp_audit_events_total"),
        });
      } catch (e) {
        setErr(e?.response?.data?.detail || "Failed to load overview");
      }
    })();
  }, []);

  if (err) return <div className="text-sm text-red-600">{err}</div>;
  if (!data) return <div className="text-sm text-slate-400">Loading…</div>;

  const healthChecks = data.health?.checks || {};

  return (
    <div data-testid="overview-page">
      <PageHeader title="Overview" description="Control-plane status across the platform." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Tenants" value={data.tenants} data-testid="stat-tenants" />
        <StatCard label="Active API Keys" value={data.activeKeys} sub={`${data.totalKeys} total`} />
        <StatCard label="FEAs Generated" value={Math.round(data.feasGenerated)} sub="from /metrics" />
        <StatCard label="Verifications" value={Math.round(data.verified)} sub="from /metrics" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel title="System Health" className="lg:col-span-1">
          <div className="p-4 space-y-2">
            <div className="flex items-center gap-2 mb-3">
              {data.health?.status === "healthy"
                ? <span className="inline-flex items-center gap-1 text-emerald-700 text-sm font-medium"><CheckCircle2 className="h-4 w-4" /> Healthy</span>
                : <span className="inline-flex items-center gap-1 text-amber-700 text-sm font-medium"><XCircle className="h-4 w-4" /> Degraded</span>}
            </div>
            {Object.entries(healthChecks).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between text-sm">
                <span className="text-slate-600">{k}</span>
                {v ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-red-600" />}
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Audit Chain Integrity" className="lg:col-span-1">
          <div className="p-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className={`h-5 w-5 ${data.chain?.intact ? "text-emerald-600" : "text-red-600"}`} />
              <span className="text-sm font-medium text-slate-900" data-testid="chain-status">
                {data.chain?.intact ? "Intact" : "BROKEN"}
              </span>
            </div>
            <div className="text-xs text-slate-500 mt-2">{data.chain?.checked} entries verified (SHA-256 hash chain)</div>
            <div className="text-xs text-slate-400 mt-3">Audit events recorded: {Math.round(data.auditEvents)}</div>
          </div>
        </Panel>

        <Panel title="Recent Activity" className="lg:col-span-1">
          {data.recent.length === 0 ? <Empty>No recent activity</Empty> : (
            <ul className="divide-y divide-slate-100">
              {data.recent.map((e) => (
                <li key={e.audit_id} className="px-4 py-2.5 text-sm">
                  <div className="font-medium text-slate-800">{e.action}</div>
                  <div className="text-xs text-slate-400">{e.actor} · {String(e.created_at).slice(0, 19).replace("T", " ")}</div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
