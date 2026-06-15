import React, { useState } from "react";
import { Zap, Loader2, AlertTriangle, ArrowRight } from "lucide-react";
import { CodeBlock, CopyInline } from "./CodeBlock";
import { useSandbox } from "./SandboxContext";
import { API } from "./data";

const buildRequest = () => ({
  idempotency_key: `portal-${Date.now()}`,
  transaction_id: `EVT-${Math.floor(Math.random() * 1_000_000)}`,
  timestamp: new Date().toISOString(),
  amount: 245000,
  currency: "USD",
  payer_id: "sha256:7b9c1f0a",
  payee_id: "sha256:a14d92e3",
});

const Field = ({ label, value, testid }) => (
  <div className="min-w-0">
    <div className="text-[11px] uppercase tracking-wider text-slate-400">{label}</div>
    <CopyInline value={value} testid={testid} />
  </div>
);

export const FirstProof = () => {
  const { apiKey, setLastProofId } = useSandbox();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [req, setReq] = useState(null);
  const [resp, setResp] = useState(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResp(null);
    const body = buildRequest();
    setReq(body);
    try {
      const res = await fetch(`${API}/fea/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
      setResp(data);
      setLastProofId(data.fea_id);
    } catch (e) {
      setError(e.message || "Failed to generate proof");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm" data-testid="playground-first-proof">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
          <Zap className="h-5 w-5 text-white" />
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-blue-600">Step 2</div>
          <h3 className="text-lg font-semibold text-slate-900 font-['Space_Grotesk']">Generate your first proof</h3>
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-600 leading-relaxed">
        Execute a real, live proof-generation request with your sandbox key. PFP canonicalizes,
        hashes and Ed25519-signs the event, returning a verifiable Proof Artifact.
      </p>

      <button
        onClick={run}
        disabled={!apiKey || loading}
        data-testid="generate-proof-btn"
        className="mt-5 inline-flex items-center gap-2 bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium rounded-lg px-5 py-2.5 transition-colors"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
        {loading ? "Generating proof\u2026" : "Generate a Proof Artifact"}
      </button>
      {!apiKey && <p className="mt-2 text-xs text-slate-400" data-testid="first-proof-need-key">Generate a sandbox key first (Step 1).</p>}

      {error && (
        <div className="mt-4 flex items-center gap-2 text-sm text-red-700 bg-red-50 ring-1 ring-inset ring-red-600/20 rounded-lg px-3 py-2" data-testid="first-proof-error">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {req && (
        <div className="mt-5">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Live request</div>
          <CodeBlock code={JSON.stringify(req, null, 2)} lang="json" testid="first-proof-request" />
        </div>
      )}

      {resp && (
        <div className="mt-5 space-y-4" data-testid="first-proof-result">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Proof ID (fea_id)" value={resp.fea_id} testid="proof-id" />
            <Field label="Timestamp" value={resp.created_at} testid="proof-timestamp" />
            <Field label="Hash (fea_hash)" value={resp.fea_payload?.fea_hash || ""} testid="proof-hash" />
            <Field label="Signature (Ed25519)" value={resp.signature} testid="proof-signature" />
          </div>
          <div className="text-xs text-slate-500">
            Signed with key <span className="font-mono text-slate-700">{resp.public_key_id}</span> · version <span className="font-mono text-slate-700">{resp.signature_version}</span>
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Live response</div>
            <CodeBlock code={JSON.stringify(resp, null, 2)} lang="json" testid="first-proof-response" />
          </div>
          <div className="flex items-center gap-2 text-sm text-blue-700 font-medium">
            <ArrowRight className="h-4 w-4" /> Proof ID copied to Step 3 — verify it below.
          </div>
        </div>
      )}
    </div>
  );
};
