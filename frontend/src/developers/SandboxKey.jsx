import React from "react";
import { KeyRound, Loader2, CheckCircle2, AlertTriangle, RefreshCw } from "lucide-react";
import { CopyInline } from "./CodeBlock";
import { useSandbox } from "./SandboxContext";

export const SandboxKey = () => {
  const { keyData, generating, keyError, generateKey } = useSandbox();

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm" data-testid="playground-sandbox-key">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
          <KeyRound className="h-5 w-5 text-white" />
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-blue-600">Step 1</div>
          <h3 className="text-lg font-semibold text-slate-900 font-['Space_Grotesk']">Generate a sandbox key</h3>
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-600 leading-relaxed">
        A real, scoped, short-lived credential bound to the isolated <span className="font-mono text-slate-800">sandbox</span> tenant.
        It instantly pre-fills every snippet below. For testing only.
      </p>

      <button
        onClick={generateKey}
        disabled={generating}
        data-testid="generate-sandbox-key-btn"
        className="mt-5 inline-flex items-center gap-2 bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60 font-medium rounded-lg px-5 py-2.5 transition-colors"
      >
        {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : keyData ? <RefreshCw className="h-4 w-4" /> : <KeyRound className="h-4 w-4" />}
        {generating ? "Generating\u2026" : keyData ? "Regenerate key" : "Generate Sandbox Key"}
      </button>

      {keyError && (
        <div className="mt-4 flex items-center gap-2 text-sm text-red-700 bg-red-50 ring-1 ring-inset ring-red-600/20 rounded-lg px-3 py-2" data-testid="sandbox-key-error">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {keyError}
        </div>
      )}

      {keyData && (
        <div className="mt-5 space-y-3" data-testid="sandbox-key-result">
          <CopyInline value={keyData.api_key} label="X-API-Key" testid="sandbox-key" />
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1 text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" /> Live key ready</span>
            <span className="text-slate-300">·</span>
            <span>Scopes: <span className="font-mono text-slate-700">{(keyData.scopes || []).join(", ")}</span></span>
            {keyData.expires_at && (<><span className="text-slate-300">·</span><span>Expires {new Date(keyData.expires_at).toLocaleString()}</span></>)}
          </div>
        </div>
      )}
    </div>
  );
};
