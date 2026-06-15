import React, { useState } from "react";
import { Code, Coffee, Hash, Download, ExternalLink } from "lucide-react";
import { SectionHeader } from "./GetStarted";
import { CodeBlock } from "./CodeBlock";
import { SDKS, DOCS, buildSdkExamples } from "./data";
import { useSandbox } from "./SandboxContext";

const ICONS = { Code, Coffee, Hash };

export const Sdks = () => {
  const { apiKey } = useSandbox();
  const examples = buildSdkExamples(apiKey);
  const [active, setActive] = useState("python");
  const current = examples.find((e) => e.id === active) || examples[0];

  return (
    <section id="sdks" className="scroll-mt-20 bg-white" data-testid="dev-sdks">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <SectionHeader
            eyebrow="SDKs & Tools"
            title="SDKs & copy-paste examples"
            subtitle="First-party SDKs with identical canonicalization — generate proofs and verify them independently in any language."
          />
          <a
            href={`${DOCS}/postman_collection.json`}
            target="_blank"
            rel="noreferrer"
            data-testid="postman-download"
            className="inline-flex items-center gap-2 bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 font-medium rounded-lg px-4 py-2 transition-colors"
          >
            <Download className="h-4 w-4" /> Postman Collection
          </a>
        </div>

        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {SDKS.map((s) => {
            const Icon = ICONS[s.icon] || Code;
            return (
              <div
                key={s.id}
                data-testid={`sdk-${s.id}`}
                className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm transition-all duration-200 hover:shadow-md hover:border-slate-300 hover:-translate-y-0.5 flex flex-col"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                    <Icon className="h-5 w-5 text-blue-600" />
                  </div>
                  <h3 className="text-base font-semibold text-slate-900 font-['Space_Grotesk']">{s.name}</h3>
                </div>
                <div className="mt-4 rounded-lg bg-slate-950 border border-slate-800 px-3 py-2">
                  <code className="font-mono text-[12px] text-slate-200 break-words">{s.install}</code>
                </div>
                <p className="mt-3 text-xs text-slate-500">{s.dep}</p>
                <a
                  href={s.source}
                  target="_blank"
                  rel="noreferrer"
                  data-testid={`sdk-source-${s.id}`}
                  className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
                >
                  View source <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            );
          })}
        </div>

        {/* Quick examples (tabbed, key-aware) */}
        <div className="mt-12">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h3 className="text-sm font-semibold text-slate-900 font-['Space_Grotesk']">Quick example — Generate &amp; verify a Proof Artifact</h3>
            {apiKey && <span className="text-xs text-emerald-700 font-medium">Pre-filled with your sandbox key</span>}
          </div>
          <div className="mt-4 inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1" role="tablist">
            {examples.map((e) => (
              <button
                key={e.id}
                onClick={() => setActive(e.id)}
                data-testid={`sdk-tab-${e.id}`}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  active === e.id ? "bg-white text-blue-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {e.name}
              </button>
            ))}
          </div>
          <CodeBlock code={current.code} lang={current.lang} testid={`sdk-example-${current.id}`} />
        </div>
      </div>
    </section>
  );
};
