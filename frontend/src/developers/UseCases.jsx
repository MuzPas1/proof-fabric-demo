import React from "react";
import {
  Landmark, BrainCircuit, GraduationCap, Signal, ScrollText, Building2, HeartPulse, Truck,
  FileSignature, ShieldCheck, Fingerprint, Globe, Boxes, Plug,
} from "lucide-react";
import { SectionHeader } from "./GetStarted";
import { INDUSTRIES, CAPABILITIES } from "./data";

const ICONS = {
  Landmark, BrainCircuit, GraduationCap, Signal, ScrollText, Building2, HeartPulse, Truck,
  FileSignature, ShieldCheck, Fingerprint, Globe, Boxes, Plug,
};

export const UseCases = () => (
  <section id="use-cases" className="scroll-mt-20 bg-white border-y border-slate-200" data-testid="dev-use-cases">
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
      <SectionHeader
        eyebrow="For Evaluators"
        title="One proof layer, every industry"
        subtitle="PFP is general-purpose proof infrastructure. CTOs, CISOs, compliance leaders and regulators can grasp the value in 60 seconds — developers can integrate it the same afternoon."
      />

      {/* Industries */}
      <div className="mt-12">
        <div className="text-sm font-semibold text-slate-900 font-['Space_Grotesk']">Industry use cases</div>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {INDUSTRIES.map((it) => {
            const Icon = ICONS[it.icon] || ShieldCheck;
            return (
              <div key={it.label} data-testid={`industry-${it.label.toLowerCase().replace(/\s+/g, "-")}`} className="rounded-xl border border-slate-200 p-5 transition-all hover:shadow-md hover:border-slate-300 hover:-translate-y-0.5">
                <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                  <Icon className="h-5 w-5 text-blue-600" />
                </div>
                <div className="mt-3 text-sm font-semibold text-slate-900">{it.label}</div>
                <div className="mt-1 text-xs text-slate-500 leading-relaxed">{it.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Capabilities */}
      <div className="mt-14">
        <div className="text-sm font-semibold text-slate-900 font-['Space_Grotesk']">Key capabilities</div>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {CAPABILITIES.map((c) => {
            const Icon = ICONS[c.icon] || ShieldCheck;
            return (
              <div key={c.label} data-testid={`capability-${c.label.toLowerCase().replace(/\s+/g, "-")}`} className="flex items-start gap-3 rounded-xl bg-slate-50 border border-slate-200 p-5">
                <div className="w-9 h-9 rounded-lg bg-white border border-slate-200 flex items-center justify-center shrink-0">
                  <Icon className="h-4 w-4 text-blue-600" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-900">{c.label}</div>
                  <div className="mt-0.5 text-xs text-slate-500 leading-relaxed">{c.desc}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  </section>
);
