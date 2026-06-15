import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, ExternalLink, ArrowRight } from "lucide-react";
import { API, NAV_SECTIONS } from "./data";

const scrollTo = (id) => (e) => {
  e.preventDefault();
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
};

export const DevNav = () => (
  <header
    className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200"
    data-testid="dev-portal-header"
  >
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
      <Link to="/developers" className="flex items-center gap-3 shrink-0" data-testid="dev-logo-link">
        <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center">
          <ShieldCheck className="w-5 h-5 text-white" />
        </div>
        <div className="leading-none">
          <div className="text-sm font-semibold tracking-tight text-slate-900 font-['Space_Grotesk']">
            Proof Fabric Protocol
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">Developer Portal</div>
        </div>
      </Link>

      <nav className="hidden lg:flex items-center gap-1">
        {NAV_SECTIONS.map((s) => (
          <a
            key={s.id}
            href={`#${s.id}`}
            onClick={scrollTo(s.id)}
            data-testid={`dev-nav-${s.id}`}
            className="px-3 py-2 text-sm text-slate-600 hover:text-slate-900 rounded-md hover:bg-slate-50 transition-colors"
          >
            {s.label}
          </a>
        ))}
      </nav>

      <div className="flex items-center gap-2 shrink-0">
        <Link
          to="/"
          data-testid="dev-nav-demo"
          className="hidden sm:inline-flex text-sm text-slate-600 hover:text-slate-900 px-3 py-2 rounded-md hover:bg-slate-50 transition-colors"
        >
          Demo
        </Link>
        <Link
          to="/admin"
          data-testid="dev-nav-admin"
          className="hidden sm:inline-flex text-sm text-slate-600 hover:text-slate-900 px-3 py-2 rounded-md hover:bg-slate-50 transition-colors"
        >
          Admin
        </Link>
        <a
          href={`${API}/docs`}
          target="_blank"
          rel="noreferrer"
          data-testid="dev-nav-api-docs"
          className="inline-flex items-center gap-1.5 bg-blue-600 text-white hover:bg-blue-700 text-sm font-medium rounded-lg px-3.5 py-2 transition-colors"
        >
          API Docs <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    </div>
  </header>
);

export const DevFooter = () => (
  <footer className="border-t border-slate-200 bg-slate-50" data-testid="dev-portal-footer">
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-white" />
          </div>
          <div className="text-sm text-slate-600">
            <span className="font-semibold text-slate-900 font-['Space_Grotesk']">Proof Fabric Protocol</span>
            <span className="mx-2 text-slate-300">·</span>
            General-purpose, cryptographically verifiable Proof Artifacts
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
          <a href="https://pfprotocol.com" target="_blank" rel="noreferrer" className="text-slate-600 hover:text-blue-600 transition-colors" data-testid="footer-website">Website</a>
          <Link to="/" className="text-slate-600 hover:text-blue-600 transition-colors" data-testid="footer-demo">Demo</Link>
          <Link to="/verify" className="text-slate-600 hover:text-blue-600 transition-colors" data-testid="footer-verify">Verifier</Link>
          <a href={`${API}/docs`} target="_blank" rel="noreferrer" className="text-slate-600 hover:text-blue-600 transition-colors" data-testid="footer-docs">API Docs</a>
          <a href={`${API}/developer`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700 font-medium transition-colors" data-testid="footer-dev-index">
            Developer index <ArrowRight className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>
    </div>
  </footer>
);
