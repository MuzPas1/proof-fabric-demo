import React from "react";
import {
  ArrowUpRight, Code, BookOpen, FileJson, FileText, Key, Rocket, Plug, Network, Boxes,
} from "lucide-react";
import { SectionHeader } from "./GetStarted";
import { RESOURCES } from "./data";

const ICONS = { Code, BookOpen, FileJson, FileText, Key, Rocket, Plug, Network, Boxes };

export const Resources = () => (
  <section id="resources" className="scroll-mt-20 bg-slate-50 border-y border-slate-200" data-testid="dev-resources">
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
      <SectionHeader
        eyebrow="Documentation"
        title="API documentation & resources"
        subtitle="Everything you need to integrate — interactive explorers, machine-readable specs, and in-depth guides."
      />
      <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {RESOURCES.map((r) => {
          const Icon = ICONS[r.icon] || FileText;
          return (
            <a
              key={r.id}
              href={r.href}
              target={r.external ? "_blank" : undefined}
              rel={r.external ? "noreferrer" : undefined}
              data-testid={`resource-${r.id}`}
              className="group relative bg-white border border-slate-200 rounded-xl p-6 shadow-sm transition-all duration-200 hover:shadow-md hover:border-slate-300 hover:-translate-y-0.5"
            >
              <ArrowUpRight className="absolute top-5 right-5 h-4 w-4 text-slate-300 group-hover:text-blue-600 transition-colors" />
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                <Icon className="h-5 w-5 text-blue-600" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 font-['Space_Grotesk']">{r.title}</h3>
              <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">{r.desc}</p>
            </a>
          );
        })}
      </div>
    </div>
  </section>
);
