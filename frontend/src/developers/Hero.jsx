import React from "react";
import { ArrowRight, BookOpen, ShieldCheck, Zap } from "lucide-react";
import { API } from "./data";

const GRID =
  "absolute inset-0 bg-[linear-gradient(to_right,#94a3b8_1px,transparent_1px),linear-gradient(to_bottom,#94a3b8_1px,transparent_1px)] bg-[size:28px_28px] opacity-[0.06] pointer-events-none";

const scrollTo = (id) => (e) => {
  e.preventDefault();
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
};

export const Hero = () => (
  <section className="relative overflow-hidden border-b border-slate-200 bg-white" data-testid="dev-hero">
    <div className={GRID} />
    <div className="absolute -top-24 right-0 h-72 w-72 rounded-full bg-blue-50 blur-3xl opacity-60 pointer-events-none" />
    <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-16 md:pt-28 md:pb-24">
      <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-sm">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Platform live · v2.0 APIs
      </div>
      <h1 className="mt-6 max-w-3xl text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-slate-900 font-['Space_Grotesk']">
        Build with cryptographic proof.
      </h1>
      <p className="mt-5 max-w-2xl text-base md:text-lg text-slate-600 leading-relaxed">
        Turn any event — a payment, an AI decision, a credential, a shipment — into a deterministic,
        Ed25519-signed Proof Artifact that anyone can verify with only the public key. General-purpose
        proof infrastructure: APIs, SDKs and docs, all in one place.
      </p>
      <div className="mt-8 flex flex-wrap items-center gap-3">
        <a
          href="#playground"
          onClick={scrollTo("playground")}
          data-testid="hero-get-started-btn"
          className="inline-flex items-center gap-2 bg-blue-600 text-white hover:bg-blue-700 font-medium rounded-lg px-5 py-2.5 transition-colors"
        >
          <Zap className="h-4 w-4" /> Try the live sandbox
        </a>
        <a
          href={`${API}/docs`}
          target="_blank"
          rel="noreferrer"
          data-testid="hero-api-docs-btn"
          className="inline-flex items-center gap-2 bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 font-medium rounded-lg px-5 py-2.5 transition-colors"
        >
          <BookOpen className="h-4 w-4" /> Explore the API
        </a>
      </div>
      <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-3 text-sm text-slate-500">
        <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-blue-600" /> Ed25519 signatures</span>
        <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-blue-600" /> Deterministic canonicalization</span>
        <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-blue-600" /> Offline verification</span>
        <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-blue-600" /> 4 first-party SDKs</span>
      </div>
    </div>
  </section>
);
