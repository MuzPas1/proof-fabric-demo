import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Link } from "react-router-dom";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { buildVerifyUrl } from "@/lib/proofLink";
import {
  CheckCircle2,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  Loader2,
  RotateCcw,
  BadgeCheck,
  Lock,
  Scale,
  GitCompareArrows,
  Share2,
  Copy,
  Search,
  Download,
  ExternalLink,
  Link2,
  ClipboardCopy,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const DEFAULTS = {
  transaction_id: "TXN-8F2C-2026-00418",
  user_id: "user_92341",
  amount: "2450.00",
};

const nowIso = () => new Date().toISOString();

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

/* --------------------------------- UI bits -------------------------------- */

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
    status === "success"
      ? CheckCircle2
      : status === "error"
      ? AlertTriangle
      : null;
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

function CheckRow({ icon: Icon, label, value, status = "success", testId }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-2.5 text-sm text-gray-700">
        <Icon className="w-4 h-4 text-gray-400" />
        <span>{label}</span>
      </div>
      <StatusPill status={status} label={value} testId={testId} />
    </div>
  );
}

/* ----------------------------- main component ----------------------------- */

export default function TransactionFlow() {
  const [form, setForm] = useState(DEFAULTS);
  const [processed, setProcessed] = useState(false);
  const [processing, setProcessing] = useState(false);

  // Compliance toggle
  const [simulateComplianceFail, setSimulateComplianceFail] = useState(false);

  // Evidence (proof from /api/demo/issue)
  const [proof, setProof] = useState(null); // { proof_id, transaction_id, issued_at, compliance }

  // Auditor verification
  const [auditorProofId, setAuditorProofId] = useState("");
  const [auditorResult, setAuditorResult] = useState(null); // VerifyByIdResponse
  const [verifying, setVerifying] = useState(false);

  // Consistency + exception
  const [mismatch, setMismatch] = useState(false);

  const complianceState = simulateComplianceFail
    ? {
        kyc: "Fail",
        aml: "Pass",
        limits: "Within allowed range",
        status: "NON-COMPLIANT",
      }
    : {
        kyc: "Pass",
        aml: "Pass",
        limits: "Within allowed range",
        status: "COMPLIANT",
      };

  const isCompliant = complianceState.status === "COMPLIANT";

  const canProcess =
    form.transaction_id.trim() &&
    form.user_id.trim() &&
    String(form.amount).trim() &&
    !isNaN(Number(form.amount));

  const handleInput = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (processed) {
      // edited after processing — invalidate downstream
      setProcessed(false);
      setProof(null);
      setAuditorResult(null);
      setAuditorProofId("");
      setMismatch(false);
    }
  };

  const processTransaction = async () => {
    if (!canProcess) {
      toast.error("Please fill all fields with valid values.");
      return;
    }
    setProcessing(true);
    setProof(null);
    setAuditorResult(null);
    try {
      // small UX delay to make the "checks running" feel weighty
      await new Promise((r) => setTimeout(r, 300));
      const { data } = await axios.post(`${API}/demo/issue`, {
        transaction_id: form.transaction_id,
        user_id: form.user_id,
        amount: form.amount,
        created_at: nowIso(),
        compliance: complianceState,
      });
      setProof({ ...data, compliance: complianceState });
      setAuditorProofId(data.proof_id); // pre-fill for demo convenience
      setProcessed(true);
      toast.success(
        `Transaction processed — proof issued (${isCompliant ? "compliant" : "non-compliant"})`
      );
    } catch (e) {
      const detail =
        e?.response?.data?.detail || e?.message || "Failed to process transaction";
      toast.error(detail);
    } finally {
      setProcessing(false);
    }
  };

  const copyProofId = async () => {
    if (!proof?.proof_id) return;
    try {
      await navigator.clipboard.writeText(proof.proof_id);
      toast.success("Proof ID copied to clipboard");
    } catch {
      toast.error("Unable to copy");
    }
  };

  const shareProof = async () => {
    if (!proof?.proof_id) return;
    const shareText = `Proof ID: ${proof.proof_id}\nTransaction: ${proof.transaction_id}\nIssued: ${proof.issued_at}`;
    if (navigator.share) {
      try {
        await navigator.share({
          title: "Proof Fabric Protocol — Evidence Artifact",
          text: shareText,
        });
        return;
      } catch {
        /* fall through */
      }
    }
    try {
      await navigator.clipboard.writeText(shareText);
      toast.success("Proof details copied — paste to share");
    } catch {
      toast.error("Unable to share");
    }
  };

  const [downloading, setDownloading] = useState(false);
  const [copyingLink, setCopyingLink] = useState(false);
  const [tooLargeOpen, setTooLargeOpen] = useState(false);
  const [tooLargeArtifact, setTooLargeArtifact] = useState(null); // raw JSON string

  /** Fetch the signed artifact JSON (raw text). Used by both download + link. */
  const fetchSignedArtifactJson = async () => {
    const { data, headers } = await axios.post(
      `${API}/demo/artifact`,
      {
        transaction_id: form.transaction_id,
        user_id: form.user_id,
        amount: form.amount,
        compliance: complianceState,
      },
      { responseType: "text", transformResponse: (t) => t }
    );
    return {
      jsonText: data,
      contentType:
        headers?.["content-type"] || "application/pfp-proof+json;v=1",
    };
  };

  const triggerDownload = (jsonText, contentType) => {
    const blob = new Blob([jsonText], { type: contentType });
    let proofId = "";
    try {
      proofId = JSON.parse(jsonText).proof_id || "";
    } catch {
      /* ignore */
    }
    const fname = proofId
      ? `pfp-proof-${proofId.slice(0, 16)}.json`
      : "pfp-proof.json";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fname;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadSignedArtifact = async () => {
    if (!proof) return;
    setDownloading(true);
    try {
      const { jsonText, contentType } = await fetchSignedArtifactJson();
      triggerDownload(jsonText, contentType);
      toast.success("Proof artifact downloaded");
    } catch (e) {
      const detail =
        e?.response?.data?.detail || e?.message || "Download failed";
      toast.error(detail);
    } finally {
      setDownloading(false);
    }
  };

  const copyVerificationLink = async () => {
    if (!proof) return;
    setCopyingLink(true);
    try {
      const { jsonText } = await fetchSignedArtifactJson();
      const { url, tooLong } = buildVerifyUrl(jsonText);

      if (tooLong) {
        setTooLargeArtifact(jsonText);
        setTooLargeOpen(true);
        return;
      }

      try {
        await navigator.clipboard.writeText(url);
        toast.success("Verification link copied to clipboard");
      } catch {
        // Clipboard blocked — surface the URL via the too-large modal as a
        // fallback so the user can still grab it manually.
        setTooLargeArtifact(url);
        setTooLargeOpen(true);
      }
    } catch (e) {
      const detail =
        e?.response?.data?.detail ||
        e?.message ||
        "Failed to build verification link";
      toast.error(detail);
    } finally {
      setCopyingLink(false);
    }
  };

  const runAuditorVerification = async () => {
    const pid = auditorProofId.trim();
    if (!pid) {
      toast.error("Enter a Proof ID to verify.");
      return;
    }
    setVerifying(true);
    setAuditorResult(null);
    try {
      await new Promise((r) => setTimeout(r, 350));
      const { data } = await axios.get(`${API}/demo/verify/${pid}`);
      setAuditorResult(data);
    } catch (e) {
      setAuditorResult({
        valid: false,
        proof_id: pid,
        reason: e?.response?.data?.detail || "Verification request failed",
      });
    } finally {
      setVerifying(false);
    }
  };

  const resetAll = () => {
    setForm(DEFAULTS);
    setProcessed(false);
    setProcessing(false);
    setSimulateComplianceFail(false);
    setProof(null);
    setAuditorProofId("");
    setAuditorResult(null);
    setMismatch(false);
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
          Convert transactions into verifiable proof.
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

        {/* 2. Compliance */}
        <SectionCard
          step="2"
          title="Compliance Checks"
          description="Automated KYC, AML and transaction limit verification."
          testId="section-compliance"
          tone={processed ? (isCompliant ? "success" : "error") : "neutral"}
          rightSlot={
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Label
                  htmlFor="compliance-toggle"
                  className="text-xs text-gray-500"
                >
                  Simulate Compliance Failure
                </Label>
                <Switch
                  id="compliance-toggle"
                  checked={simulateComplianceFail}
                  onCheckedChange={(v) => {
                    setSimulateComplianceFail(v);
                    if (processed) {
                      setProcessed(false);
                      setProof(null);
                      setAuditorResult(null);
                      setAuditorProofId("");
                    }
                  }}
                  data-testid="compliance-toggle"
                />
              </div>
              {processed && (
                <StatusPill
                  status={isCompliant ? "success" : "error"}
                  label={isCompliant ? "Compliant" : "Non-Compliant"}
                  testId="compliance-overall-badge"
                />
              )}
            </div>
          }
        >
          <div className="rounded-lg bg-gray-50 border border-gray-100 px-4 py-2">
            <CheckRow
              icon={BadgeCheck}
              label="KYC verification"
              value={complianceState.kyc}
              status={complianceState.kyc === "Pass" ? "success" : "error"}
              testId="compliance-kyc"
            />
            <CheckRow
              icon={Lock}
              label="AML screening"
              value={complianceState.aml}
              status={complianceState.aml === "Pass" ? "success" : "error"}
              testId="compliance-aml"
            />
            <CheckRow
              icon={Scale}
              label="Transaction amount limit"
              value={complianceState.limits}
              status={
                complianceState.limits === "Within allowed range"
                  ? "success"
                  : "error"
              }
              testId="compliance-limits"
            />
          </div>
          <p
            className={`text-sm font-medium mt-4 ${
              isCompliant ? "text-emerald-700" : "text-red-700"
            }`}
            data-testid="compliance-summary"
          >
            {isCompliant
              ? "Transaction is COMPLIANT"
              : "KYC Fail — Transaction is NON-COMPLIANT"}
          </p>
        </SectionCard>

        {/* 3. Evidence (auto after process) */}
        {processed && proof && (
          <SectionCard
            step="3"
            title="Evidence"
            description="A cryptographically verifiable proof artifact has been issued for this transaction."
            testId="section-evidence"
            tone={isCompliant ? "success" : "error"}
            rightSlot={
              <StatusPill
                status={isCompliant ? "success" : "error"}
                label={isCompliant ? "Proof Issued" : "Flagged"}
                testId="evidence-status-badge"
              />
            }
          >
            <div className="rounded-lg bg-gray-50 border border-gray-100 divide-y divide-gray-100">
              <ProofRow
                label="Transaction ID"
                value={proof.transaction_id}
                testId="evidence-transaction-id"
              />
              <ProofRow
                label="Proof ID"
                value={shortHash(proof.proof_id)}
                full={proof.proof_id}
                testId="evidence-proof-id"
                action={
                  <button
                    onClick={copyProofId}
                    className="text-gray-400 hover:text-gray-700 transition-colors"
                    data-testid="copy-proof-id-btn"
                    aria-label="Copy Proof ID"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                }
              />
              <ProofRow
                label="Issued at"
                value={formatTs(proof.issued_at)}
                testId="evidence-timestamp"
              />
            </div>

            <div
              className={`mt-4 flex items-center gap-2 text-sm font-medium ${
                isCompliant ? "text-emerald-700" : "text-red-700"
              }`}
              data-testid="evidence-verification-status"
            >
              {isCompliant ? (
                <CheckCircle2 className="w-4 h-4" />
              ) : (
                <AlertTriangle className="w-4 h-4" />
              )}
              {isCompliant
                ? "Proof Verified — Data Untampered"
                : "Proof Verified — Transaction flagged as NON-COMPLIANT"}
            </div>

            <p
              className="text-xs text-gray-500 mt-2"
              data-testid="evidence-tamper-note"
            >
              This proof is cryptographically generated, independently
              verifiable, and cannot be altered.
            </p>

            <div className="mt-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <p className="text-sm text-gray-600">
                Share this proof with auditors or external systems for
                independent verification.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={downloadSignedArtifact}
                  disabled={downloading}
                  className="border-gray-200 text-gray-700 hover:bg-gray-50"
                  data-testid="download-proof-btn"
                >
                  {downloading ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Download className="w-4 h-4 mr-2" />
                  )}
                  Download Proof
                </Button>
                <Button
                  variant="outline"
                  onClick={copyVerificationLink}
                  disabled={copyingLink}
                  className="border-gray-200 text-gray-700 hover:bg-gray-50"
                  data-testid="copy-verification-link-btn"
                >
                  {copyingLink ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Link2 className="w-4 h-4 mr-2" />
                  )}
                  Copy Verification Link
                </Button>
                <Button
                  onClick={shareProof}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-medium"
                  data-testid="share-proof-btn"
                >
                  <Share2 className="w-4 h-4 mr-2" />
                  Share Proof
                </Button>
              </div>
            </div>

            <div className="mt-3 text-xs text-gray-500">
              Downloaded proof can be verified anywhere using the{" "}
              <Link
                to="/verify"
                className="text-blue-600 hover:text-blue-700 inline-flex items-center gap-1"
                data-testid="open-public-verify-link"
              >
                public verifier
                <ExternalLink className="w-3 h-3" />
              </Link>
              .
            </div>
            <div
              className="mt-1.5 text-xs text-gray-400"
              data-testid="link-security-note"
            >
              This link contains the full proof artifact. Share only with
              intended recipients.
            </div>
          </SectionCard>
        )}

        {/* 4. Auditor / External Verification */}
        <SectionCard
          step="4"
          title="Auditor Verification"
          description="Verify any issued proof using only its Proof ID — no transaction data required."
          testId="section-auditor"
          tone={
            auditorResult
              ? auditorResult.valid
                ? auditorResult.compliance?.status === "COMPLIANT"
                  ? "success"
                  : "error"
                : "error"
              : "neutral"
          }
        >
          <div className="flex flex-col sm:flex-row gap-3">
            <Input
              placeholder="Paste Proof ID (64-character hash)"
              value={auditorProofId}
              onChange={(e) => setAuditorProofId(e.target.value)}
              className="bg-white border-gray-200 font-mono text-sm flex-1 focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:border-blue-400"
              data-testid="auditor-proof-id-input"
            />
            <Button
              onClick={runAuditorVerification}
              disabled={verifying || !auditorProofId.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium"
              data-testid="auditor-verify-btn"
            >
              {verifying ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Search className="w-4 h-4 mr-2" />
              )}
              Verify External Proof
            </Button>
          </div>

          {auditorResult && (
            <div className="mt-5" data-testid="auditor-result">
              <AuditorResult result={auditorResult} />
            </div>
          )}

          <p className="text-xs text-gray-500 mt-4" data-testid="auditor-note">
            Verification is performed using cryptographic proof, not by
            re-entering transaction data.
          </p>
        </SectionCard>

        {/* 5. Consistency */}
        {processed && proof && (
          <SectionCard
            step="5"
            title="Cross-Party Consistency"
            description="Compare the transaction record as seen by both parties."
            testId="section-consistency"
            tone={mismatch ? "error" : "success"}
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
                subtitle="Client · ABCPay"
                amount={form.amount}
                testId="party-a-panel"
              />
              <PartyPanel
                name="Party B"
                subtitle="Bank · HDFC"
                amount={
                  mismatch
                    ? (Number(form.amount) + 100).toFixed(2)
                    : form.amount
                }
                diverged={mismatch}
                testId="party-b-panel"
              />
            </div>
            <div className="mt-4 flex items-center justify-between">
              <div className="text-sm text-gray-600 flex items-center gap-2">
                <GitCompareArrows className="w-4 h-4 text-gray-400" />
                Comparing records across parties
              </div>
              <StatusPill
                status={mismatch ? "error" : "success"}
                label={mismatch ? "MISMATCH DETECTED" : "CONSISTENT"}
                testId="consistency-status"
              />
            </div>
          </SectionCard>
        )}

        {/* 6. Exception (only on mismatch) */}
        {processed && proof && mismatch && (
          <SectionCard
            step="6"
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
                  Party A reports ₹{form.amount}, Party B reports ₹
                  {(Number(form.amount) + 100).toFixed(2)}. Settlement paused
                  pending reconciliation.
                </div>
              </div>
            </div>
          </SectionCard>
        )}

        {/* Footer */}
        <footer className="pt-8 mt-4 border-t border-gray-200 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-gray-500">
          <span>Ed25519 · SHA-256 · Deterministic canonicalization</span>
          <span className="ml-auto">
            Proof artifacts verifiable without access to raw data
          </span>
        </footer>
      </main>

      {/* Too-large fallback dialog */}
      <Dialog open={tooLargeOpen} onOpenChange={setTooLargeOpen}>
        <DialogContent
          className="bg-white border-gray-200"
          data-testid="too-large-dialog"
        >
          <DialogHeader>
            <DialogTitle className="text-gray-900">
              Proof too large for link — use file sharing
            </DialogTitle>
            <DialogDescription className="text-gray-500">
              This proof exceeds the safe URL size. Send it as a file or paste
              the JSON directly instead.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(tooLargeArtifact || "");
                  toast.success("Proof JSON copied to clipboard");
                  setTooLargeOpen(false);
                } catch {
                  toast.error("Could not copy — select the text manually");
                }
              }}
              className="border-gray-200 text-gray-700 hover:bg-gray-50"
              data-testid="copy-json-btn"
            >
              <ClipboardCopy className="w-4 h-4 mr-2" />
              Copy JSON
            </Button>
            <Button
              onClick={() => {
                if (tooLargeArtifact) {
                  triggerDownload(
                    tooLargeArtifact,
                    "application/pfp-proof+json;v=1"
                  );
                  setTooLargeOpen(false);
                }
              }}
              className="bg-blue-600 hover:bg-blue-700 text-white"
              data-testid="too-large-download-btn"
            >
              <Download className="w-4 h-4 mr-2" />
              Download Proof
            </Button>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setTooLargeOpen(false)}
              className="text-gray-500 hover:text-gray-800"
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* --------------------------- auditor result view -------------------------- */

function AuditorResult({ result }) {
  const { valid, compliance, transaction_id, issued_at, reason } = result;
  const isCompliant = valid && compliance?.status === "COMPLIANT";
  const isNonCompliantValid = valid && compliance?.status === "NON-COMPLIANT";

  const headline = !valid
    ? "Invalid Proof — Verification Failed"
    : isCompliant
    ? "Valid Proof — Data Untampered"
    : "Valid Proof — Transaction flagged as NON-COMPLIANT";

  const tone = !valid
    ? "bg-red-50 border-red-200 text-red-800"
    : isCompliant
    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
    : "bg-red-50 border-red-200 text-red-800";

  const Icon = !valid
    ? AlertTriangle
    : isCompliant
    ? CheckCircle2
    : AlertTriangle;

  return (
    <div className={`rounded-lg border ${tone} p-4`}>
      <div
        className="flex items-center gap-2 text-sm font-semibold"
        data-testid="auditor-result-headline"
      >
        <Icon className="w-4 h-4" />
        {headline}
      </div>

      {!valid && reason && (
        <div className="mt-1 text-xs" data-testid="auditor-result-reason">
          {reason}
        </div>
      )}

      {(valid || compliance) && (
        <div className="mt-4 rounded-md bg-white/80 border border-white/60 divide-y divide-gray-100 backdrop-blur-sm">
          {transaction_id && (
            <ProofRow
              label="Transaction ID"
              value={transaction_id}
              testId="auditor-transaction-id"
              borderless
            />
          )}
          {compliance && (
            <>
              <ProofRow
                label="KYC"
                value={compliance.kyc}
                testId="auditor-kyc"
                borderless
                valueClass={
                  compliance.kyc === "Pass"
                    ? "text-emerald-700"
                    : "text-red-700"
                }
              />
              <ProofRow
                label="AML"
                value={compliance.aml}
                testId="auditor-aml"
                borderless
                valueClass={
                  compliance.aml === "Pass"
                    ? "text-emerald-700"
                    : "text-red-700"
                }
              />
              <ProofRow
                label="Transaction Amount Limit"
                value={compliance.limits}
                testId="auditor-limits"
                borderless
                valueClass={
                  compliance.limits === "Within allowed range"
                    ? "text-emerald-700"
                    : "text-red-700"
                }
              />
            </>
          )}
          {issued_at && (
            <ProofRow
              label="Issued at"
              value={formatTs(issued_at)}
              testId="auditor-issued-at"
              borderless
            />
          )}
        </div>
      )}
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
        diverged ? "border-red-200 bg-red-50/40" : "border-gray-200 bg-gray-50"
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

function ProofRow({
  label,
  value,
  full,
  testId,
  action,
  borderless,
  valueClass = "text-gray-900",
}) {
  return (
    <div
      className={`flex items-center justify-between px-4 py-3 ${
        borderless ? "" : ""
      }`}
    >
      <span className="text-xs uppercase tracking-wide text-gray-500">
        {label}
      </span>
      <div className="flex items-center gap-2 max-w-[65%]">
        <span
          className={`text-sm font-mono truncate text-right ${valueClass}`}
          title={full || value}
          data-testid={testId}
        >
          {value}
        </span>
        {action}
      </div>
    </div>
  );
}
