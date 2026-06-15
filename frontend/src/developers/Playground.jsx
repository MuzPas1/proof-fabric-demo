import React from "react";
import { Beaker, ArrowDown } from "lucide-react";
import { SectionHeader } from "./GetStarted";
import { SandboxKey } from "./SandboxKey";
import { FirstProof } from "./FirstProof";
import { VerifyProof } from "./VerifyProof";

export const Playground = () => (
  <section id="playground" className="scroll-mt-20 bg-white" data-testid="dev-playground">
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <SectionHeader
          eyebrow="Try It Live"
          title="The full lifecycle, in your browser"
          subtitle="Generate a real sandbox key, sign a live Proof Artifact, then independently verify it — Generate → Verify — without writing a line of code."
        />
        <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20 px-3 py-1 text-sm font-medium">
          <Beaker className="h-3.5 w-3.5" /> Live sandbox
        </div>
      </div>

      <div className="mt-12 grid grid-cols-1 lg:grid-cols-3 gap-5 lg:gap-4 items-start relative">
        <SandboxKey />
        <FirstProof />
        <VerifyProof />
      </div>

      <div className="mt-6 flex items-center justify-center gap-2 text-sm text-slate-400">
        <ArrowDown className="h-4 w-4" /> Each step pre-fills the next — finish the whole flow in under a minute.
      </div>
    </div>
  </section>
);
