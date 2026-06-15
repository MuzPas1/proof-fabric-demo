import React, { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";
import { SectionHeader } from "./GetStarted";
import { PLATFORM_STATUS, API } from "./data";

export const PlatformStatus = () => {
  const [healthy, setHealthy] = useState(null); // null = loading
  const [docsUp, setDocsUp] = useState(null);

  useEffect(() => {
    let active = true;
    fetch(`${API}/health`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => active && setHealthy(d?.status === "healthy"))
      .catch(() => active && setHealthy(false));
    fetch(`${API}/openapi.json`)
      .then((r) => active && setDocsUp(r.ok))
      .catch(() => active && setDocsUp(false));
    return () => { active = false; };
  }, []);

  const resolve = (check) => {
    if (check === "static") return true;       // SDKs are statically hosted
    if (check === "docs") return docsUp;        // live OpenAPI fetch
    return healthy;                             // health-driven
  };

  const allUp = healthy !== false && docsUp !== false;

  return (
    <section id="status" className="scroll-mt-20 bg-slate-50 border-y border-slate-200" data-testid="dev-platform-status">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <SectionHeader
            eyebrow="Platform Status"
            title="Live & operational"
            subtitle="Real-time health of the API, documentation, SDKs, verification engine and demo environment."
          />
          <div
            data-testid="platform-live-pill"
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset ${
              !allUp ? "bg-red-50 text-red-700 ring-red-600/20" : "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${!allUp ? "bg-red-500" : "bg-emerald-500 animate-pulse"}`} />
            {healthy === null ? "Checking…" : !allUp ? "Degraded" : "All systems operational"}
          </div>
        </div>

        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {PLATFORM_STATUS.map((s) => {
            const state = resolve(s.check); // true | false | null
            const loading = state === null;
            return (
              <div
                key={s.id}
                data-testid={`status-${s.id}`}
                className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex items-start gap-3"
              >
                {loading ? (
                  <Loader2 className="h-5 w-5 text-slate-400 shrink-0 mt-0.5 animate-spin" />
                ) : state ? (
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
                    loading
                      ? "bg-slate-100 text-slate-500 ring-slate-300"
                      : state
                      ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
                      : "bg-red-50 text-red-700 ring-red-600/20"
                  }`}
                >
                  {loading ? "Checking" : state ? "Operational" : "Down"}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
