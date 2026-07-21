import { useState } from "react";
import { toast } from "sonner";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Check,
  FileSignature,
  Fingerprint,
  ChevronDown,
} from "lucide-react";

// Human-friendly labels for well-known authenticated fields. Anything not in
// this map is rendered with a derived Title Case label so the summary stays
// industry-neutral (no hardcoded payment fields).
const LABELS = {
  transaction_id: "External Transaction ID",
  timestamp: "Event Timestamp",
  amount: "Amount",
  currency: "Currency",
  iat: "Proof Issued At",
  algorithm: "Signature Algorithm",
  public_key_id: "Signing Key ID",
  signature_version: "Signature Version",
  fea_hash: "Payload Hash",
  fea_version: "Artifact Version",
  issuer_id: "Issuer",
  tenant_id: "Tenant",
  jti: "Artifact Nonce (jti)",
  fea_id: "Proof Artifact ID",
  payer_hash: "Originator Commitment",
  payee_hash: "Counterparty Commitment",
  metadata_hash: "Metadata Commitment",
};

// Keys handled explicitly elsewhere (or intentionally not shown as raw values).
const RESERVED = new Set([
  "transaction_summary",
  "parties",
  "signature_version",
]);

const titleCase = (k) =>
  String(k)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

const isIsoLike = (v) =>
  typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v);

const isHashLike = (k) =>
  /_hash$/.test(k) || k === "payer_hash" || k === "payee_hash";

const fmtTs = (iso) => {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(undefined, {
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

const fmtAmount = (amount, currency) => {
  if (amount === undefined || amount === null || amount === "") return null;
  const n = Number(amount);
  if (Number.isNaN(n)) return String(amount);
  const s = n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return currency ? `${s} ${currency}` : s;
};

function CopyBtn({ value }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(String(value));
          setCopied(true);
          toast.success("Copied");
          setTimeout(() => setCopied(false), 1400);
        } catch {
          toast.error("Copy failed");
        }
      }}
      className="shrink-0 text-gray-400 hover:text-gray-700 transition-colors"
      title="Copy"
      data-testid="evidence-copy-btn"
    >
      {copied ? (
        <Check className="w-3.5 h-3.5 text-emerald-600" />
      ) : (
        <Copy className="w-3.5 h-3.5" />
      )}
    </button>
  );
}

function EvidenceRow({ label, value, mono = false, copy = false, testId }) {
  if (value === undefined || value === null || value === "") return null;
  return (
    <div
      className="flex items-start justify-between gap-4 px-4 py-2.5"
      data-testid={testId}
    >
      <span className="text-xs uppercase tracking-wide text-gray-500 pt-0.5 shrink-0">
        {label}
      </span>
      <div className="flex items-center gap-2 min-w-0 justify-end">
        <span
          className={`text-sm text-gray-900 text-right break-all ${
            mono ? "font-mono text-xs" : ""
          }`}
          title={String(value)}
        >
          {String(value)}
        </span>
        {copy && <CopyBtn value={value} />}
      </div>
    </div>
  );
}

// Builds the ordered list of authenticated evidence rows dynamically from the
// signed FEA payload — never hardcodes any single industry's fields.
function buildRows(payload, artifact) {
  const p = payload || {};
  const ts = p.transaction_summary || {};

  const evidence = [];
  // Business evidence (from the signed transaction_summary), industry-neutral.
  if (ts.transaction_id !== undefined)
    evidence.push({
      key: "transaction_id",
      label: LABELS.transaction_id,
      value: ts.transaction_id,
      mono: true,
      copy: true,
    });
  const amt = fmtAmount(ts.amount, ts.currency);
  if (amt !== null)
    evidence.push({ key: "amount", label: LABELS.amount, value: amt });
  if (ts.currency !== undefined)
    evidence.push({ key: "currency", label: LABELS.currency, value: ts.currency });
  if (ts.timestamp !== undefined)
    evidence.push({
      key: "timestamp",
      label: LABELS.timestamp,
      value: fmtTs(ts.timestamp),
    });
  // Any additional authenticated scalar fields inside transaction_summary.
  Object.entries(ts).forEach(([k, v]) => {
    if (["transaction_id", "amount", "currency", "timestamp"].includes(k)) return;
    if (v === null || typeof v === "object") return;
    evidence.push({
      key: k,
      label: LABELS[k] || titleCase(k),
      value: isIsoLike(v) ? fmtTs(v) : v,
    });
  });
  // Any additional top-level authenticated scalar metadata (non-hash, non-crypto).
  const cryptoKeys = new Set([
    "algorithm",
    "public_key_id",
    "iat",
    "jti",
    "fea_version",
    "issuer_id",
    "fea_hash",
    "tenant_id",
  ]);
  Object.entries(p).forEach(([k, v]) => {
    if (RESERVED.has(k) || cryptoKeys.has(k) || isHashLike(k)) return;
    if (v === null || typeof v === "object") return;
    evidence.push({
      key: k,
      label: LABELS[k] || titleCase(k),
      value: isIsoLike(v) ? fmtTs(v) : v,
    });
  });

  // Cryptographic / issuance details.
  const crypto = [];
  const pushCrypto = (key, value, opts = {}) => {
    if (value === undefined || value === null || value === "") return;
    crypto.push({ key, label: LABELS[key] || titleCase(key), value, ...opts });
  };
  pushCrypto("iat", fmtTs(p.iat || artifact?.created_at));
  pushCrypto("algorithm", p.algorithm);
  pushCrypto("public_key_id", p.public_key_id || artifact?.public_key_id, {
    mono: true,
    copy: true,
  });
  pushCrypto("signature_version", artifact?.signature_version || p.signature_version);
  pushCrypto("fea_hash", p.fea_hash, { mono: true, copy: true });
  pushCrypto("fea_version", p.fea_version);
  pushCrypto("issuer_id", p.issuer_id);
  if (artifact?.fea_id)
    crypto.push({
      key: "fea_id",
      label: LABELS.fea_id,
      value: artifact.fea_id,
      mono: true,
      copy: true,
    });
  pushCrypto("jti", p.jti, { mono: true });

  // Privacy-preserving commitments (hashes only — no raw content ever).
  const commitments = [];
  const parties = p.parties || {};
  if (parties.payer_hash)
    commitments.push({
      key: "payer_hash",
      label: LABELS.payer_hash,
      value: parties.payer_hash,
    });
  if (parties.payee_hash)
    commitments.push({
      key: "payee_hash",
      label: LABELS.payee_hash,
      value: parties.payee_hash,
    });
  if (p.metadata_hash)
    commitments.push({
      key: "metadata_hash",
      label: LABELS.metadata_hash,
      value: p.metadata_hash,
    });

  return { evidence, crypto, commitments };
}

// A read-only, industry-neutral Evidence Summary rendered dynamically from a
// cryptographically authenticated Proof Artifact (FEA). Consistent auditor
// experience for both PFP-generated and externally ingested proofs.
export default function EvidenceSummary({ artifact, valid }) {
  const [showCommit, setShowCommit] = useState(false);
  if (!artifact || !artifact.fea_payload) return null;
  const { evidence, crypto, commitments } = buildRows(
    artifact.fea_payload,
    artifact
  );

  const ok = !!valid;
  const StatusIcon = ok ? CheckCircle2 : AlertTriangle;

  return (
    <div
      className="rounded-lg border border-slate-200 bg-white overflow-hidden"
      data-testid="evidence-summary"
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100 bg-slate-50/70">
        <ShieldCheck className="w-4 h-4 text-blue-600" />
        <h4 className="text-sm font-semibold text-slate-900 font-['Space_Grotesk']">
          Evidence Summary
        </h4>
        <span
          className={`ml-auto inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${
            ok
              ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20"
              : "bg-red-50 text-red-700 ring-1 ring-red-600/20"
          }`}
          data-testid="evidence-verification-status"
        >
          <StatusIcon className="w-3 h-3" />
          {ok ? "Cryptographically Authenticated" : "Verification Failed"}
        </span>
      </div>

      <p className="px-4 pt-3 text-xs text-gray-500 leading-relaxed">
        The fields below were cryptographically authenticated by the proof's
        signature. No sensitive or confidential content is stored or shown.
      </p>

      {/* Authenticated evidence */}
      <div className="px-4 pt-2 pb-1">
        <div className="flex items-center gap-1.5 pt-1 pb-1">
          <FileSignature className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Authenticated Evidence
          </span>
        </div>
      </div>
      {evidence.length > 0 ? (
        <div className="divide-y divide-gray-100 border-y border-gray-100">
          {evidence.map((r) => (
            <EvidenceRow
              key={`ev-${r.key}`}
              label={r.label}
              value={r.value}
              mono={r.mono}
              copy={r.copy}
              testId={`evidence-${r.key.replace(/_/g, "-")}`}
            />
          ))}
        </div>
      ) : (
        <div className="px-4 pb-2 text-xs text-gray-500" data-testid="evidence-none">
          No additional authenticated business fields are present in this proof.
        </div>
      )}

      {/* Cryptographic details */}
      <div className="px-4 pt-3 pb-1">
        <div className="flex items-center gap-1.5">
          <Fingerprint className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Verification Metadata
          </span>
        </div>
      </div>
      <div className="divide-y divide-gray-100 border-y border-gray-100">
        {crypto.map((r) => (
          <EvidenceRow
            key={`cr-${r.key}`}
            label={r.label}
            value={r.value}
            mono={r.mono}
            copy={r.copy}
            testId={`evidence-${r.key.replace(/_/g, "-")}`}
          />
        ))}
      </div>

      {/* Privacy-preserving commitments (collapsible) */}
      {commitments.length > 0 && (
        <div className="border-t border-gray-100">
          <button
            type="button"
            onClick={() => setShowCommit((s) => !s)}
            className="w-full flex items-center gap-1.5 px-4 py-2.5 text-left hover:bg-slate-50/60 transition-colors"
            data-testid="evidence-commitments-toggle"
          >
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Privacy-Preserving Commitments (hashes)
            </span>
            <ChevronDown
              className={`w-3.5 h-3.5 text-slate-400 ml-auto transition-transform ${
                showCommit ? "rotate-180" : ""
              }`}
            />
          </button>
          {showCommit && (
            <div className="divide-y divide-gray-100 border-t border-gray-100">
              {commitments.map((r) => (
                <EvidenceRow
                  key={`cm-${r.key}`}
                  label={r.label}
                  value={r.value}
                  mono
                  copy
                  testId={`evidence-${r.key.replace(/_/g, "-")}`}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
