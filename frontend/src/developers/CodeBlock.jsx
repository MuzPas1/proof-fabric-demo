import React, { useState } from "react";
import { Check, Copy } from "lucide-react";

export const CodeBlock = ({ code, lang = "bash", testid }) => {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch (_) {}
  };

  return (
    <div className="relative mt-4 rounded-xl border border-slate-800 bg-slate-950 shadow-inner overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800/80">
        <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-500">
          {lang}
        </span>
        <button
          onClick={copy}
          data-testid={testid ? `copy-${testid}` : "copy-code-btn"}
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors"
          aria-label="Copy code"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 md:p-5">
        <code className="font-mono text-[13px] leading-relaxed text-slate-200 whitespace-pre">
          {code}
        </code>
      </pre>
    </div>
  );
};
