import React from "react";
import { useNavigate } from "react-router-dom";
import {
  Rocket, Code, Network, ShieldCheck, Boxes, ServerCog, Scale, FileJson, Tag, Search, ArrowRight, ExternalLink,
} from "lucide-react";
import { DOC_TREE, CANONICAL } from "./docsData";

const ICONS = { Rocket, Code, Network, ShieldCheck, Boxes, ServerCog, Scale, FileJson, Tag };

const QUICK = [
  { label: "Developer Portal", desc: "Interactive sandbox & onboarding", href: CANONICAL.developers, internal: true },
  { label: "Swagger UI", desc: "Try the API live", href: CANONICAL.swagger },
  { label: "OpenAPI Spec", desc: "Machine-readable contract", href: CANONICAL.openapi },
  { label: "Demo Platform", desc: "Transaction Evidence Dashboard", href: CANONICAL.demo },
];

export const DocsHome = ({ onSearch }) => {
  const navigate = useNavigate();

  const openCat = (cat) => {
    const first = cat.items.find((i) => i.type !== "link") || cat.items[0];
    if (first.type === "link") window.open(first.href, "_blank", "noopener");
    else navigate(`/docs/${first.slug}`);
  };

  return (
    <div data-testid="docs-home">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">Documentation</div>
      <h1 className="mt-2 text-3xl md:text-4xl font-bold tracking-tight text-slate-900 font-['Space_Grotesk']">
        Proof Fabric Protocol docs
      </h1>
      <p className="mt-4 max-w-2xl text-[15px] md:text-base leading-7 text-slate-600">
        The single source of truth for PFP — product, architecture, security, integration, operations,
        governance and release notes. New here? Start with the Overview and Quickstart to understand
        general-purpose, independently verifiable Proof Artifacts in 5 minutes.
      </p>

      <button
        onClick={onSearch}
        data-testid="docs-home-search"
        className="mt-6 inline-flex items-center gap-3 w-full max-w-md rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-slate-400 hover:border-slate-300 hover:shadow-sm transition-all"
      >
        <Search className="h-4 w-4" /> Search the documentation…
        <kbd className="ml-auto rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-medium text-slate-500">⌘K</kbd>
      </button>

      <div className="mt-6 flex flex-wrap gap-2">
        <button onClick={() => navigate("/docs/overview")} data-testid="docs-cta-overview" className="inline-flex items-center gap-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 px-4 py-2 text-sm font-medium transition-colors">
          <Rocket className="h-4 w-4" /> Read the Overview
        </button>
        <button onClick={() => navigate("/docs/quickstart")} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 px-4 py-2 text-sm font-medium transition-colors">
          Quickstart <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      {/* Quick links to interactive surfaces (not duplicated here) */}
      <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {QUICK.map((q) => (
          <a
            key={q.label}
            href={q.href}
            target={q.internal ? undefined : "_blank"}
            rel={q.internal ? undefined : "noreferrer"}
            onClick={q.internal ? (e) => { e.preventDefault(); navigate(q.href); } : undefined}
            data-testid={`docs-quick-${q.label.toLowerCase().replace(/\s+/g, "-")}`}
            className="group rounded-xl border border-slate-200 bg-white p-4 hover:border-blue-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-900">{q.label}</span>
              {!q.internal && <ExternalLink className="h-3.5 w-3.5 text-slate-300 group-hover:text-blue-500" />}
            </div>
            <div className="mt-1 text-xs text-slate-500">{q.desc}</div>
          </a>
        ))}
      </div>

      {/* Category grid */}
      <h2 className="mt-14 text-lg font-semibold text-slate-900 font-['Space_Grotesk']">Browse by category</h2>
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {DOC_TREE.map((cat) => {
          const Icon = ICONS[cat.icon] || Rocket;
          return (
            <button
              key={cat.id}
              onClick={() => openCat(cat)}
              data-testid={`docs-cat-${cat.id}`}
              className="group text-left rounded-2xl border border-slate-200 bg-white p-5 hover:border-blue-300 hover:shadow-md hover:-translate-y-0.5 transition-all"
            >
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                <Icon className="h-5 w-5 text-blue-600" />
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-sm font-semibold text-slate-900">
                {cat.label}
                <ArrowRight className="h-3.5 w-3.5 text-slate-300 group-hover:text-blue-500 group-hover:translate-x-0.5 transition-all" />
              </div>
              <div className="mt-1 text-xs text-slate-500">{cat.blurb}</div>
              <div className="mt-2 text-[11px] text-slate-400">{cat.items.length} item{cat.items.length > 1 ? "s" : ""}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
