import React from "react";
import { Zap } from "lucide-react";
import { CodeBlock } from "./CodeBlock";
import { STEPS } from "./data";

const SectionHeader = ({ eyebrow, title, subtitle }) => (
  <div className="max-w-2xl">
    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">{eyebrow}</div>
    <h2 className="mt-2 text-2xl md:text-3xl font-bold tracking-tight text-slate-900 font-['Space_Grotesk']">
      {title}
    </h2>
    {subtitle && <p className="mt-3 text-base text-slate-600 leading-relaxed">{subtitle}</p>}
  </div>
);

export const GetStarted = () => (
  <section id="get-started" className="scroll-mt-20 bg-white" data-testid="dev-get-started">
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <SectionHeader
          eyebrow="Get Started"
          title="First API call in 15 minutes"
          subtitle="Five steps from zero to a verified Proof Artifact — credentials, generate, verify, integrate, review."
        />
        <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20 px-3 py-1 text-sm font-medium">
          <Zap className="h-3.5 w-3.5" /> ~15 min total
        </div>
      </div>

      <ol className="mt-12 relative">
        {STEPS.map((step, i) => (
          <li key={step.key} className="relative pl-12 md:pl-14 pb-12 last:pb-0" data-testid={`step-${step.key}`}>
            {i < STEPS.length - 1 && (
              <span className="absolute left-4 top-9 bottom-0 w-px bg-slate-200" aria-hidden />
            )}
            <span className="absolute left-0 top-0 w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm bg-blue-100 text-blue-700 border border-blue-200">
              {i + 1}
            </span>
            <div className="flex items-center gap-3 flex-wrap">
              <h3 className="text-lg font-semibold text-slate-900 font-['Space_Grotesk']">{step.title}</h3>
              <span className="text-xs text-slate-400 font-medium">{step.minutes}</span>
            </div>
            <p className="mt-1.5 text-sm text-slate-600 leading-relaxed max-w-2xl">{step.desc}</p>
            <CodeBlock code={step.code} lang={step.lang} testid={step.key} />
          </li>
        ))}
      </ol>
    </div>
  </section>
);

export { SectionHeader };
