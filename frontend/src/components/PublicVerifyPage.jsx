import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  ShieldCheck,
  Upload,
  ClipboardPaste,
  CheckCircle2,
  AlertTriangle,
  Search,
  FileText,
  Loader2,
  ArrowLeft,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatTs = (iso) => {
  if (!iso) return "";
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

export default function PublicVerifyPage() {
  const [rawJson, setRawJson] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  const canVerify = useMemo(() => rawJson.trim().length > 0, [rawJson]);

  const handleFile = async (file) => {
    if (!file) return;
    try {
      const text = await file.text();
      setRawJson(text);
      setResult(null);
      toast.success(`Loaded ${file.name}`);
    } catch {
      toast.error("Failed to read file");
    }
  };

  const onFileInput = (e) => {
    const file = e.target.files?.[0];
    handleFile(file);
    e.target.value = "";
  };

  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const verify = async () => {
    setResult(null);
    setVerifying(true);
    let parsed;
    try {
      parsed = JSON.parse(rawJson);
    } catch (e) {
      setVerifying(false);
      setResult({
        valid: false,
        status: "invalid",
        reason: "Malformed JSON — could not parse the artifact",
      });
      return;
    }
    try {
      const { data } = await axios.post(`${API}/demo/artifact/verify`, parsed);
      setResult(data);
    } catch (e) {
      setResult({
        valid: false,
        status: "invalid",
        reason:
          e?.response?.data?.detail || e?.message || "Verification request failed",
      });
    } finally {
      setVerifying(false);
    }
  };

  const clearAll = () => {
    setRawJson("");
    setResult(null);
  };

  return (
    <div
      className="min-h-screen bg-white text-gray-900"
      data-testid="public-verify-page"
    >
      {/* Top Nav */}
      <header className="border-b border-gray-200 bg-white sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-3 hover:opacity-80"
            data-testid="back-home-link"
          >
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-gray-900">
                Proof Fabric Protocol
              </div>
              <div className="text-xs text-gray-500">
                Independent Proof Verification
              </div>
            </div>
          </Link>
          <Link
            to="/"
            className="text-xs text-gray-600 hover:text-gray-900 inline-flex items-center gap-1.5"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to dashboard
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-10 pb-6">
        <h1
          className="text-3xl sm:text-4xl font-semibold tracking-tight text-gray-900 font-['Space_Grotesk']"
          data-testid="verify-page-title"
        >
          Verify a Proof Artifact
        </h1>
        <p className="mt-3 text-base text-gray-600 max-w-2xl">
          Upload or paste a signed proof artifact (JSON) to verify it
          independently. No transaction data is re-entered and no internal
          systems are queried.
        </p>
      </section>

      <main className="max-w-4xl mx-auto px-6 pb-20 space-y-5">
        {/* Input */}
        <Card className="bg-white border-gray-200 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-gray-900 tracking-tight">
              Proof artifact
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              onDrop={onDrop}
              onDragOver={onDragOver}
              className="rounded-lg border-2 border-dashed border-gray-200 p-5 bg-gray-50/60 hover:bg-gray-50 transition-colors"
              data-testid="drop-zone"
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-md bg-white border border-gray-200 flex items-center justify-center">
                    <FileText className="w-5 h-5 text-gray-500" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-800">
                      Drop a proof file here
                    </div>
                    <div className="text-xs text-gray-500">
                      or choose a file · accepts{" "}
                      <code className="font-mono">.json</code>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".json,application/json,application/pfp-proof+json"
                    onChange={onFileInput}
                    className="hidden"
                    data-testid="file-input"
                  />
                  <Button
                    variant="outline"
                    onClick={() => fileRef.current?.click()}
                    className="border-gray-200 text-gray-700 hover:bg-gray-100"
                    data-testid="upload-file-btn"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Upload JSON
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={async () => {
                      try {
                        const text = await navigator.clipboard.readText();
                        if (!text?.trim()) {
                          toast.error("Clipboard is empty");
                          return;
                        }
                        setRawJson(text);
                        setResult(null);
                        toast.success("Pasted from clipboard");
                      } catch {
                        toast.error(
                          "Could not read clipboard — paste into the box below"
                        );
                      }
                    }}
                    className="text-gray-700 hover:bg-gray-100"
                    data-testid="paste-clipboard-btn"
                  >
                    <ClipboardPaste className="w-4 h-4 mr-2" />
                    Paste
                  </Button>
                </div>
              </div>
            </div>

            <Textarea
              value={rawJson}
              onChange={(e) => {
                setRawJson(e.target.value);
                if (result) setResult(null);
              }}
              placeholder='Paste the signed artifact JSON here, e.g. { "version": 1, "transaction_id": "...", ..., "signature": "..." }'
              className="min-h-[220px] font-mono text-xs bg-white border-gray-200 text-gray-900 focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:border-blue-400"
              data-testid="json-textarea"
            />

            <div className="flex items-center justify-between">
              <Button
                variant="ghost"
                onClick={clearAll}
                disabled={!rawJson && !result}
                className="text-gray-500 hover:text-gray-800"
                data-testid="clear-btn"
              >
                Clear
              </Button>
              <Button
                onClick={verify}
                disabled={!canVerify || verifying}
                className="bg-blue-600 hover:bg-blue-700 text-white font-medium"
                data-testid="verify-proof-btn"
              >
                {verifying ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Search className="w-4 h-4 mr-2" />
                )}
                Verify Proof
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Result */}
        {result && <VerifyResult result={result} />}

        {/* Note */}
        <p
          className="text-xs text-gray-500 max-w-3xl leading-relaxed"
          data-testid="verify-note"
        >
          This verification is performed independently using the proof artifact,
          digital signature, key ID, version, canonical ordering, normalization,
          timestamp validation, and constant-time checks — without querying
          internal systems.
        </p>
      </main>
    </div>
  );
}

function VerifyResult({ result }) {
  const { valid, status, reason, extracted } = result;
  const headline =
    status === "valid_compliant"
      ? "Valid Proof — Data Untampered"
      : status === "valid_non_compliant"
      ? "Valid Proof — Transaction flagged as NON-COMPLIANT"
      : "Invalid Proof — Verification Failed";

  const tone = !valid
    ? "bg-red-50 border-red-200 text-red-800"
    : status === "valid_compliant"
    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
    : "bg-red-50 border-red-200 text-red-800";

  const Icon = !valid
    ? AlertTriangle
    : status === "valid_compliant"
    ? CheckCircle2
    : AlertTriangle;

  return (
    <Card className="bg-white border-gray-200 shadow-sm" data-testid="verify-result">
      <CardContent className="p-5">
        <div className={`rounded-lg border ${tone} p-4`}>
          <div
            className="flex items-center gap-2 text-sm font-semibold"
            data-testid="verify-result-headline"
          >
            <Icon className="w-4 h-4" />
            {headline}
          </div>
          {!valid && reason && (
            <div
              className="mt-1.5 text-xs"
              data-testid="verify-result-reason"
            >
              {reason}
            </div>
          )}
        </div>

        {extracted && (
          <div
            className="mt-4 rounded-md border border-gray-200 divide-y divide-gray-100 overflow-hidden"
            data-testid="verify-extracted"
          >
            <Row label="Transaction ID" value={extracted.transaction_id} />
            <Row
              label="KYC"
              value={extracted.compliance.kyc}
              valueClass={
                extracted.compliance.kyc === "Pass"
                  ? "text-emerald-700"
                  : "text-red-700"
              }
              testId="extracted-kyc"
            />
            <Row
              label="AML"
              value={extracted.compliance.aml}
              valueClass={
                extracted.compliance.aml === "Pass"
                  ? "text-emerald-700"
                  : "text-red-700"
              }
              testId="extracted-aml"
            />
            <Row
              label="Transaction Amount Limit"
              value={extracted.compliance.limits}
              valueClass={
                extracted.compliance.limits === "Within allowed range"
                  ? "text-emerald-700"
                  : "text-red-700"
              }
              testId="extracted-limits"
            />
            <Row
              label="Timestamp"
              value={formatTs(extracted.timestamp)}
              testId="extracted-timestamp"
            />
            <Row
              label="Key ID"
              value={extracted.kid}
              valueClass="font-mono text-xs"
              testId="extracted-kid"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Row({ label, value, valueClass = "text-gray-900", testId }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 bg-white">
      <span className="text-xs uppercase tracking-wide text-gray-500">
        {label}
      </span>
      <span
        className={`text-sm ${valueClass} text-right truncate max-w-[65%]`}
        data-testid={testId}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}
