import React, { useEffect, useState } from "react";
import { ShieldCheck, Loader2, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { CodeBlock } from "./CodeBlock";
import { useSandbox } from "./SandboxContext";
import { API } from "./data";

const CheckRow = ({ ok, label, detail, testid }) => (
  <div className="flex items-center gap-3 py-2 border-b border-slate-100 last:border-0" data-testid={testid}>
    {ok ? <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" /> : <XCircle className="h-5 w-5 text-red-500 shrink-0" />}
    <div className="min-w-0">
      <div className="text-sm font-medium text-slate-800">{label}</div>
      {detail && <div className="text-xs text-slate-500 font-mono truncate">{detail}</div>}
    </div>
    <span className={`ml-auto text-xs font-semibold ${ok ? "text-emerald-600" : "text-red-600"}`}>{ok ? "PASS" : "FAIL"}</span>
  </div>
);

export const VerifyProof = () => {
  const { lastProofId } = useSandbox();
  const [proofId, setProofId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // Auto-fill with the proof generated in Step 2.
  useEffect(() => {
    if (lastProofId) {
      setProofId(lastProofId);
      setResult(null);
      setError(null);
    }
  }, [lastProofId]);

  const verify = async () => {
    const id = proofId.trim();
    if (!id) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API}/public/verify/${encodeURIComponent(id)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Proof not found (${res.status})`);
      setResult(data);
    } catch (e) {
      setError(e.message || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  const valid = result?.signature_valid;

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm" data-testid="playground-verify-proof">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
          <ShieldCheck className="h-5 w-5 text-white" />
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-blue-600">Step 3</div>
          <h3 className="text-lg font-semibold text-slate-900 font-['Space_Grotesk']">Verify a proof</h3>
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-600 leading-relaxed">
        Independently verify any Proof Artifact by its ID — no auth, no contacting the issuer.
        Verification re-derives the canonical hash and checks the Ed25519 signature.
      </p>

      <div className="mt-5 flex flex-col sm:flex-row gap-2">
        <input
          value={proofId}
          onChange={(e) => setProofId(e.target.value)}
          placeholder="Paste a Proof ID (fea_id)"
          data-testid="verify-proof-input"
          className="flex-1 rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm font-mono text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-600/30 focus:border-blue-500"
        />
        <button
          onClick={verify}
          disabled={!proofId.trim() || loading}
          data-testid="verify-proof-btn"
          className="inline-flex items-center justify-center gap-2 bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium rounded-lg px-5 py-2.5 transition-colors"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          {loading ? "Verifying\u2026" : "Verify Proof"}
        </button>
      </div>

      {error && (
        <div className="mt-4 flex items-center gap-2 text-sm text-red-700 bg-red-50 ring-1 ring-inset ring-red-600/20 rounded-lg px-3 py-2" data-testid="verify-proof-error">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {result && (
        <div className="mt-5" data-testid="verify-proof-result">
          <div
            className={`flex items-center gap-3 rounded-xl px-4 py-3 ring-1 ring-inset ${valid ? "bg-emerald-50 ring-emerald-600/20" : "bg-red-50 ring-red-600/20"}`}
            data-testid="verify-outcome"
          >
            {valid ? <CheckCircle2 className="h-6 w-6 text-emerald-600" /> : <XCircle className="h-6 w-6 text-red-600" />}
            <div>
              <div className={`text-sm font-semibold ${valid ? "text-emerald-800" : "text-red-800"}`}>
                {valid ? "Proof is authentic & untampered" : "Verification failed"}
              </div>
              <div className="text-xs text-slate-500">Outcome from the live verification engine</div>
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-slate-200 px-4">
            <CheckRow ok={valid} label="Signature validation" detail={`Ed25519 · ${result.signature_version}`} testid="check-signature" />
            <CheckRow ok={!!result.fea_payload?.fea_hash} label="Hash validation" detail={result.fea_payload?.fea_hash} testid="check-hash" />
            <CheckRow ok={!!result.created_at} label="Timestamp validation" detail={result.created_at} testid="check-timestamp" />
          </div>

          <div className="mt-4">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Verification response</div>
            <CodeBlock code={JSON.stringify(result, null, 2)} lang="json" testid="verify-response" />
          </div>
        </div>
      )}
    </div>
  );
};
