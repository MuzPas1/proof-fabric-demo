import { useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  ShieldCheck,
  AlertTriangle,
  Loader2,
  ChevronDown,
  RotateCcw,
  Fingerprint,
  GitCompareArrows,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SHARED_TXN_ID = "TXN-8F2C-2026-00418";
const DEFAULT_TS = "2026-02-10T14:23:00Z";

const makeDefaultRecord = () => ({
  transaction_id: SHARED_TXN_ID,
  user_id: "user_92341",
  amount: "2450.00",
  created_at: DEFAULT_TS,
});

const FIELD_DEFS = [
  { key: "transaction_id", label: "Transaction ID", mono: true },
  { key: "user_id", label: "User ID", mono: true },
  { key: "amount", label: "Amount", mono: true },
  { key: "created_at", label: "Timestamp", mono: true },
];

function shortHash(h) {
  if (!h) return "";
  return `${h.slice(0, 10)}…${h.slice(-6)}`;
}

function PartyCard({
  label,
  accent,
  record,
  proof,
  isStale,
  loading,
  onChange,
  onGenerate,
  testIdPrefix,
}) {
  const hasProof = Boolean(proof);
  return (
    <Card
      className={`bg-[#0b0b0d] border-zinc-800 ${
        isStale ? "ring-1 ring-amber-500/30" : ""
      }`}
      data-testid={`${testIdPrefix}-card`}
    >
      <CardHeader className="border-b border-zinc-800/70 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex w-8 h-8 items-center justify-center rounded-sm text-sm font-bold ${accent.badge}`}
            >
              {label.slice(-1)}
            </span>
            <CardTitle className="text-base font-semibold tracking-tight text-zinc-100">
              {label} Record
            </CardTitle>
          </div>
          {hasProof && !isStale && (
            <Badge
              className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono text-[10px] tracking-wider uppercase"
              data-testid={`${testIdPrefix}-proof-valid-badge`}
            >
              Proof Ready
            </Badge>
          )}
          {isStale && (
            <Badge
              className="bg-amber-500/10 text-amber-400 border border-amber-500/30 font-mono text-[10px] tracking-wider uppercase"
              data-testid={`${testIdPrefix}-proof-stale-badge`}
            >
              Proof Stale
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-5 space-y-4">
        {FIELD_DEFS.map((f) => (
          <div key={f.key} className="space-y-1.5">
            <Label
              htmlFor={`${testIdPrefix}-${f.key}`}
              className="text-[11px] uppercase tracking-[0.14em] text-zinc-500 font-medium"
            >
              {f.label}
            </Label>
            <Input
              id={`${testIdPrefix}-${f.key}`}
              data-testid={`${testIdPrefix}-${f.key}-input`}
              value={record[f.key]}
              onChange={(e) => onChange(f.key, e.target.value)}
              className={`bg-[#050506] border-zinc-800 text-zinc-100 h-10 ${
                f.mono ? "font-mono text-sm" : ""
              } focus-visible:ring-1 focus-visible:ring-zinc-600 focus-visible:border-zinc-700`}
            />
          </div>
        ))}

        <div className="pt-2 flex items-center justify-between gap-3">
          <div
            className={`flex-1 min-w-0 flex items-center gap-2 text-xs font-mono px-3 py-2 rounded-sm border ${
              isStale
                ? "text-amber-400/70 border-amber-500/20 bg-amber-500/[0.03]"
                : hasProof
                ? "text-emerald-400/90 border-emerald-500/20 bg-emerald-500/[0.03]"
                : "text-zinc-600 border-zinc-800 bg-zinc-900/30"
            }`}
            data-testid={`${testIdPrefix}-proof-display`}
          >
            <Fingerprint className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">
              {hasProof
                ? isStale
                  ? "stale — edit detected, regenerate"
                  : shortHash(proof.proof_hash)
                : "no proof yet"}
            </span>
          </div>

          <Button
            onClick={onGenerate}
            disabled={loading}
            className={`h-10 px-4 text-xs font-medium tracking-wide ${accent.button}`}
            data-testid={`${testIdPrefix}-generate-btn`}
          >
            {loading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin mr-2" />
            ) : (
              <Fingerprint className="w-3.5 h-3.5 mr-2" />
            )}
            Generate {label} Proof
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ResultCard({ result, proofA, proofB }) {
  if (!result) return null;

  const isMatch = result === "match";
  return (
    <Card
      className={`border ${
        isMatch
          ? "bg-emerald-500/[0.04] border-emerald-500/30"
          : "bg-red-500/[0.04] border-red-500/30"
      }`}
      data-testid={`result-card-${result}`}
    >
      <CardContent className="p-6">
        <div className="flex items-start gap-4">
          <div
            className={`w-12 h-12 rounded-sm flex items-center justify-center shrink-0 ${
              isMatch
                ? "bg-emerald-500/10 border border-emerald-500/40"
                : "bg-red-500/10 border border-red-500/40"
            }`}
          >
            {isMatch ? (
              <ShieldCheck className="w-6 h-6 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-6 h-6 text-red-400" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <h3
              className={`text-lg font-semibold tracking-tight ${
                isMatch ? "text-emerald-300" : "text-red-300"
              }`}
              data-testid="result-headline"
            >
              {isMatch
                ? "Records Consistent Across Parties"
                : "Mismatch Detected — Potential Dispute"}
            </h3>
            <p className="text-sm text-zinc-400 mt-1">
              {isMatch
                ? "Both parties produced identical proofs. Their records are logically equivalent — no raw data was exchanged."
                : "The two parties produced different proofs. Their records diverge on at least one normalized field."}
            </p>

            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
              <div className="px-3 py-2 rounded-sm bg-black/30 border border-zinc-800">
                <span className="text-zinc-500 mr-2">A</span>
                <span className={isMatch ? "text-emerald-400" : "text-red-400"}>
                  {shortHash(proofA?.proof_hash)}
                </span>
              </div>
              <div className="px-3 py-2 rounded-sm bg-black/30 border border-zinc-800">
                <span className="text-zinc-500 mr-2">B</span>
                <span className={isMatch ? "text-emerald-400" : "text-red-400"}>
                  {shortHash(proofB?.proof_hash)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function TwoPartyProofComparison() {
  const [recordA, setRecordA] = useState(makeDefaultRecord);
  const [recordB, setRecordB] = useState(makeDefaultRecord);
  const [proofA, setProofA] = useState(null);
  const [proofB, setProofB] = useState(null);
  const [loadingA, setLoadingA] = useState(false);
  const [loadingB, setLoadingB] = useState(false);
  const [result, setResult] = useState(null); // 'match' | 'mismatch' | null
  const [detailsOpen, setDetailsOpen] = useState(false);

  const staleA = useMemo(
    () => Boolean(proofA && proofA._sourceSnapshot !== JSON.stringify(recordA)),
    [proofA, recordA]
  );
  const staleB = useMemo(
    () => Boolean(proofB && proofB._sourceSnapshot !== JSON.stringify(recordB)),
    [proofB, recordB]
  );

  const canCompare =
    proofA && proofB && !staleA && !staleB && !loadingA && !loadingB;

  const invalidateResultIfNeeded = () => {
    if (result !== null) setResult(null);
  };

  const updateRecordA = (key, value) => {
    setRecordA((r) => ({ ...r, [key]: value }));
    invalidateResultIfNeeded();
  };
  const updateRecordB = (key, value) => {
    setRecordB((r) => ({ ...r, [key]: value }));
    invalidateResultIfNeeded();
  };

  const generateProof = async (party) => {
    const record = party === "A" ? recordA : recordB;
    const setLoading = party === "A" ? setLoadingA : setLoadingB;
    const setProof = party === "A" ? setProofA : setProofB;

    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/demo/proof`, record);
      setProof({ ...data, _sourceSnapshot: JSON.stringify(record) });
      setResult(null);
      toast.success(`Party ${party} proof generated`);
    } catch (e) {
      const detail =
        e?.response?.data?.detail || e?.message || "Failed to generate proof";
      toast.error(`Party ${party}: ${detail}`);
    } finally {
      setLoading(false);
    }
  };

  const compareProofs = () => {
    if (!canCompare) return;
    const match = proofA.proof_hash === proofB.proof_hash;
    setResult(match ? "match" : "mismatch");
  };

  const resetDemo = () => {
    setRecordA(makeDefaultRecord());
    setRecordB(makeDefaultRecord());
    setProofA(null);
    setProofB(null);
    setResult(null);
    setDetailsOpen(false);
    toast.message("Demo reset to identical sample records");
  };

  return (
    <div
      className="min-h-screen bg-[#050505] text-zinc-100"
      data-testid="two-party-demo"
    >
      {/* Backdrop grid accent */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, #ffffff 1px, transparent 0)",
          backgroundSize: "28px 28px",
        }}
      />

      <div className="relative max-w-6xl mx-auto px-6 py-12 sm:py-16">
        {/* Header */}
        <header className="mb-10 sm:mb-14">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-8 h-8 rounded-sm bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <span className="text-[11px] uppercase tracking-[0.22em] text-zinc-500 font-mono">
              Proof Fabric Protocol · Demo
            </span>
          </div>
          <h1
            className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight font-['Space_Grotesk'] leading-[1.05]"
            data-testid="demo-title"
          >
            Two-Party Proof
            <br />
            <span className="text-emerald-400">Comparison.</span>
          </h1>
          <p className="mt-5 text-base sm:text-lg text-zinc-400 max-w-2xl">
            Proof-based comparison across parties — without exposing raw
            transaction data. Each side independently normalizes and proves its
            record, then only the proofs are compared.
          </p>
        </header>

        {/* Shared transaction reference */}
        <div
          className="mb-6 flex items-center justify-between gap-3 px-4 py-3 rounded-sm border border-zinc-800 bg-zinc-900/30"
          data-testid="shared-reference"
        >
          <div className="flex items-center gap-3 min-w-0">
            <GitCompareArrows className="w-4 h-4 text-zinc-500 shrink-0" />
            <div className="flex items-center gap-2 min-w-0 flex-wrap">
              <span className="text-[11px] uppercase tracking-[0.14em] text-zinc-500">
                Shared reference
              </span>
              <code className="font-mono text-xs text-zinc-300 truncate">
                transaction_id = {SHARED_TXN_ID}
              </code>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetDemo}
            className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 h-8 text-xs"
            data-testid="reset-demo-btn"
          >
            <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
            Reset
          </Button>
        </div>

        {/* Two parties */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5" data-testid="parties-grid">
          <PartyCard
            label="Party A"
            accent={{
              badge: "bg-sky-500/10 text-sky-400 border border-sky-500/30",
              button:
                "bg-sky-500/90 hover:bg-sky-400 text-sky-950 border border-sky-400/40",
            }}
            record={recordA}
            proof={proofA}
            isStale={staleA}
            loading={loadingA}
            onChange={updateRecordA}
            onGenerate={() => generateProof("A")}
            testIdPrefix="party-a"
          />
          <PartyCard
            label="Party B"
            accent={{
              badge:
                "bg-violet-500/10 text-violet-400 border border-violet-500/30",
              button:
                "bg-violet-500/90 hover:bg-violet-400 text-violet-950 border border-violet-400/40",
            }}
            record={recordB}
            proof={proofB}
            isStale={staleB}
            loading={loadingB}
            onChange={updateRecordB}
            onGenerate={() => generateProof("B")}
            testIdPrefix="party-b"
          />
        </div>

        {/* Compare action */}
        <div className="my-8 flex flex-col items-center gap-3">
          <Button
            onClick={compareProofs}
            disabled={!canCompare}
            className="h-12 px-8 text-sm font-semibold bg-emerald-500 hover:bg-emerald-400 text-emerald-950 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:border-zinc-800 border border-emerald-400/30 rounded-sm tracking-wide"
            data-testid="compare-btn"
          >
            <GitCompareArrows className="w-4 h-4 mr-2" />
            Compare Proofs
          </Button>
          {!canCompare && (
            <p className="text-xs text-zinc-500 font-mono" data-testid="compare-hint">
              Generate valid proofs for both parties to enable comparison
            </p>
          )}
        </div>

        {/* Result */}
        <ResultCard result={result} proofA={proofA} proofB={proofB} />

        {/* Technical details */}
        <div className="mt-10">
          <Collapsible open={detailsOpen} onOpenChange={setDetailsOpen}>
            <CollapsibleTrigger asChild>
              <button
                className="group flex items-center gap-2 text-xs font-mono text-zinc-500 hover:text-zinc-300 transition-colors"
                data-testid="toggle-tech-details"
              >
                <ChevronDown
                  className={`w-3.5 h-3.5 transition-transform ${
                    detailsOpen ? "rotate-180" : ""
                  }`}
                />
                {detailsOpen ? "Hide technical details" : "Show technical details"}
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-4" data-testid="tech-details-panel">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <TechnicalPanel label="Party A" proof={proofA} stale={staleA} />
                <TechnicalPanel label="Party B" proof={proofB} stale={staleB} />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>

        {/* Footer */}
        <footer className="mt-16 pt-6 border-t border-zinc-800/60 flex flex-wrap items-center gap-x-6 gap-y-2 text-[11px] text-zinc-600 font-mono uppercase tracking-wider">
          <span>Ed25519 · SHA-256 · Deterministic canonicalization</span>
          <span className="ml-auto">Demo · No raw data exchanged</span>
        </footer>
      </div>
    </div>
  );
}

function TechnicalPanel({ label, proof, stale }) {
  return (
    <div className="rounded-sm border border-zinc-800 bg-[#0b0b0d] p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] uppercase tracking-[0.14em] text-zinc-500">
          {label}
        </span>
        {stale && (
          <span className="text-[10px] font-mono text-amber-400 uppercase">
            stale
          </span>
        )}
      </div>
      {!proof ? (
        <p className="text-xs text-zinc-600 font-mono">
          No proof generated yet.
        </p>
      ) : (
        <div className="space-y-3">
          <DetailRow label="proof_hash" value={proof.proof_hash} mono wrap />
          <DetailRow
            label="normalized_payload"
            value={JSON.stringify(proof.normalized_payload, null, 2)}
            mono
            pre
          />
          <DetailRow label="algorithm" value={proof.metadata.algorithm} mono />
          <DetailRow
            label="canonicalization"
            value={proof.metadata.canonicalization}
            mono
          />
          <DetailRow
            label="generated_at"
            value={proof.metadata.generated_at}
            mono
          />
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value, mono, wrap, pre }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-zinc-600 mb-1">
        {label}
      </div>
      {pre ? (
        <pre
          className={`text-[11px] ${
            mono ? "font-mono" : ""
          } text-zinc-300 bg-black/40 border border-zinc-800 rounded-sm p-2 overflow-x-auto`}
        >
          {value}
        </pre>
      ) : (
        <div
          className={`text-xs ${mono ? "font-mono" : ""} text-zinc-300 ${
            wrap ? "break-all" : "truncate"
          }`}
        >
          {value}
        </div>
      )}
    </div>
  );
}
