import React, { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { SectionHeader } from "./GetStarted";
import { PLATFORM_STATUS, API } from "./data";

export const PlatformStatus = () => {
  const [healthy, setHealthy] = useState(null); // null = loading

  useEffect(() => {
    let active = true;
    fetch(`${API}/health`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => active && setHealthy(d?.status === "healthy"))
      .catch(() => active && setHealthy(false));
    return () => { active = false; };
  }, []);

  return (
    <section id="status" className="scroll-mt-20 bg-slate-50 border-y border-slate-200" data-testid="dev-platform-status">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <SectionHeader
            eyebrow="Platform Status"
            title="Production-ready & operational"
            subtitle="The platform is live with multi-tenancy, a cryptographic verification engine, production APIs and full documentation."
          />
          <div
            data-testid="platform-live-pill"
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset ${
              healthy === false
                ? "bg-red-50 text-red-700 ring-red-600/20"
                : "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                healthy === false ? "bg-red-500" : "bg-emerald-500 animate-pulse"
              }`}
            />
            {healthy === null ? "Checking…" : healthy === false ? "Degraded" : "All systems operational"}
          </div>
        </div>

        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {PLATFORM_STATUS.map((s) => {
            const isLive = s.id === "live-platform" ? healthy !== false : true;
            return (
              <div
                key={s.id}
                data-testid={`status-${s.id}`}
                className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex items-start gap-3"
              >
                {isLive ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
                )}
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-slate-900">{s.label}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{s.detail}</div>
                </div>
                <span
                  className={`ml-auto inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
                    isLive
                      ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
                      : "bg-red-50 text-red-700 ring-red-600/20"
                  }`}
                >
                  {isLive ? "Live" : "Down"}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
