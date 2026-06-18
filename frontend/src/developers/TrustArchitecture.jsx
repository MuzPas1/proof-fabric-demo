import React, { useEffect, useState } from "react";
import { CheckCircle2, ShieldCheck, Cloud, Cpu, Clock, KeyRound } from "lucide-react";
import { SectionHeader } from "./GetStarted";
import { API } from "./data";

const COLUMNS = [
  {
    id: "current",
    tag: "Current Capability",
    tagClass: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    dotClass: "text-emerald-500",
    fallback: [
      "Deterministic canonicalization (PFP-JCS) + signing",
      "Crypto agility: Ed25519 (default), ES256, ES256K — selectable per request/tenant",
      "Independent, offline verification with the public key (any suite)",
      "Federated key registry: customer/partner keys (raw/JWK/PEM) with proof-of-possession",
      "Bring-Your-Own-Signing: local / remote / cloud-KMS signers per tenant",
      "Multi-tenant key isolation; persistent key registry & rotation",
    ],
    field: "current_capability",
  },
  {
    id: "readiness",
    tag: "Architecture Readiness",
    tagClass: "bg-blue-50 text-blue-700 ring-blue-600/20",
    dotClass: "text-blue-500",
    fallback: [
      "Cloud KMS ready — AWS / GCP / Azure (config-only switch)",
      "Native HSM / cloud-KMS signing path (private key never leaves the boundary) — config-gated",
    ],
    field: "architecture_readiness",
  },
  {
    id: "planned",
    tag: "Planned Enhancement",
    tagClass: "bg-amber-50 text-amber-700 ring-amber-600/20",
    dotClass: "text-amber-500",
    fallback: [
      "Native HSM signing — private key never leaves the HSM/KMS boundary",
      "External time anchoring (RFC-3161 / transparency log)",
    ],
    field: "planned_enhancements",
  },
];

const BADGES = [
  { icon: ShieldCheck, label: "Crypto Agility", status: "Active" },
  { icon: KeyRound, label: "Federated Key Registry", status: "Active" },
  { icon: Cpu, label: "Bring-Your-Own-Signing", status: "Active" },
  { icon: Cloud, label: "Cloud KMS", status: "Ready" },
  { icon: Clock, label: "External Time Anchoring", status: "Planned" },
];

const badgeClass = (status) =>
  status === "Active"
    ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
    : status === "Ready"
    ? "bg-blue-50 text-blue-700 ring-blue-600/20"
    : "bg-amber-50 text-amber-700 ring-amber-600/20";

export const TrustArchitecture = () => {
  const [signing, setSigning] = useState(null);

  useEffect(() => {
    let active = true;
    fetch(`${API}/developer`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => active && setSigning(d?.signing || null))
      .catch(() => {});
    return () => { active = false; };
  }, []);

  return (
    <section id="trust" className="scroll-mt-20 bg-slate-50 border-y border-slate-200" data-testid="dev-trust-architecture">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
        <SectionHeader
          eyebrow="Trust & Security"
          title="Cryptographic signing architecture"
          subtitle="Proofs are signed with selectable suites — Ed25519 (default), ES256 (secp256r1) and ES256K (secp256k1). A federated key registry and Bring-Your-Own-Signing let partners use their own keys/signers, while independent verification stays signer-agnostic — all without API or proof-format changes."
        />

        {/* Capability badges */}
        <div className="mt-8 flex flex-wrap gap-2.5" data-testid="trust-badges">
          {BADGES.map((b) => {
            const Icon = b.icon;
            return (
              <span
                key={b.label}
                data-testid={`trust-badge-${b.label.toLowerCase().replace(/\s+/g, "-")}`}
                className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ring-1 ring-inset ${badgeClass(b.status)}`}
              >
                <Icon className="h-4 w-4" /> {b.label}
                <span className="text-[11px] font-semibold uppercase tracking-wide opacity-70">{b.status}</span>
              </span>
            );
          })}
        </div>

        {/* Three honest columns */}
        <div className="mt-10 grid grid-cols-1 lg:grid-cols-3 gap-4">
          {COLUMNS.map((col) => {
            const items = (signing && signing[col.field]) || col.fallback;
            return (
              <div key={col.id} data-testid={`trust-col-${col.id}`} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${col.tagClass}`}>
                  {col.tag}
                </span>
                <ul className="mt-4 space-y-3">
                  {items.map((it, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-slate-700 leading-relaxed">
                      <CheckCircle2 className={`h-4 w-4 mt-0.5 shrink-0 ${col.dotClass}`} />
                      <span>{it}</span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>

        <p className="mt-6 text-xs text-slate-400 max-w-3xl">
          {signing
            ? `Active signing: ${signing.algorithm} · provider "${signing.active_provider}" (${signing.active_mode}). Config-only migration to: ${(signing.supported_providers || []).join(", ")}.`
            : "Active signing: Ed25519 software provider. Cloud KMS / HSM migration is configuration-only."}
          {" "}Readiness and planned items are not active capabilities unless stated as Current.
        </p>
      </div>
    </section>
  );
};
