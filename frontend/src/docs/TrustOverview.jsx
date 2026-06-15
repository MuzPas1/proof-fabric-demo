import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, ShieldCheck, Cloud, Cpu, Clock, ArrowRight } from "lucide-react";
import { API } from "./docsData";

const COLUMNS = [
  {
    id: "current", tag: "Current Capabilities", tagClass: "bg-emerald-50 text-emerald-700 ring-emerald-600/20", dot: "text-emerald-500",
    fallback: ["Proof Generation", "Proof Verification", "Ed25519 Signing", "Multi-Tenant Architecture"],
    field: "current_capability",
  },
  {
    id: "readiness", tag: "Architecture Readiness", tagClass: "bg-blue-50 text-blue-700 ring-blue-600/20", dot: "text-blue-500",
    fallback: ["Cloud KMS Ready (AWS / GCP / Azure)", "HSM Ready Architecture"],
    field: "architecture_readiness",
  },
  {
    id: "planned", tag: "Planned Enhancements", tagClass: "bg-amber-50 text-amber-700 ring-amber-600/20", dot: "text-amber-500",
    fallback: ["RFC-3161 External Time Anchoring"],
    field: "planned_enhancements",
  },
];

const DOC_LINKS = [
  { slug: "security-architecture", label: "Security Architecture" },
  { slug: "cryptographic-architecture", label: "Cryptographic Architecture" },
  { slug: "kms-migration", label: "KMS / HSM Migration Guide" },
  { slug: "verification-audit", label: "Verification Audit" },
  { slug: "threat-model", label: "Threat Model" },
];

export const TrustOverview = () => {
  const navigate = useNavigate();
  const [signing, setSigning] = useState(null);

  useEffect(() => {
    fetch(`${API}/developer`).then((r) => (r.ok ? r.json() : null)).then((d) => setSigning(d?.signing || null)).catch(() => {});
    window.scrollTo({ top: 0 });
  }, []);

  return (
    <div className="max-w-3xl" data-testid="docs-trust-overview">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900 font-['Space_Grotesk']">Trust &amp; Security Overview</h1>
      <p className="mt-4 text-[15px] leading-7 text-slate-600">
        PFP produces Ed25519-signed Proof Artifacts that anyone can verify independently with only the
        public key. Signing runs through a pluggable KMS abstraction, so enterprise key management can be
        enabled by configuration without any API or proof-format change. The matrix below distinguishes
        what is active today from what the architecture is ready for and what is planned.
      </p>

      <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
        {COLUMNS.map((col) => {
          const items = (signing && signing[col.field]) || col.fallback;
          return (
            <div key={col.id} data-testid={`trust-col-${col.id}`} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${col.tagClass}`}>{col.tag}</span>
              <ul className="mt-4 space-y-2.5">
                {items.map((it, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <CheckCircle2 className={`h-4 w-4 mt-0.5 shrink-0 ${col.dot}`} /> <span>{it}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      <p className="mt-5 text-xs text-slate-400">
        {signing
          ? `Active signing: ${signing.algorithm} · provider "${signing.active_provider}" (${signing.active_mode}). Config-only migration to: ${(signing.supported_providers || []).join(", ")}.`
          : "Active signing: Ed25519 software provider. Cloud KMS / HSM migration is configuration-only."}
        {" "}Readiness and planned items are not active capabilities unless listed under Current Capabilities.
      </p>

      <div className="mt-10">
        <div className="flex flex-wrap gap-2">
          {[{ icon: ShieldCheck, t: "Cryptographic Signing", s: "Active" }, { icon: Cloud, t: "Cloud KMS", s: "Ready" }, { icon: Cpu, t: "HSM Architecture", s: "Ready" }, { icon: Clock, t: "External Time Anchoring", s: "Planned" }].map((b) => {
            const Icon = b.icon;
            const cls = b.s === "Active" ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20" : b.s === "Ready" ? "bg-blue-50 text-blue-700 ring-blue-600/20" : "bg-amber-50 text-amber-700 ring-amber-600/20";
            return (
              <span key={b.t} className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ring-1 ring-inset ${cls}`}>
                <Icon className="h-4 w-4" /> {b.t}<span className="text-[11px] font-semibold uppercase opacity-70">{b.s}</span>
              </span>
            );
          })}
        </div>
      </div>

      <div className="mt-10">
        <h2 className="text-lg font-semibold text-slate-900 font-['Space_Grotesk']">Detailed security documentation</h2>
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {DOC_LINKS.map((d) => (
            <button
              key={d.slug}
              onClick={() => navigate(`/docs/${d.slug}`)}
              data-testid={`trust-doc-${d.slug}`}
              className="group flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm text-slate-700 hover:border-blue-300 hover:bg-blue-50/40 transition-colors"
            >
              {d.label}
              <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-blue-500 group-hover:translate-x-0.5 transition-all" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
