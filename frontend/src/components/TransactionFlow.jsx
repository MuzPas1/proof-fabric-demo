import { useState, Fragment } from "react";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  INDUSTRIES,
  INDUSTRY_ORDER,
  DEFAULT_INDUSTRY,
} from "@/lib/industries";
import WorkflowBuilder from "@/components/WorkflowBuilder";
import {
  cloneStarter,
  saveTemplate,
  loadTemplate,
  encodeConfig,
  decodeConfig,
  validateConfig,
} from "@/lib/workflowConfig";
import {
  TabHowItWorks,
  TabUseCases,
  TabAiGovernance,
  TabFaq,
  TabResources,
} from "@/components/PfpOverview";
import {
  PortalSidebar,
  PortalTopBar,
  PortalRightRail,
  SessionProofsView,
  useSessionProofs,
  formatUSD,
} from "@/components/PortalShell";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  CheckCircle2,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  Loader2,
  RotateCcw,
  GitCompareArrows,
  Share2,
  Copy,
  Search,
  Download,
  ExternalLink,
  Link2,
  ClipboardCopy,
  Code,
  BookOpen,
  Sparkles,
  Award,
  Bot,
  Cpu,
  Users,
  Clock,
  Workflow,
  UserCheck,
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

const formatTsUTC = (iso) => {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const pad = (n) => String(n).padStart(2, "0");
    return (
      `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ` +
      `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} UTC`
    );
  } catch {
    return iso;
  }
};

const shortHash = (h) => (h ? `${h.slice(0, 16)}...${h.slice(-8)}` : "");

/** Read a shared workflow config from the current URL (?config=...). */
const readUrlConfig = () => {
  try {
    const c = new URLSearchParams(window.location.search).get("config");
    return c ? decodeConfig(c) : null;
  } catch {
    return null;
  }
};

/* --------------------------------- UI bits -------------------------------- */

function SectionCard({
  step,
  title,
  description,
  tone = "neutral",
  children,
  testId,
  rightSlot,
  accent,
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

  // Visual emphasis for "core product" sections (e.g., Evidence)
  const accentRing =
    accent === "primary"
      ? tone === "neutral"
        ? "ring-1 ring-blue-100 shadow-blue-50"
        : tone === "success"
        ? "ring-2 ring-emerald-100"
        : tone === "error"
        ? "ring-2 ring-red-100"
        : ""
      : "";

  const accentTitle = accent === "primary" ? "text-lg" : "text-base";

  return (
    <Card
      className={`bg-white ${toneRing} ${accentRing} shadow-sm hover:shadow-md transition-shadow`}
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
              <CardTitle
                className={`${accentTitle} font-semibold text-gray-900 tracking-tight`}
              >
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

function ComplianceCheckRow({ name, desc, status = "success", testId }) {
  const Icon = status === "success" ? CheckCircle2 : AlertTriangle;
  const iconClass =
    status === "success" ? "text-emerald-600" : "text-red-600";
  return (
    <div
      className="flex items-start justify-between gap-4 py-3 border-b border-gray-100 last:border-0"
      data-testid={testId}
    >
      <div className="flex items-start gap-2.5 min-w-0">
        <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${iconClass}`} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-gray-900 leading-snug">
            {name}
          </div>
          {desc && (
            <div
              className="text-xs text-gray-500 mt-0.5 leading-relaxed"
              data-testid={`${testId}-desc`}
            >
              {desc}
            </div>
          )}
        </div>
      </div>
      <StatusPill
        status={status}
        label={status === "success" ? "Pass" : "Fail"}
        testId={`${testId}-status`}
      />
    </div>
  );
}

/* ----------------------------- main component ----------------------------- */

export default function TransactionFlow() {
  const [form, setForm] = useState(DEFAULTS);
  const [processed, setProcessed] = useState(false);
  const [processing, setProcessing] = useState(false);

  // Portal information architecture: product (Demo) first, education secondary.
  const [activeTab, setActiveTab] = useState("demo");

  // Session-scoped proof history (localStorage — no backend, no fake data).
  const { proofs: sessionProofs, addProof, clear: clearSessionProofs } =
    useSessionProofs();

  // Industry context (presentation-only — backend payload is unchanged)
  const [industryId, setIndustryId] = useState(() =>
    readUrlConfig() ? "generic_builder" : DEFAULT_INDUSTRY
  );
  const industry = INDUSTRIES[industryId] || INDUSTRIES[DEFAULT_INDUSTRY];
  const isCustomForm = Array.isArray(industry.fields) && industry.fields.length > 0;
  const isBuilder = industry.builder === true;

  // Generic Workflow Builder config (starter template, or shared URL config).
  const [builder, setBuilder] = useState(() => readUrlConfig() || cloneStarter());
  const builderValidation = isBuilder ? validateConfig(builder) : null;

  // Custom (industry-specific) form values — e.g. Change & Release Management.
  const buildExtraDefaults = (ind) => {
    const o = {};
    (ind.fields || []).forEach((f) => { o[f.key] = f.default ?? ""; });
    return o;
  };
  const [extra, setExtra] = useState(() => buildExtraDefaults(industry));

  // Compliance toggle
  const [simulateComplianceFail, setSimulateComplianceFail] = useState(false);

  // Evidence (proof from /api/demo/issue)
  const [proof, setProof] = useState(null); // { proof_id, transaction_id, issued_at, compliance }

  // Auditor verification
  const [auditorProofId, setAuditorProofId] = useState("");
  const [auditorResult, setAuditorResult] = useState(null); // VerifyByIdResponse
  const [auditorTrust, setAuditorTrust] = useState(null); // Trust Layer 2: { ai_provenance, time_attestation }
  const [verifying, setVerifying] = useState(false);

  // Consistency + exception
  const [mismatch, setMismatch] = useState(false);

  const complianceState = (isBuilder ? builder.simulateFailure : simulateComplianceFail)
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

  // Effective "simulate failure" flag — the Generic Workflow Builder carries
  // its own toggle in its config; other industries use the section toggle.
  const effectiveFail = isBuilder ? builder.simulateFailure : simulateComplianceFail;

  // Checks shown in the "Checks" section. For the Generic Workflow Builder
  // these come from the live builder config; otherwise from the industry preset.
  const displayedChecks = isBuilder
    ? (builderValidation?.validChecks || []).map((c) => ({
        name: c.name.trim(),
        desc: "",
      }))
    : industry.checks;

  // Canonical record sent to the proof engine. For custom-form industries the
  // industry fields are mapped onto the same {transaction_id,user_id,amount}
  // contract so the proof engine, artifact structure and Proof ID generation
  // are completely unchanged.
  const currentRecord = () => {
    if (isBuilder) {
      return {
        transaction_id: builder.workflowName.trim() || "workflow",
        user_id: "generic-workflow",
        amount: "0.00",
      };
    }
    if (isCustomForm) {
      const mt = industry.mapTo || {};
      return {
        transaction_id: (extra[mt.transaction_id] || "").trim(),
        user_id: (extra[mt.user_id] || "").trim(),
        amount: "0.00",
      };
    }
    return {
      transaction_id: form.transaction_id,
      user_id: form.user_id,
      amount: form.amount,
    };
  };

  const canProcess = isBuilder
    ? builderValidation.valid
    : isCustomForm
    ? industry.fields.every((f) => String(extra[f.key] ?? "").trim())
    : form.transaction_id.trim() &&
      form.user_id.trim() &&
      String(form.amount).trim() &&
      !isNaN(Number(form.amount));

  const invalidateDownstream = () => {
    if (processed) {
      setProcessed(false);
      setProof(null);
      setAuditorResult(null);
      setAuditorProofId("");
      setMismatch(false);
    }
  };

  const handleInput = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
    invalidateDownstream();
  };

  const handleExtra = (key, value) => {
    setExtra((e) => ({ ...e, [key]: value }));
    invalidateDownstream();
  };

  // Generic Workflow Builder: edit + browser-only persistence + share.
  const updateBuilder = (next) => {
    setBuilder(next);
    invalidateDownstream();
  };

  const handleSaveTemplate = () => {
    if (saveTemplate(builder)) toast.success("Template saved to this browser");
    else toast.error("Unable to save template");
  };

  const handleLoadTemplate = () => {
    const c = loadTemplate();
    if (!c) {
      toast.error("No saved template found in this browser");
      return;
    }
    updateBuilder(c);
    toast.success("Last saved template loaded");
  };

  const handleResetTemplate = () => {
    updateBuilder(cloneStarter());
    toast.message("Template reset to starter");
  };

  const handleShareTemplate = async () => {
    const enc = encodeConfig(builder);
    if (!enc) {
      toast.error("Unable to build a share link");
      return;
    }
    const url = `${window.location.origin}/demo?config=${enc}`;
    if (url.length > 6000) {
      toast.error("Workflow is too large to share via link");
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Share link copied to clipboard");
    } catch {
      toast.error("Unable to copy link");
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

      // Build the industry-aware check list to send alongside the canonical
      // compliance result so the auditor can later see exactly which checks
      // were executed for this industry. The first check fails when
      // "Simulate Compliance Failure" is on (mirrors the kyc/aml/limits
      // semantics carried by `complianceState`).
      let industryPayload;
      if (isBuilder) {
        // Generic Workflow Builder → feed custom workflow data into the
        // unchanged proof engine. Empty/deleted fields are excluded; the
        // visible field & check order is preserved (sent as ordered lists).
        const { validFields, validChecks } = builderValidation;
        industryPayload = {
          id: "generic_builder",
          label: builder.workflowName.trim(),
          checks: validChecks.map((c) => ({
            name: c.name.trim(),
            status: effectiveFail ? "Fail" : "Pass",
          })),
          custom_fields: validFields.map((f) => ({
            label: f.label.trim(),
            value: f.value.trim(),
          })),
        };
      } else {
        industryPayload = {
          id: industry.id,
          label: industry.label,
          checks: industry.checks.map((c, idx) => ({
            name: c.name,
            desc: c.desc,
            status: effectiveFail && idx === 0 ? "Fail" : "Pass",
          })),
        };

        // For custom-form industries, embed descriptive context (e.g. Release
        // Name / Environment) into the signed payload so it is cryptographically
        // proven and surfaced to auditors without exposing raw operational data.
        if (isCustomForm) {
          industryPayload.context = Object.fromEntries(
            industry.fields.map((f) => [f.label, String(extra[f.key] ?? "").trim()])
          );
        }
      }

      const record = currentRecord();
      const { data } = await axios.post(`${API}/demo/issue`, {
        transaction_id: record.transaction_id,
        user_id: record.user_id,
        amount: record.amount,
        created_at: nowIso(),
        compliance: complianceState,
        industry: industryPayload,
      });

      // For certificate-style industries and the Generic Workflow Builder,
      // also fetch the signed Ed25519 artifact so a real signature can be shown.
      let signature = null;
      if (industry.certificate || isBuilder) {
        try {
          const { jsonText } = await fetchSignedArtifactJson();
          signature = JSON.parse(jsonText)?.signature || null;
        } catch {
          /* signature is optional for display */
        }
      }

      setProof({ ...data, compliance: complianceState, signature });
      setAuditorProofId(data.proof_id); // pre-fill for demo convenience
      setProcessed(true);
      addProof({
        proof_id: data.proof_id,
        transaction_id: record.transaction_id,
        amount: record.amount,
        compliant: isCompliant,
        industry_label: isBuilder ? builder.workflowName.trim() : industry.label,
      });
      toast.success(
        isBuilder
          ? `Proof generated — ${isCompliant ? "Verified" : "Failed"}`
          : isCustomForm
          ? `Release Readiness Proof issued (${isCompliant ? "Ready" : "Not Ready"})`
          : `Transaction processed — proof issued (${isCompliant ? "compliant" : "non-compliant"})`
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
    const record = currentRecord();
    const { data, headers } = await axios.post(
      `${API}/demo/artifact`,
      {
        transaction_id: record.transaction_id,
        user_id: record.user_id,
        amount: record.amount,
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
    setAuditorTrust(null);
    try {
      await new Promise((r) => setTimeout(r, 350));

      // Trust Layer 2 (additive, never breaks the primary flow): the production
      // public-verify surface carries any AI provenance & independent time
      // attestation. Demo proofs simply 404 here -> trust stays null.
      let trust = null;
      try {
        const { data: pub } = await axios.get(`${API}/public/verify/${pid}`);
        trust = {
          ai_provenance: pub.ai_provenance || null,
          time_attestation: pub.time_attestation || null,
          pub,
        };
      } catch {
        /* not a production proof / no trust layer data */
      }

      // Primary verification: demo trust domain first (existing behaviour).
      let demoData = null;
      try {
        const { data } = await axios.get(`${API}/demo/verify/${pid}`);
        demoData = data;
      } catch (e) {
        demoData = e?.response?.data?.detail
          ? { valid: false, proof_id: pid, reason: e.response.data.detail }
          : null;
      }

      if (demoData && demoData.valid) {
        // A valid demo-domain proof — render the existing demo result.
        setAuditorResult(demoData);
      } else if (trust?.pub) {
        // Production proof (verified via public-verify) — render in the SAME panel.
        const p = trust.pub;
        const ts = p.fea_payload?.transaction_summary || {};
        setAuditorResult({
          valid: !!p.signature_valid,
          proof_id: pid,
          transaction_id: ts.transaction_id,
          issued_at: p.created_at,
          reason: p.signature_valid ? undefined : "Signature verification failed",
        });
      } else {
        setAuditorResult(
          demoData || {
            valid: false,
            proof_id: pid,
            reason: "Verification request failed",
          }
        );
      }
      setAuditorTrust(trust);
    } finally {
      setVerifying(false);
    }
  };

  const resetAll = () => {
    setForm(DEFAULTS);
    setExtra(buildExtraDefaults(industry));
    setBuilder(cloneStarter());
    setProcessed(false);
    setProcessing(false);
    setSimulateComplianceFail(false);
    setIndustryId(DEFAULT_INDUSTRY);
    setProof(null);
    setAuditorProofId("");
    setAuditorResult(null);
    setAuditorTrust(null);
    setMismatch(false);
    setActiveTab("demo");
    toast.message(isCustomForm ? "New release started" : "New transaction started");
  };

  const checksTotal = isBuilder
    ? (builderValidation?.validChecks || []).length
    : (industry.checks || []).length;
  const checksPassed = !processed
    ? 0
    : effectiveFail
    ? isBuilder
      ? 0
      : Math.max(checksTotal - 1, 0)
    : checksTotal;

  return (
    <div
      className="flex h-screen bg-slate-50 text-slate-900 overflow-hidden"
      data-testid="transaction-flow"
    >
      <PortalSidebar
        active={activeTab}
        onNavigate={setActiveTab}
        onNewTransaction={() => {
          resetAll();
          setActiveTab("demo");
        }}
      />

      <div className="flex-1 flex flex-col min-w-0 h-full">
        <PortalTopBar
          active={activeTab}
          onNavigate={setActiveTab}
          onNewTransaction={() => {
            resetAll();
            setActiveTab("demo");
          }}
        />

        <div className="flex-1 flex overflow-hidden">
          <div
            className="flex-1 overflow-y-auto min-w-0"
            data-testid="portal-center"
          >
            {/* Educational views */}
            {activeTab !== "demo" &&
              activeTab !== "verify" &&
              activeTab !== "proofs" && (
                <div className="p-6 max-w-4xl" data-testid="education-content">
                  {activeTab === "how" && <TabHowItWorks />}
                  {activeTab === "usecases" && <TabUseCases />}
                  {activeTab === "aigov" && <TabAiGovernance />}
                  {activeTab === "faq" && <TabFaq />}
                  {activeTab === "resources" && <TabResources />}
                </div>
              )}

            {/* Session proofs list */}
            {activeTab === "proofs" && (
              <div className="p-6" data-testid="proofs-view">
                <SessionProofsView
                  proofs={sessionProofs}
                  onOpen={(id) => {
                    setAuditorProofId(id);
                    setActiveTab("verify");
                  }}
                  onClear={clearSessionProofs}
                  onNew={() => {
                    resetAll();
                    setActiveTab("demo");
                  }}
                />
              </div>
            )}

            {/* Live Demo (primary) */}
            {activeTab === "demo" && (
            <div className="p-6 space-y-5" data-testid="demo-view">
      <section data-testid="demo-section">
        <h2
          className="text-xl font-bold tracking-tight text-slate-900 font-['Space_Grotesk']"
          data-testid="page-title"
        >
          {industry.ui?.heroTitle || "Cryptographic proof for any regulated workflow."}
        </h2>
        <p
          className="mt-1 text-sm text-slate-500 max-w-2xl"
          data-testid="page-subtitle"
        >
          {industry.ui?.heroSubtitle ||
            "This demo shows how transactions, records and events are converted into independently verifiable proof artifacts — across industries."}
        </p>

        {/* Industry context selector — primary context, immediately visible */}
        <div
          className="mt-7 rounded-xl border border-gray-200 bg-white shadow-sm px-5 py-4 sm:px-6 sm:py-5"
          data-testid="industry-selector-row"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-5">
            <div className="shrink-0">
              <Label
                htmlFor="industry-select"
                className="block text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500"
              >
                Industry
              </Label>
              <p className="mt-1 text-xs text-gray-400 hidden sm:block">
                Context for compliance checks
              </p>
            </div>

            <div className="flex-1 min-w-0">
              <Select
                value={industryId}
                onValueChange={(v) => {
                  setIndustryId(v);
                  setExtra(buildExtraDefaults(INDUSTRIES[v] || INDUSTRIES[DEFAULT_INDUSTRY]));
                  if (processed) {
                    // changing the displayed compliance ruleset invalidates
                    // the currently issued proof from a UX standpoint
                    setProcessed(false);
                    setProof(null);
                    setAuditorResult(null);
                    setAuditorProofId("");
                    setMismatch(false);
                  }
                }}
              >
                <SelectTrigger
                  id="industry-select"
                  className="w-full h-14 bg-white border-2 border-gray-200 hover:border-gray-300 text-gray-900 text-lg font-medium px-4 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 transition-colors data-[state=open]:border-blue-400"
                  data-testid="industry-select-trigger"
                >
                  <SelectValue placeholder="Select an industry" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  {INDUSTRY_ORDER.map((id) => {
                    const ind = INDUSTRIES[id];
                    return (
                      <SelectItem
                        key={id}
                        value={id}
                        className="text-base py-2.5"
                        data-testid={`industry-option-${id}`}
                      >
                        <span className="mr-2.5 text-lg leading-none">
                          {ind.emoji}
                        </span>
                        <span className="font-medium">{ind.label}</span>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
              <p
                className="mt-2 text-sm text-gray-500"
                data-testid="industry-tagline"
              >
                {industry.tagline}
              </p>
            </div>
          </div>
        </div>

        {/* Positioning + approach comparison (industry-specific) */}
        {industry.positioning && (
          <div className="mt-5" data-testid="industry-positioning">
            <div className="rounded-xl border border-blue-200 bg-blue-50/60 px-5 py-4 flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-blue-600 mt-0.5 shrink-0" />
              <p className="text-sm text-blue-900 font-medium leading-relaxed">
                {industry.positioning}
              </p>
            </div>
            {industry.approaches && (
              <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="rounded-xl border border-gray-200 bg-white px-5 py-4" data-testid="approach-traditional">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">Traditional Approach</div>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    {industry.approaches.traditional.map((s, i) => (
                      <Fragment key={s}>
                        <span className="inline-flex items-center rounded-md bg-gray-100 text-gray-600 px-2 py-1 text-xs font-medium">{s}</span>
                        {i < industry.approaches.traditional.length - 1 && <ArrowRight className="w-3 h-3 text-gray-300" />}
                      </Fragment>
                    ))}
                  </div>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 px-5 py-4" data-testid="approach-pfp">
                  <div className="text-xs font-semibold uppercase tracking-wide text-emerald-600">PFP Approach</div>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    {industry.approaches.pfp.map((s, i) => (
                      <Fragment key={s}>
                        <span className="inline-flex items-center rounded-md bg-emerald-100 text-emerald-700 px-2 py-1 text-xs font-medium">{s}</span>
                        {i < industry.approaches.pfp.length - 1 && <ArrowRight className="w-3 h-3 text-emerald-300" />}
                      </Fragment>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <main className="mt-5 space-y-5" data-testid="demo-steps">
        {/* 1. Input (industry-aware) */}
        <SectionCard
          step="1"
          title={industry.ui?.inputTitle || "Transaction"}
          description={industry.ui?.inputDesc || "Enter the transaction details to begin processing."}
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
          {isBuilder ? (
            <WorkflowBuilder
              config={builder}
              onChange={updateBuilder}
              validation={builderValidation}
              onSave={handleSaveTemplate}
              onLoad={handleLoadTemplate}
              onReset={handleResetTemplate}
              onShare={handleShareTemplate}
            />
          ) : isCustomForm ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="custom-industry-form">
              {industry.fields.map((f) =>
                f.type === "select" ? (
                  <FieldSelect
                    key={f.key}
                    label={f.label}
                    value={extra[f.key]}
                    options={f.options}
                    onChange={(v) => handleExtra(f.key, v)}
                    testId={`input-${f.key}`}
                  />
                ) : (
                  <FieldInput
                    key={f.key}
                    label={f.label}
                    value={extra[f.key]}
                    onChange={(v) => handleExtra(f.key, v)}
                    testId={`input-${f.key}`}
                    mono={f.mono}
                  />
                )
              )}
            </div>
          ) : (
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
                prefix="$"
              />
            </div>
          )}
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
              {industry.ui?.processBtn || "Process Transaction"}
            </Button>
          </div>
        </SectionCard>

        {/* 2. Compliance */}
        <SectionCard
          step="2"
          title={industry.ui?.checksTitle || "Compliance Checks"}
          description={industry.ui?.checksDesc || `Automated checks for ${industry.label}.`}
          testId="section-compliance"
          tone={processed ? (isCompliant ? "success" : "error") : "neutral"}
          rightSlot={
            <div className="flex items-center gap-3">
              {!isBuilder && (
                <div className="flex items-center gap-2">
                  <Label
                    htmlFor="compliance-toggle"
                    className="text-xs text-gray-500"
                  >
                    {industry.ui?.failToggle || "Simulate Compliance Failure"}
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
              )}
              {processed && (
                <StatusPill
                  status={isCompliant ? "success" : "error"}
                  label={
                    industry.statusLabels
                      ? isCompliant ? industry.statusLabels.pass : industry.statusLabels.fail
                      : isCompliant ? "Compliant" : "Non-Compliant"
                  }
                  testId="compliance-overall-badge"
                />
              )}
            </div>
          }
        >
          <div
            className="rounded-lg bg-gray-50 border border-gray-100 px-4 py-1"
            data-testid="compliance-checks-list"
          >
            {displayedChecks.map((c, idx) => {
              // For curated industries, simulating failure marks only the first
              // check as failed (single, clear point of divergence). For the
              // Generic Workflow Builder, Simulate Failure fails ALL checks.
              const failed = isBuilder
                ? effectiveFail
                : effectiveFail && idx === 0;
              return (
                <ComplianceCheckRow
                  key={`${industry.id}-${idx}`}
                  name={c.name}
                  desc={c.desc}
                  status={failed ? "error" : "success"}
                  testId={`compliance-check-${industry.id}-${idx}`}
                />
              );
            })}
          </div>
          <p
            className={`text-sm font-medium mt-4 ${
              isCompliant ? "text-emerald-700" : "text-red-700"
            }`}
            data-testid="compliance-summary"
          >
            {isBuilder
              ? isCompliant
                ? `All ${displayedChecks.length} checks passed — ${
                    builder.workflowName.trim() || "workflow"
                  } is VERIFIED`
                : `Checks failed — ${
                    builder.workflowName.trim() || "workflow"
                  } is NOT VERIFIED`
              : isCompliant
              ? industry.statusLabels
                ? `All checks passed — release is ${industry.statusLabels.pass.toUpperCase()}`
                : "All checks passed — workflow is COMPLIANT"
              : industry.statusLabels
              ? `${industry.checks[0].name} failed — release is ${industry.statusLabels.fail.toUpperCase()}`
              : `${industry.checks[0].name} failed — workflow is NON-COMPLIANT`}
          </p>
        </SectionCard>

        {/* 3. Evidence Generated — CORE PRODUCT (always rendered) */}
        <SectionCard
          step="3"
          title={industry.ui?.evidenceTitle || "Evidence Generated"}
          description={
            processed && proof
              ? industry.ui?.evidenceDesc ||
                "A cryptographically verifiable proof artifact has been issued for this transaction."
              : industry.ui?.evidencePlaceholder ||
                "A cryptographic proof of the processed transaction will appear here."
          }
          testId="section-evidence"
          tone={
            !processed || !proof
              ? "neutral"
              : isCompliant
              ? "success"
              : "error"
          }
          accent="primary"
          rightSlot={
            processed && proof ? (
              <StatusPill
                status={isCompliant ? "success" : "error"}
                label={isCompliant ? "Proof Generated" : "Flagged"}
                testId="evidence-status-badge"
              />
            ) : (
              <StatusPill
                status="neutral"
                label="Awaiting Transaction"
                testId="evidence-status-badge"
              />
            )
          }
        >
          {!processed || !proof ? (
            <div
              className="rounded-lg border border-dashed border-gray-200 bg-gray-50/60 px-4 py-6 text-sm text-gray-500"
              data-testid="evidence-placeholder"
            >
              {industry.ui?.evidencePlaceholder ||
                "Process a transaction above. Once compliance checks pass, a tamper-resistant proof artifact will be generated here automatically."}
            </div>
          ) : (
            <>
              <div
                className="mb-3 flex items-center gap-2"
                data-testid="proof-artifact-label"
              >
                <TooltipProvider delayDuration={150}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 cursor-help">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        Cryptographically Verifiable Proof Artifact
                      </span>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">
                      Independently verifiable evidence containing integrity,
                      provenance, accountability, and audit metadata.
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <div className="rounded-lg bg-gray-50 border border-gray-100 divide-y divide-gray-100">
                {isBuilder && (
                  <>
                    <ProofRow
                      label="Workflow Name"
                      value={builder.workflowName.trim() || "—"}
                      testId="evidence-workflow-name"
                      valueClass="text-gray-900"
                    />
                    {(builderValidation?.validFields || []).map((f, i) => (
                      <ProofRow
                        key={`evfield-${i}`}
                        label={f.label.trim()}
                        value={f.value.trim()}
                        testId={`evidence-field-${i}`}
                        valueClass="text-gray-900"
                      />
                    ))}
                    <ProofRow
                      label="Checks Passed"
                      value={`${
                        effectiveFail
                          ? 0
                          : (builderValidation?.validChecks || []).length
                      }/${(builderValidation?.validChecks || []).length}`}
                      testId="evidence-checks-passed"
                      valueClass={isCompliant ? "text-emerald-700" : "text-amber-700"}
                    />
                    <ProofRow
                      label="Status"
                      value={isCompliant ? "Verified" : "Failed"}
                      testId="evidence-status"
                      valueClass={isCompliant ? "text-emerald-700" : "text-red-700"}
                    />
                  </>
                )}
                {isCustomForm && (
                  <>
                    <ProofRow
                      label="Workflow Type"
                      value={industry.workflow || industry.label}
                      testId="evidence-workflow-type"
                      valueClass="text-gray-900"
                    />
                    <ProofRow
                      label="Release Name"
                      value={extra[industry.workflowField] || "—"}
                      testId="evidence-release-name"
                      valueClass="text-gray-900"
                    />
                    <ProofRow
                      label="Environment"
                      value={extra[industry.environmentField] || "—"}
                      testId="evidence-environment"
                      valueClass="text-gray-900"
                    />
                    <ProofRow
                      label="Status"
                      value={isCompliant ? industry.statusLabels.pass : industry.statusLabels.fail}
                      testId="evidence-status"
                      valueClass={isCompliant ? "text-emerald-700" : "text-red-700"}
                    />
                    <ProofRow
                      label="Checks Passed"
                      value={`${simulateComplianceFail ? industry.checks.length - 1 : industry.checks.length}/${industry.checks.length}`}
                      testId="evidence-checks-passed"
                      valueClass="text-gray-900"
                    />
                  </>
                )}
                {!isBuilder && (
                  <ProofRow
                    label={isCustomForm ? "Release ID" : "Transaction ID"}
                    value={proof.transaction_id}
                    testId="evidence-transaction-id"
                  />
                )}
                <ProofRow
                  label={industry.ui?.proofIdLabel || "Proof ID"}
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
                  label="Timestamp (UTC)"
                  value={formatTsUTC(proof.issued_at)}
                  testId="evidence-timestamp"
                />
                <ProofRow
                  label="Algorithm"
                  value="Ed25519 · SHA-256 · Deterministic canonicalization"
                  testId="evidence-algorithm"
                  valueClass="text-gray-700"
                />
              </div>

              {isBuilder && (
                <div className="mt-3 rounded-lg bg-gray-950 border border-gray-800 px-4 py-3">
                  <div className="text-[11px] uppercase tracking-wider text-gray-400">
                    Cryptographic Signature (Ed25519)
                  </div>
                  <div
                    className="mt-1 font-mono text-[12px] text-gray-200 break-all"
                    data-testid="evidence-signature"
                  >
                    {proof.signature ||
                      "Signature available in the downloadable proof artifact"}
                  </div>
                </div>
              )}

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
                verifiable, and tamper-resistant.
              </p>
              <p
                className="text-xs text-gray-500"
                data-testid="evidence-privacy-note"
              >
                Proof can be verified without sharing raw transaction data.
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
            </>
          )}
        </SectionCard>

        {/* 3b. Release Readiness Certificate (certificate-style industries) */}
        {isCustomForm && industry.certificate && processed && proof && (
          <div
            className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden"
            data-testid="release-readiness-certificate"
          >
            <div className="flex items-center justify-between gap-3 px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-blue-50/80 to-white">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center">
                  <Award className="w-5 h-5 text-white" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-gray-900 font-['Space_Grotesk']">
                    Release Readiness Certificate
                  </div>
                  <div className="text-xs text-gray-500">
                    Cryptographically signed · independently verifiable
                  </div>
                </div>
              </div>
              <StatusPill
                status={isCompliant ? "success" : "error"}
                label={isCompliant ? industry.statusLabels.pass : industry.statusLabels.fail}
                testId="certificate-status-badge"
              />
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-0 rounded-lg bg-gray-50 border border-gray-100 divide-y sm:divide-y-0 divide-gray-100">
                <ProofRow label="Release Name" value={extra[industry.workflowField] || "—"} testId="cert-release-name" />
                <ProofRow label="Environment" value={extra[industry.environmentField] || "—"} testId="cert-environment" />
                <ProofRow
                  label="Readiness Score"
                  value={`${Math.round(((simulateComplianceFail ? industry.checks.length - 1 : industry.checks.length) / industry.checks.length) * 100)}%`}
                  testId="cert-readiness-score"
                  valueClass={isCompliant ? "text-emerald-700" : "text-amber-700"}
                />
                <ProofRow
                  label="Verification Status"
                  value={isCompliant ? "Ready for Production" : "Blocked — Not Ready"}
                  testId="cert-verification-status"
                  valueClass={isCompliant ? "text-emerald-700" : "text-red-700"}
                />
                <ProofRow label="Proof ID" value={shortHash(proof.proof_id)} full={proof.proof_id} testId="cert-proof-id" />
                <ProofRow label="Generated (UTC)" value={formatTsUTC(proof.issued_at)} testId="cert-timestamp" />
              </div>
              <div className="mt-3 rounded-lg bg-gray-950 border border-gray-800 px-4 py-3">
                <div className="text-[11px] uppercase tracking-wider text-gray-400">Cryptographic Signature (Ed25519)</div>
                <div className="mt-1 font-mono text-[12px] text-gray-200 break-all" data-testid="cert-signature">
                  {proof.signature || "Signature available in the downloadable proof artifact"}
                </div>
              </div>
              <p className="mt-3 text-xs text-gray-500" data-testid="certificate-note">
                This certificate proves release readiness without exposing raw release data. Anyone can verify it using only the Proof ID.
              </p>
            </div>
          </div>
        )}
      </main>
            </div>
            )}

            {/* Verify Proof view */}
            {activeTab === "verify" && (
            <div className="p-6 space-y-5" data-testid="verify-view">
      <main className="space-y-5" data-testid="verify-steps">
        {/* 4. Auditor / External Verification */}
        <SectionCard
          step="4"
          title="Auditor Verification"
          description={industry.ui?.auditorDesc || "Verify any issued proof using only its Proof ID — no transaction data required."}
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
            <div
              className="mt-5 grid grid-cols-1 xl:grid-cols-2 gap-4 items-start"
              data-testid="auditor-result"
            >
              <AuditorResult result={auditorResult} />
              <AuditorTrustSection trust={auditorTrust} />
            </div>
          )}

          <p className="text-xs text-gray-500 mt-4" data-testid="auditor-note">
            Verification is performed using cryptographic proof, not by
            re-entering transaction data.
          </p>
        </SectionCard>

        {/* 5. Consistency */}
        {processed && proof && !industry.hideConsistency && (
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
        {processed && proof && mismatch && !industry.hideConsistency && (
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
                  Party A reports {formatUSD(form.amount)}, Party B reports{" "}
                  {formatUSD((Number(form.amount) + 100).toFixed(2))}. Settlement paused
                  pending reconciliation.
                </div>
              </div>
            </div>
          </SectionCard>
        )}

      </main>
            </div>
            )}
          </div>

          {(activeTab === "demo" || activeTab === "verify") && (
            <PortalRightRail
              active={activeTab}
              processed={processed}
              proof={proof}
              isCompliant={isCompliant}
              checksPassed={checksPassed}
              checksTotal={checksTotal}
              sessionProofs={sessionProofs}
              onVerify={() => setActiveTab("verify")}
              onViewAll={(id) => {
                if (id) {
                  setAuditorProofId(id);
                  setActiveTab("verify");
                } else {
                  setActiveTab("proofs");
                }
              }}
              onShare={shareProof}
              onCopyLink={copyVerificationLink}
            />
          )}
        </div>
      </div>

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

function TrustRow({ label, value, valueClass = "text-gray-900", testId }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2.5">
      <span className="text-xs uppercase tracking-wide text-gray-500">{label}</span>
      <span className={`text-sm text-right ${valueClass}`} data-testid={testId}>
        {value}
      </span>
    </div>
  );
}

function YesNo({ yes }) {
  return (
    <span className={`inline-flex items-center gap-1.5 font-medium ${yes ? "text-emerald-700" : "text-gray-500"}`}>
      {yes ? <CheckCircle2 className="w-3.5 h-3.5" /> : null}
      {yes ? "Yes" : "No"}
    </span>
  );
}

// Trust Layer 2 — AI Accountability & Trust Information.
// Always rendered below the verification results (never hidden). Sources data
// from the production public-verify response (ai_provenance + time_attestation).
// Privacy: shows identity/role/verdict facts only — never raw prompts, system
// prompts, AI outputs, sensitive content, or provenance content hashes.
function AuditorTrustSection({ trust }) {
  const NA = "Not Available";
  const ap = trust?.ai_provenance || null;
  const ta = trust?.time_attestation || null;
  const present = !!ap?.present;

  const ident = ap?.ai_identity || {};
  const aiUsed =
    present &&
    (ap.ai_identity_present ||
      (ap.agent_chain_length || 0) > 0 ||
      (ap.provenance_hashes && Object.keys(ap.provenance_hashes).length > 0));

  const multiAgent = present && !!ap.multi_agent;
  const agents = (present && Array.isArray(ap.agents) && ap.agents) || [];
  const approvalChain =
    (present && Array.isArray(ap.approval_chain) && ap.approval_chain) || [];

  const modelLabel =
    (ident.provider || ident.model_name)
      ? `${ident.provider || "—"} / ${ident.model_name || "—"}`
      : "—";

  // Independent time attestation status string.
  let timeStatus = NA;
  let timeClass = "text-gray-500";
  if (ta && ta.present) {
    if (ta.valid && ta.independent) {
      timeStatus = "Independently attested (RFC-3161)";
      timeClass = "text-emerald-700 font-medium";
    } else if (ta.valid && !ta.independent) {
      timeStatus = `Timestamped — ${ta.tier || "local authority"}`;
      timeClass = "text-blue-700 font-medium";
    } else {
      timeStatus = "Present — not verified";
      timeClass = "text-amber-700 font-medium";
    }
  }

  const aiVal = (yes, txt) => (
    <span className={yes ? "text-gray-900" : "text-gray-500"}>{txt}</span>
  );

  return (
    <div
      className="mt-4 rounded-lg border border-slate-200 bg-white overflow-hidden"
      data-testid="auditor-trust-section"
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100 bg-slate-50/70">
        <ShieldCheck className="w-4 h-4 text-blue-600" />
        <h4 className="text-sm font-semibold text-slate-900 font-['Space_Grotesk']">
          AI Accountability &amp; Trust Information
        </h4>
        {present && (
          <span
            className={`ml-auto inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${
              ap.valid
                ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20"
                : "bg-amber-50 text-amber-700 ring-1 ring-amber-600/20"
            }`}
            data-testid="trust-provenance-integrity"
          >
            {ap.valid ? "Provenance cryptographically verified" : "Provenance unverified"}
          </span>
        )}
      </div>

      {!present && (
        <div className="px-4 py-2.5 text-xs text-gray-500" data-testid="trust-no-provenance">
          No AI provenance record is attached to this proof.
        </div>
      )}

      <div className="divide-y divide-gray-100">
        <TrustRow label="AI Used" value={<YesNo yes={!!aiUsed} />} testId="trust-ai-used" />
        <TrustRow
          label="AI Provider"
          value={aiUsed ? aiVal(!!ident.provider, ident.provider || NA) : "Not Applicable"}
          testId="trust-ai-provider"
        />
        <TrustRow
          label="Model Name"
          value={aiUsed ? aiVal(!!ident.model_name, ident.model_name || NA) : "Not Applicable"}
          testId="trust-model-name"
        />
        <TrustRow
          label="Model Version"
          value={aiUsed ? aiVal(!!ident.model_version, ident.model_version || NA) : "Not Applicable"}
          testId="trust-model-version"
        />
        <TrustRow
          label="Agent Identifier"
          value={
            aiUsed
              ? aiVal(!!ident.agent_identifier, ident.agent_identifier || NA)
              : "Not Applicable"
          }
          valueClass="font-mono text-xs text-gray-900"
          testId="trust-agent-identifier"
        />
        <TrustRow
          label="Human Reviewed"
          value={present ? <YesNo yes={!!ap.human_reviewed} /> : NA}
          testId="trust-human-reviewed"
        />
        <TrustRow
          label="Human Approved"
          value={present ? <YesNo yes={!!ap.human_approved} /> : NA}
          testId="trust-human-approved"
        />
        <TrustRow
          label="Multi-Agent Workflow"
          value={present ? <YesNo yes={multiAgent} /> : NA}
          testId="trust-multi-agent"
        />
        <TrustRow
          label="Independent Time Attestation"
          value={<span className={timeClass}>{timeStatus}</span>}
          testId="trust-time-attestation"
        />
      </div>

      {/* Human Approval Chain */}
      {present && (
        <div className="border-t border-gray-100">
          <div className="px-4 pt-3 pb-1 flex items-center gap-1.5">
            <UserCheck className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Human Approval Chain
            </span>
          </div>
          {approvalChain.length === 0 ? (
            <div className="px-4 pb-3 text-xs text-gray-500" data-testid="trust-approval-chain-empty">
              Not Applicable
            </div>
          ) : (
            <ol className="px-4 pb-3 space-y-1.5" data-testid="trust-approval-chain">
              {approvalChain.map((e, i) => (
                <li
                  key={`approval-${i}`}
                  className="flex items-center gap-2 text-sm text-gray-800"
                  data-testid={`trust-approval-${i}`}
                >
                  <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600">
                    {i + 1}
                  </span>
                  <span className="capitalize font-medium">{e.event_type}</span>
                  <span className="text-gray-400">·</span>
                  <span>{e.actor_role || "—"}</span>
                  {e.actor_id && (
                    <span className="font-mono text-[11px] text-gray-400 truncate">
                      ({e.actor_id})
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {/* Agent Accountability Chain — only when Multi-Agent Workflow = Yes */}
      {multiAgent && (
        <div className="border-t border-gray-100 bg-slate-50/40" data-testid="agent-accountability-chain">
          <div className="px-4 pt-3 pb-1 flex items-center gap-1.5">
            <Workflow className="w-3.5 h-3.5 text-blue-600" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-blue-700">
              Agent Accountability Chain
            </span>
          </div>
          <ol className="px-4 pb-3 space-y-1.5">
            {agents.map((a, i) => (
              <li
                key={`agent-${i}`}
                className="flex items-center gap-2 text-sm text-gray-800"
                data-testid={`agent-chain-row-${i}`}
              >
                <Bot className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                <span className="font-medium">{a.agent_role || a.agent_identifier || `Agent ${i + 1}`}</span>
                <ArrowRight className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                <span className="text-gray-600">{modelLabel}</span>
                {a.outcome && (
                  <span className="ml-1 text-[11px] text-gray-400">· {a.outcome}</span>
                )}
              </li>
            ))}
            {approvalChain
              .filter((e) => e.event_type === "approval")
              .map((e, i) => (
                <li
                  key={`agent-approval-${i}`}
                  className="flex items-center gap-2 text-sm text-gray-800"
                  data-testid={`agent-chain-approval-${i}`}
                >
                  <UserCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span className="font-medium">Human Approval</span>
                  <ArrowRight className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                  <span className="text-gray-600">
                    {(e.actor_id || "Approver")}{e.actor_role ? ` / ${e.actor_role}` : ""}
                  </span>
                </li>
              ))}
          </ol>
        </div>
      )}

      <div className="px-4 py-2.5 border-t border-gray-100 bg-slate-50/50">
        <p className="text-[11px] text-gray-400 leading-relaxed">
          Accountability facts are derived from the proof's cryptographically
          bound provenance envelope. No raw prompts, AI outputs, or sensitive
          content are stored or shown.
        </p>
      </div>
    </div>
  );
}

function AuditorResult({ result }) {
  const { valid, compliance, industry, transaction_id, issued_at, reason } =
    result;
  // A valid proof with NO compliance metadata (e.g. production proofs verified
  // via public-verify) reads as a clean valid proof — not "non-compliant".
  const isCompliant = valid && (!compliance || compliance?.status === "COMPLIANT");

  const headline = !valid
    ? "Invalid Proof — Verification Failed"
    : isCompliant
    ? "Valid Proof — Data Untampered"
    : "Valid Proof — Workflow flagged as NON-COMPLIANT";

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

  const hasIndustryChecks =
    valid && industry && Array.isArray(industry.checks) && industry.checks.length > 0;

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

      {valid && industry?.label && (
        <div
          className="mt-1 text-xs text-gray-600"
          data-testid="auditor-industry-label"
        >
          Industry context: <span className="font-medium">{industry.label}</span>
        </div>
      )}

      {valid && industry?.context && Object.keys(industry.context).length > 0 && (
        <div
          className="mt-3 rounded-md bg-white/80 border border-white/60 backdrop-blur-sm divide-y divide-gray-100"
          data-testid="auditor-context"
        >
          {Object.entries(industry.context).map(([k, v]) => (
            <ProofRow key={k} label={k} value={v} testId={`auditor-context-${k.toLowerCase().replace(/\s+/g, "-")}`} borderless />
          ))}
        </div>
      )}

      {valid &&
        Array.isArray(industry?.custom_fields) &&
        industry.custom_fields.length > 0 && (
          <div
            className="mt-3 rounded-md bg-white/80 border border-white/60 backdrop-blur-sm divide-y divide-gray-100"
            data-testid="auditor-custom-fields"
          >
            {industry.custom_fields.map((f, i) => (
              <ProofRow
                key={`auditor-field-${i}`}
                label={f.label}
                value={f.value}
                testId={`auditor-field-${i}`}
                borderless
              />
            ))}
          </div>
        )}

      {hasIndustryChecks && (
        <div
          className="mt-4 rounded-md bg-white/80 border border-white/60 backdrop-blur-sm divide-y divide-gray-100"
          data-testid="auditor-industry-checks"
        >
          {industry.checks.map((c, idx) => {
            const passed = c.status === "Pass";
            const RowIcon = passed ? CheckCircle2 : AlertTriangle;
            const iconClass = passed ? "text-emerald-600" : "text-red-600";
            return (
              <div
                key={`auditor-check-${idx}`}
                className="flex items-start justify-between gap-4 px-4 py-3"
                data-testid={`auditor-check-${idx}`}
              >
                <div className="flex items-start gap-2.5 min-w-0">
                  <RowIcon
                    className={`w-4 h-4 mt-0.5 shrink-0 ${iconClass}`}
                  />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-gray-900 leading-snug">
                      {c.name}
                    </div>
                    {c.desc && (
                      <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">
                        {c.desc}
                      </div>
                    )}
                  </div>
                </div>
                <StatusPill
                  status={passed ? "success" : "error"}
                  label={passed ? "Pass" : "Fail"}
                  testId={`auditor-check-${idx}-status`}
                />
              </div>
            );
          })}
          {transaction_id && (
            <ProofRow
              label="Transaction ID"
              value={transaction_id}
              testId="auditor-transaction-id"
              borderless
            />
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

      {/* Fallback: when no industry metadata was persisted with this proof
          (e.g. proofs issued before industry-aware persistence), show the
          underlying compliance summary so older proofs remain auditable. */}
      {valid && !hasIndustryChecks && compliance && (
        <div className="mt-4 rounded-md bg-white/80 border border-white/60 divide-y divide-gray-100 backdrop-blur-sm">
          {transaction_id && (
            <ProofRow
              label="Transaction ID"
              value={transaction_id}
              testId="auditor-transaction-id"
              borderless
            />
          )}
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

function FieldSelect({ label, value, options = [], onChange, testId }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
        {label}
      </Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger
          className="bg-white border-gray-200 text-gray-900 h-10 focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
          data-testid={testId}
        >
          <SelectValue placeholder={`Select ${label}`} />
        </SelectTrigger>
        <SelectContent className="bg-white border-gray-200">
          {options.map((opt) => (
            <SelectItem key={opt} value={opt} data-testid={`${testId}-option-${opt.toLowerCase()}`}>
              {opt}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

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
          {formatUSD(amount)}
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
