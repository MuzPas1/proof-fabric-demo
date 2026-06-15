import React from "react";
import { Rocket } from "lucide-react";
import { ONBOARDING } from "./data";

const scrollTo = (id) => () => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

export const Onboarding = () => (
  <section id="onboarding" className="scroll-mt-20 bg-slate-50 border-b border-slate-200" data-testid="dev-onboarding">
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-16">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
        <Rocket className="h-3.5 w-3.5" /> Onboarding · ~5 minutes
      </div>
      <h2 className="mt-3 text-2xl md:text-3xl font-bold tracking-tight text-slate-900 font-['Space_Grotesk']">
        From zero to verified proof in five steps
      </h2>

      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {ONBOARDING.map((s) => (
          <button
            key={s.n}
            onClick={scrollTo(s.target)}
            data-testid={`onboarding-step-${s.n}`}
            className="text-left group rounded-xl border border-slate-200 bg-white p-4 transition-all hover:shadow-md hover:border-blue-300 hover:-translate-y-0.5"
          >
            <span className="inline-flex w-7 h-7 rounded-full bg-blue-100 text-blue-700 text-sm font-bold items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-colors">
              {s.n}
            </span>
            <div className="mt-3 text-sm font-semibold text-slate-900">{s.title}</div>
            <div className="mt-1 text-xs text-slate-500 leading-relaxed">{s.desc}</div>
          </button>
        ))}
      </div>
    </div>
  </section>
);
