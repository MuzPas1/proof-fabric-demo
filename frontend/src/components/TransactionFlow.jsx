import { useState } from "react";
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
import { Switch } from "@/components/ui/switch";
import {
  CheckCircle2,
  ShieldCheck,
  AlertTriangle,
  FileSignature,
  ArrowRight,
  Loader2,
  RotateCcw,
  BadgeCheck,
  Lock,
  Scale,
  GitCompareArrows,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const DEFAULTS = {
  transaction_id: "TXN-8F2C-2026-00418",
  user_id: "user_92341",
  amount: "2450.00",
};

/* --------------------------------- helpers -------------------------------- */

const nowIso = () =>
  new Date().toISOString().replace(/\.\d{3}Z$/, (m) => m);

const formatTs = (iso) => {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
};

const shortHash = (h) => (h ? `${h.slice(0, 10)}…${h.slice(-8)}` : "");

/* ---------------------------- shared components --------------------------- */

function SectionCard({
  step,
  title,
  description,
  tone = "neutral",
  children,
  testId,
  rightSlot,
}) {
  const toneRing = {
    neutral: "border-gray-200",
    success: "border-emerald-200",
    error: "border-red-200",
    info: "border-blue-200",
  }[tone];

  const toneBadge = {
    neutral: "bg-gray-100 text-gray-600",
    success: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
    error: "bg-red-50 text-red-700 ring-1 ring-red-200",
    info: "bg-blue-50 text-blue-700 ring-1 ring-blue-200",
  }[tone];

  return (
    <Card
      className={`bg-white ${toneRing} shadow-sm hover:shadow-md transition-shadow`}
      data-testid={testId}
    >
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div
              className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold ${toneBadge}`}
            >
              {step}
            </div>
            <div>
              <CardTitle className="text-base font-semibold text-gray-900 tracking-tight">
                {title}
              </CardTitle>
              {description && (
                <p className="text-sm text-gray-500 mt-1">{description}</p>
              )}
            </div>
          </div>
          {rightSlot}
        </div>
      </CardHeader>
      <CardContent className="pt-0">{children}</CardContent>
    </Card>
  );
}

function StatusPill({ status, label, testId }) {
  const map = {
    success: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
    error: "bg-red-50 text-red-700 ring-1 ring-red-200",
    neutral: "bg-gray-100 text-gray-700 ring-1 ring-gray-200",
  };
  const Icon =
    status === "success" ? CheckCircle2 : status === "error" ? AlertTriangle : null;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${map[status]}`}
      data-testid={testId}
    >
      {Icon && <Icon className="w-3.5 h-3.5" />}
      {label}
    </span>
  );
}

function CheckRow({ icon: Icon, label, value, testId }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-2.5 text-sm text-gray-700">
        <Icon className="w-4 h-4 text-gray-400" />
        <span>{label}</span>
      </div>
      <StatusPill status="success" label={value} testId={testId} />
    </div>
  );
}

/* ----------------------------- main component ----------------------------- */

export default function TransactionFlow() {
  const [form, setForm] = useState(DEFAULTS);
  const [processed, setProcessed] = useState(false);
  const [processing, setProcessing] = useState(false);

  // Consistency
  const [mismatch, setMismatch] = useState(false);
  const partyAAmount = form.amount;
  const partyBAmount = mismatch
    ? (Number(form.amount) + 100).toFixed(2)
    : form.amount;
  const isConsistent = !mismatch;

  // Evidence
  const [proof, setProof] = useState(null); // { proof_hash, normalized_payload, metadata, issued_at }
  const [generating, setGenerating] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState(null); // 'verified' | 'tampered' | null

  const handleInput = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (processed) {
      // user edited after processing — invalidate downstream
      setProcessed(false);
      setProof(null);
      setVerifyStatus(null);
      setMismatch(false);
    }
  };

  const canProcess =
    form.transaction_id.trim() &&
    form.user_id.trim() &&
    String(form.amount).trim() &&
    !isNaN(Number(form.amount));

  const processTransaction = async () => {
    if (!canProcess) {
      toast.error("Please fill in all fields with valid values.");
      return;
    }
    setProcessing(true);
    // simulate compliance engine delay for UX weight
    await new Promise((r) => setTimeout(r, 450));
    setProcessed(true);
    setProcessing(false);
    setProof(null);
    setVerifyStatus(null);
    toast.success("Transaction processed");
  };

  const generateProof = async () => {
    setGenerating(true);
    setVerifyStatus(null);
    try {
      const payload = {
        transaction_id: form.transaction_id,
        user_id: form.user_id,
        amount: form.amount,
        created_at: nowIso(),
      };
      const { data } = await axios.post(`${API}/demo/proof`, payload);
      setProof({ ...data, issued_at: new Date().toISOString() });
      toast.success("Proof artifact generated");
    } catch (e) {
      const detail =
        e?.response?.data?.detail || e?.message || "Failed to generate proof";
      toast.error(detail);
    } finally {
      setGenerating(false);
    }
  };

  const verifyProof = async () => {
    if (!proof) return;
    setVerifying(true);
    setVerifyStatus(null);
    try {
      // Re-run proof generation on the same normalized input and compare.
      const { data } = await axios.post(`${API}/demo/proof`, {
        transaction_id: proof.normalized_payload.transaction_id,
        user_id: proof.normalized_payload.user_id,
        amount: proof.normalized_payload.amount,
        created_at: proof.normalized_payload.created_at,
      });
      await new Promise((r) => setTimeout(r, 350));
      const ok = data.proof_hash === proof.proof_hash;
      setVerifyStatus(ok ? "verified" : "tampered");
    } catch (e) {
      toast.error("Verification failed");
      setVerifyStatus("tampered");
    } finally {
      setVerifying(false);
    }
  };

  const resetAll = () => {
    setForm(DEFAULTS);
    setProcessed(false);
    setProcessing(false);
    setMismatch(false);
    setProof(null);
    setVerifyStatus(null);
    toast.message("New transaction started");
  };

  return (
    <div
      className="min-h-screen bg-white text-gray-900"
      data-testid="transaction-flow"
    >
      {/* Top Nav */}
      <header className="border-b border-gray-200 bg-white sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-gray-900">
                Proof Fabric Protocol
              </div>
              <div className="text-xs text-gray-500">
                Transaction Evidence Dashboard
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetAll}
            className="text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            data-testid="new-transaction-btn"
          >
            <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
            New Transaction
          </Button>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-10 pb-6">
        <h1
          className="text-3xl sm:text-4xl font-semibold tracking-tight text-gray-900 font-['Space_Grotesk']"
          data-testid="page-title"
        >
          Transaction to verifiable evidence, in one flow.
        </h1>
        <p
          className="mt-3 text-base text-gray-600 max-w-2xl"
          data-testid="page-subtitle"
        >
          This demo shows how transactions are converted into independently
          verifiable proof artifacts.
        </p>
      </section>

      <main className="max-w-5xl mx-auto px-6 pb-20 space-y-5">
        {/* 1. Transaction Input */}
        <SectionCard
          step="1"
          title="Transaction"
          description="Enter the transaction details to begin processing."
          testId="section-transaction"
          tone={processed ? "success" : "neutral"}
          rightSlot={
            processed && (
              <StatusPill
                status="success"
                label="Processed"
                testId="transaction-processed-badge"
              />
            )
          }
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <FieldInput
              label="Transaction ID"
              value={form.transaction_id}
              onChange={(v) => handleInput("transaction_id", v)}
              testId="input-transaction-id"
              mono
            />
            <FieldInput
              label="User ID"
              value={form.user_id}
              onChange={(v) => handleInput("user_id", v)}
              testId="input-user-id"
              mono
            />
            <FieldInput
              label="Amount"
              value={form.amount}
              onChange={(v) => handleInput("amount", v)}
              testId="input-amount"
              mono
              prefix="₹"
            />
          </div>
          <div className="mt-5 flex items-center justify-end">
            <Button
              onClick={processTransaction}
              disabled={!canProcess || processing}
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium"
              data-testid="process-transaction-btn"
            >
              {processing ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <ArrowRight className="w-4 h-4 mr-2" />
              )}
              Process Transaction
            </Button>
          </div>
        </SectionCard>

        {/* Downstream sections — reveal after processing */}
        {processed && (
          <>
            {/* 2. Compliance */}
            <SectionCard
              step="2"
              title="Compliance Checks"
              description="Automated KYC, AML and transaction limit verification."
              testId="section-compliance"
              tone="success"
              rightSlot={
                <StatusPill
                  status="success"
                  label="Compliant"
                  testId="compliance-overall-badge"
                />
              }
            >
              <div className="rounded-lg bg-gray-50 border border-gray-100 px-4 py-2">
                <CheckRow
                  icon={BadgeCheck}
                  label="KYC verification"
                  value="Pass"
                  testId="compliance-kyc"
                />
                <CheckRow
                  icon={Lock}
                  label="AML screening"
                  value="Pass"
                  testId="compliance-aml"
                />
                <CheckRow
                  icon={Scale}
                  label="Transaction limits"
                  value="Within range"
                  testId="compliance-limits"
                />
              </div>
              <p
                className="text-sm text-emerald-700 font-medium mt-4"
                data-testid="compliance-summary"
              >
                Transaction is COMPLIANT
              </p>
            </SectionCard>

            {/* 3. Consistency */}
            <SectionCard
              step="3"
              title="Cross-Party Consistency"
              description="Compare the transaction record as seen by both parties."
              testId="section-consistency"
              tone={isConsistent ? "success" : "error"}
              rightSlot={
                <div className="flex items-center gap-2.5">
                  <Label
                    htmlFor="mismatch-toggle"
                    className="text-xs text-gray-500"
                  >
                    Simulate Mismatch
                  </Label>
                  <Switch
                    id="mismatch-toggle"
                    checked={mismatch}
                    onCheckedChange={setMismatch}
                    data-testid="mismatch-toggle"
                  />
                </div>
              }
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <PartyPanel
                  name="Party A"
                  subtitle="Client · Razorpay"
                  amount={partyAAmount}
                  testId="party-a-panel"
                />
                <PartyPanel
                  name="Party B"
                  subtitle="Bank · HDFC"
                  amount={partyBAmount}
                  diverged={!isConsistent}
                  testId="party-b-panel"
                />
              </div>
              <div className="mt-4 flex items-center justify-between">
                <div className="text-sm text-gray-600 flex items-center gap-2">
                  <GitCompareArrows className="w-4 h-4 text-gray-400" />
                  Comparing records across parties
                </div>
                {isConsistent ? (
                  <StatusPill
                    status="success"
                    label="CONSISTENT"
                    testId="consistency-status"
                  />
                ) : (
                  <StatusPill
                    status="error"
                    label="MISMATCH DETECTED"
                    testId="consistency-status"
                  />
                )}
              </div>
            </SectionCard>

            {/* 4. Exception (only on mismatch) */}
            {!isConsistent && (
              <SectionCard
                step="4"
                title="Exception"
                description="Discrepancy requiring review before settlement."
                testId="section-exception"
                tone="error"
                rightSlot={
                  <StatusPill
                    status="error"
                    label="Open"
                    testId="exception-status"
                  />
                }
              >
                <div className="rounded-lg bg-red-50 border border-red-100 p-4 flex items-start gap-3">
                  <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
                  <div>
                    <div
                      className="text-sm font-medium text-red-800"
                      data-testid="exception-reason"
                    >
                      Amount mismatch detected
                    </div>
                    <div className="text-sm text-red-700/90 mt-1">
                      Party A reports ₹{partyAAmount}, Party B reports ₹
                      {partyBAmount}. Settlement paused pending reconciliation.
                    </div>
                  </div>
                </div>
              </SectionCard>
            )}

            {/* 5. Evidence */}
            <SectionCard
              step={isConsistent ? "4" : "5"}
              title="Evidence"
              description="Generate and verify a tamper-evident proof artifact for this transaction."
              testId="section-evidence"
              tone={
                verifyStatus === "verified"
                  ? "success"
                  : verifyStatus === "tampered"
                  ? "error"
                  : "info"
              }
            >
              {!proof ? (
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div className="text-sm text-gray-600">
                    Create a cryptographically verifiable record of this
                    transaction. No raw data is exposed.
                  </div>
                  <Button
                    onClick={generateProof}
                    disabled={generating}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-medium"
                    data-testid="generate-proof-btn"
                  >
                    {generating ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <FileSignature className="w-4 h-4 mr-2" />
                    )}
                    Generate Proof Artifact
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="rounded-lg bg-gray-50 border border-gray-100 divide-y divide-gray-100">
                    <ProofRow
                      label="Proof ID"
                      value={shortHash(proof.proof_hash)}
                      full={proof.proof_hash}
                      testId="proof-id"
                    />
                    <ProofRow
                      label="Issued at"
                      value={formatTs(proof.issued_at)}
                      testId="proof-timestamp"
                    />
                    <ProofRow
                      label="Algorithm"
                      value={proof.metadata.algorithm}
                      testId="proof-algorithm"
                    />
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div
                      className="text-sm"
                      data-testid="verify-status-text"
                    >
                      {verifyStatus === "verified" && (
                        <span className="inline-flex items-center gap-2 text-emerald-700 font-medium">
                          <CheckCircle2 className="w-4 h-4" />
                          Proof Verified — Data Untampered
                        </span>
                      )}
                      {verifyStatus === "tampered" && (
                        <span className="inline-flex items-center gap-2 text-red-700 font-medium">
                          <AlertTriangle className="w-4 h-4" />
                          Verification failed — data may be tampered
                        </span>
                      )}
                      {!verifyStatus && (
                        <span className="text-gray-500">
                          Proof artifact ready. Run verification to confirm
                          integrity.
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={generateProof}
                        disabled={generating}
                        className="border-gray-200 text-gray-700 hover:bg-gray-50"
                        data-testid="regenerate-proof-btn"
                      >
                        Regenerate
                      </Button>
                      <Button
                        onClick={verifyProof}
                        disabled={verifying}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium"
                        data-testid="verify-proof-btn"
                      >
                        {verifying ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        ) : (
                          <ShieldCheck className="w-4 h-4 mr-2" />
                        )}
                        Verify Proof
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </SectionCard>
          </>
        )}

        {/* Footer */}
        <footer className="pt-8 mt-4 border-t border-gray-200 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-gray-500">
          <span>Ed25519 · SHA-256 · Deterministic canonicalization</span>
          <span className="ml-auto">
            Proof artifacts verifiable without access to raw data
          </span>
        </footer>
      </main>
    </div>
  );
}

/* ------------------------------ sub components ---------------------------- */

function FieldInput({ label, value, onChange, testId, mono, prefix }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
        {label}
      </Label>
      <div className="relative">
        {prefix && (
          <span className="absolute inset-y-0 left-3 flex items-center text-gray-400 text-sm font-mono">
            {prefix}
          </span>
        )}
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`bg-white border-gray-200 text-gray-900 h-10 ${
            prefix ? "pl-7" : ""
          } ${mono ? "font-mono text-sm" : ""} focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:border-blue-400`}
          data-testid={testId}
        />
      </div>
    </div>
  );
}

function PartyPanel({ name, subtitle, amount, diverged, testId }) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        diverged
          ? "border-red-200 bg-red-50/40"
          : "border-gray-200 bg-gray-50"
      }`}
      data-testid={testId}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-gray-900">{name}</div>
          <div className="text-xs text-gray-500">{subtitle}</div>
        </div>
        <div
          className={`text-lg font-semibold font-mono ${
            diverged ? "text-red-700" : "text-gray-900"
          }`}
          data-testid={`${testId}-amount`}
        >
          ₹{amount}
        </div>
      </div>
    </div>
  );
}

function ProofRow({ label, value, full, testId }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-xs uppercase tracking-wide text-gray-500">
        {label}
      </span>
      <span
        className="text-sm font-mono text-gray-900 truncate max-w-[60%] text-right"
        title={full || value}
        data-testid={testId}
      >
        {value}
      </span>
    </div>
  );
}
