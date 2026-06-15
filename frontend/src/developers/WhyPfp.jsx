import React from "react";
import { ArrowRight } from "lucide-react";
import { LIFECYCLE } from "./data";

export const WhyPfp = () => (
  <section id="why" className="scroll-mt-20 bg-slate-950 text-white border-b border-slate-800 relative overflow-hidden" data-testid="dev-why-pfp">
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(37,99,235,0.18),transparent_55%)] pointer-events-none" />
    <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-400">Why PFP</div>
      <h2 className="mt-3 max-w-3xl text-3xl md:text-4xl font-bold tracking-tight font-['Space_Grotesk']">
        Traditional systems generate records.
        <span className="text-blue-400"> PFP generates independently verifiable proof.</span>
      </h2>
      <p className="mt-5 max-w-2xl text-base md:text-lg text-slate-300 leading-relaxed">
        A record asks you to trust the system that stored it. A Proof Artifact can be verified by
        anyone, anywhere, using only a public key — even years later, fully offline. General-purpose
        proof infrastructure for any event that must be trusted without trusting its source.
      </p>

      {/* Lifecycle */}
      <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3" data-testid="why-lifecycle">
        {LIFECYCLE.map((step, i) => (
          <div key={step.label} className="relative">
            <div className="h-full rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur px-4 py-5">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center">{i + 1}</span>
                <span className="text-sm font-semibold text-white">{step.label}</span>
              </div>
              <p className="mt-2 text-xs text-slate-400 leading-relaxed">{step.desc}</p>
            </div>
            {i < LIFECYCLE.length - 1 && (
              <ArrowRight className="hidden lg:block absolute top-1/2 -right-3 -translate-y-1/2 h-4 w-4 text-slate-600 z-10" />
            )}
          </div>
        ))}
      </div>
    </div>
  </section>
);
