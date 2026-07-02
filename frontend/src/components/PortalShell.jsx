import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Home,
  BookOpen,
  LayoutGrid,
  Bot,
  Library,
  HelpCircle,
  FilePlus2,
  ShieldCheck,
  FileText,
  Code2,
  ArrowRight,
  Clock,
  Share2,
  Link2,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Plus,
  ChevronRight,
  ExternalLink,
} from "lucide-react";

/* --------------------------------- utils ---------------------------------- */

export function formatUSD(v) {
  const n = Number(v);
  if (v === undefined || v === null || v === "" || Number.isNaN(n)) {
    return `$${v ?? "0.00"}`;
  }
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}

function timeAgo(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const dd = Math.floor(h / 24);
  return `${dd}d ago`;
}

const SHORT = (h) => (h ? `${h.slice(0, 10)}…${h.slice(-6)}` : "");

/* ------------------------- session proofs (localStorage) ------------------- */

const STORAGE_KEY = "pfp_session_proofs_v1";

export function useSessionProofs() {
  const [proofs, setProofs] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch {
      return [];
    }
  });

  const addProof = useCallback((p) => {
    setProofs((prev) => {
      const next = [
        { ...p, recorded_at: new Date().toISOString() },
        ...prev.filter((x) => x.proof_id !== p.proof_id),
      ].slice(0, 50);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* ignore quota errors */
      }
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setProofs([]);
  }, []);

  return { proofs, addProof, clear };
}

/* -------------------------------- nav config ------------------------------ */

const MAIN_NAV = [
  { id: "demo", label: "Demo", icon: Home },
  { id: "how", label: "How PFP Works", icon: BookOpen },
  { id: "usecases", label: "Use Cases", icon: LayoutGrid },
  { id: "aigov", label: "AI Governance", icon: Bot },
  { id: "resources", label: "Resources", icon: Library },
  { id: "faq", label: "FAQ", icon: HelpCircle },
];

const CRUMB = {
  demo: "New Transaction",
  verify: "Verify Proof",
  proofs: "Proofs",
  how: "How PFP Works",
  usecases: "Use Cases",
  aigov: "AI Governance",
  resources: "Resources",
  faq: "FAQ",
};

/* -------------------------------- Sidebar --------------------------------- */

export function PortalSidebar({ active, onNavigate, onNewTransaction }) {
  const navItem = (item) => {
    const Icon = item.icon;
    const isActive = active === item.id;
    return (
      <button
        key={item.id}
        onClick={() => onNavigate(item.id)}
        data-testid={`nav-${item.id}`}
        className={`flex w-full items-center gap-3 px-3 py-2 rounded-md text-sm border-l-2 transition-colors ${
          isActive
            ? "bg-blue-50 text-blue-700 font-semibold border-blue-600"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 border-transparent"
        }`}
      >
        <Icon className="w-4 h-4 shrink-0" />
        {item.label}
      </button>
    );
  };

  return (
    <aside
      className="hidden md:flex w-[240px] flex-shrink-0 border-r border-slate-200 bg-white flex-col h-full"
      data-testid="portal-sidebar"
    >
      <div className="flex items-center gap-2.5 px-5 h-14 border-b border-slate-200">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
          <ShieldCheck className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="text-sm font-bold tracking-tight text-slate-900 font-['Space_Grotesk'] leading-none">
            PFP
          </div>
          <div className="text-[11px] text-slate-500 leading-tight">
            Proof Fabric Protocol
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <div className="space-y-1">{MAIN_NAV.map(navItem)}</div>

        <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500 mt-5">
          Quick Actions
        </div>
        <div className="space-y-1">
          <button
            onClick={onNewTransaction}
            data-testid="quick-new-transaction"
            className="flex w-full items-center gap-3 px-3 py-2 rounded-md text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900 border-l-2 border-transparent transition-colors"
          >
            <FilePlus2 className="w-4 h-4 shrink-0" />
            New Transaction
          </button>
          <button
            onClick={() => onNavigate("verify")}
            data-testid="quick-verify-proof"
            className={`flex w-full items-center gap-3 px-3 py-2 rounded-md text-sm border-l-2 transition-colors ${
              active === "verify"
                ? "bg-blue-50 text-blue-700 font-semibold border-blue-600"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 border-transparent"
            }`}
          >
            <ShieldCheck className="w-4 h-4 shrink-0" />
            Verify Proof
          </button>
          <button
            onClick={() => onNavigate("proofs")}
            data-testid="quick-view-proofs"
            className={`flex w-full items-center gap-3 px-3 py-2 rounded-md text-sm border-l-2 transition-colors ${
              active === "proofs"
                ? "bg-blue-50 text-blue-700 font-semibold border-blue-600"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 border-transparent"
            }`}
          >
            <FileText className="w-4 h-4 shrink-0" />
            View Proofs
          </button>
          <a
            href="/developers"
            data-testid="quick-api-docs"
            className="flex w-full items-center gap-3 px-3 py-2 rounded-md text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900 border-l-2 border-transparent transition-colors"
          >
            <Code2 className="w-4 h-4 shrink-0" />
            API Docs
          </a>
        </div>
      </nav>

      <div className="p-3 border-t border-slate-200">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="text-sm font-semibold text-slate-900">
            Build with PFP
          </div>
          <p className="mt-1 text-xs text-slate-500 leading-relaxed">
            Integrate proof generation and verification into your systems in
            minutes.
          </p>
          <a
            href="/developers"
            data-testid="sidebar-view-api-docs"
            className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-700"
          >
            View API Docs <ArrowRight className="w-3 h-3" />
          </a>
        </div>
      </div>
    </aside>
  );
}

/* -------------------------------- Top Bar --------------------------------- */

export function PortalTopBar({ active, onNavigate, onNewTransaction }) {
  return (
    <header
      className="flex-shrink-0 border-b border-slate-200 bg-white"
      data-testid="portal-topbar"
    >
      <div className="h-14 flex items-center px-4 sm:px-6 justify-between">
        <div className="flex items-center gap-2 text-sm min-w-0">
          <span className="text-slate-400 hidden sm:inline">Dashboard</span>
          <ChevronRight className="w-3.5 h-3.5 text-slate-300 hidden sm:inline" />
          <span
            className="font-semibold text-slate-900 truncate"
            data-testid="topbar-crumb"
          >
            {CRUMB[active] || "Dashboard"}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <a
            href="/docs"
            data-testid="topbar-docs"
            className="hidden sm:inline-flex items-center text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md px-3 py-1.5 transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5 mr-1.5" />
            Docs
          </a>
          <a
            href="/developers"
            data-testid="topbar-developers"
            className="hidden sm:inline-flex items-center text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md px-3 py-1.5 transition-colors"
          >
            <Code2 className="w-3.5 h-3.5 mr-1.5" />
            Developers
          </a>
          <Button
            size="sm"
            onClick={onNewTransaction}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium"
            data-testid="topbar-new-transaction"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Transaction
          </Button>
        </div>
      </div>

      {/* Mobile nav strip (sidebar hidden < md) */}
      <div className="md:hidden border-t border-slate-100 px-2">
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar py-1.5">
          {[...MAIN_NAV, { id: "verify", label: "Verify", icon: ShieldCheck }, { id: "proofs", label: "Proofs", icon: FileText }].map(
            (t) => {
              const Icon = t.icon;
              const isActive = active === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => onNavigate(t.id)}
                  data-testid={`mobile-nav-${t.id}`}
                  className={`flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-blue-50 text-blue-700"
                      : "text-slate-500 hover:text-slate-900"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {t.label}
                </button>
              );
            }
          )}
        </div>
      </div>
    </header>
  );
}

/* ------------------------------- Right Rail ------------------------------- */

function RailCard({ title, icon: Icon, children, testId }) {
  return (
    <div
      className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden"
      data-testid={testId}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
        {Icon && <Icon className="w-4 h-4 text-blue-600" />}
        <h3 className="text-sm font-semibold text-slate-900 font-['Space_Grotesk']">
          {title}
        </h3>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export function PortalRightRail({
  active,
  processed,
  proof,
  isCompliant,
  checksPassed,
  checksTotal,
  sessionProofs = [],
  onVerify,
  onViewAll,
  onShare,
  onCopyLink,
}) {
  const hasProof = processed && proof;

  let stateLabel = "Awaiting Transaction";
  let stateSub = "Process a transaction to generate a proof.";
  let stateClass = "bg-slate-50 border-slate-200 text-slate-600";
  if (hasProof && isCompliant) {
    stateLabel = active === "verify" ? "Trusted & Verified" : "Ready to Verify";
    stateSub = "All compliance checks passed";
    stateClass = "bg-emerald-50 border-emerald-200 text-emerald-700";
  } else if (hasProof && !isCompliant) {
    stateLabel = "Flagged";
    stateSub = "One or more compliance checks failed";
    stateClass = "bg-red-50 border-red-200 text-red-700";
  }

  return (
    <aside
      className="w-[320px] flex-shrink-0 border-l border-slate-200 bg-slate-50 p-5 overflow-y-auto hidden lg:flex flex-col gap-5"
      data-testid="portal-right-rail"
    >
      <RailCard title="Proof Summary" icon={ShieldCheck} testId="rail-proof-summary">
        <div
          className={`rounded-lg border px-4 py-4 text-center ${stateClass}`}
          data-testid="rail-state"
        >
          <div className="text-base font-semibold font-['Space_Grotesk']">
            {stateLabel}
          </div>
          <div className="mt-1 flex items-center justify-center gap-1.5 text-xs">
            {hasProof && isCompliant && <CheckCircle2 className="w-3.5 h-3.5" />}
            {hasProof && !isCompliant && <AlertTriangle className="w-3.5 h-3.5" />}
            {stateSub}
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between py-1.5 border-b border-slate-100">
          <span className="text-xs text-slate-500 font-medium">Checks Passed</span>
          <span
            className={`text-sm font-bold font-['Space_Grotesk'] ${
              hasProof ? (isCompliant ? "text-emerald-600" : "text-amber-600") : "text-slate-400"
            }`}
            data-testid="rail-checks-passed"
          >
            {hasProof ? `${checksPassed} / ${checksTotal}` : "—"}
          </span>
        </div>
        <div className="flex items-center justify-between py-1.5">
          <span className="text-xs text-slate-500 font-medium">Workflow Status</span>
          <span data-testid="rail-workflow-status">
            {hasProof ? (
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                  isCompliant
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-red-50 text-red-700 border-red-200"
                }`}
              >
                {isCompliant ? "Compliant" : "Flagged"}
              </span>
            ) : (
              <span className="text-sm text-slate-400">—</span>
            )}
          </span>
        </div>
      </RailCard>

      <RailCard title="Next Step" icon={ArrowRight} testId="rail-next-step">
        {!hasProof ? (
          <p className="text-xs text-slate-500 leading-relaxed">
            Generate a proof, then verify it independently using the public
            verifier or API.
          </p>
        ) : active === "verify" ? (
          <>
            <p className="text-xs text-slate-500 leading-relaxed">
              Share this proof or copy the verification link for independent
              verification.
            </p>
            <div className="mt-3 space-y-2">
              <Button
                variant="outline"
                onClick={onCopyLink}
                className="w-full justify-center border-slate-200 text-slate-700 hover:bg-slate-50"
                data-testid="rail-copy-link"
              >
                <Link2 className="w-4 h-4 mr-2" />
                Copy Verification Link
              </Button>
              <Button
                onClick={onShare}
                className="w-full justify-center bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="rail-share"
              >
                <Share2 className="w-4 h-4 mr-2" />
                Share Proof
              </Button>
            </div>
          </>
        ) : (
          <>
            <p className="text-xs text-slate-500 leading-relaxed">
              Verify this proof independently using the public verifier or API.
            </p>
            <Button
              onClick={onVerify}
              className="mt-3 w-full justify-center bg-blue-600 hover:bg-blue-700 text-white"
              data-testid="rail-verify-proof"
            >
              Verify Proof <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </>
        )}
      </RailCard>

      <RailCard title="Recent Proofs" icon={Clock} testId="rail-recent-proofs">
        {sessionProofs.length === 0 ? (
          <div
            className="rounded-md border border-dashed border-slate-300 px-3 py-4 text-center text-xs text-slate-400"
            data-testid="rail-recent-empty"
          >
            No session proofs yet
          </div>
        ) : (
          <div className="space-y-1">
            {sessionProofs.slice(0, 4).map((p) => (
              <button
                key={p.proof_id}
                onClick={() => onViewAll && onViewAll(p.proof_id)}
                className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-2 hover:bg-slate-50 transition-colors text-left"
                data-testid={`rail-proof-${p.proof_id}`}
              >
                <div className="min-w-0">
                  <div className="text-xs font-medium text-slate-900 font-mono truncate">
                    {p.transaction_id || SHORT(p.proof_id)}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {formatUSD(p.amount)} · {timeAgo(p.recorded_at)}
                  </div>
                </div>
                <span
                  className={`shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold border ${
                    p.compliant
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-red-50 text-red-700 border-red-200"
                  }`}
                >
                  {p.compliant ? "Verified" : "Flagged"}
                </span>
              </button>
            ))}
            <button
              onClick={() => onViewAll && onViewAll()}
              className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700"
              data-testid="rail-view-all"
            >
              View all <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        )}
      </RailCard>
    </aside>
  );
}

/* ---------------------------- Session Proofs view ------------------------- */

export function SessionProofsView({ proofs = [], onOpen, onClear, onNew }) {
  return (
    <div className="max-w-4xl" data-testid="session-proofs-view">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 font-['Space_Grotesk']">
            Proofs
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Proof artifacts you generated in this browser session.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={onNew}
            className="border-slate-200 text-slate-700 hover:bg-slate-50"
            data-testid="proofs-new-transaction"
          >
            <FilePlus2 className="w-4 h-4 mr-2" />
            New Transaction
          </Button>
          {proofs.length > 0 && (
            <Button
              variant="outline"
              onClick={onClear}
              className="border-slate-200 text-slate-600 hover:bg-red-50 hover:text-red-700 hover:border-red-200"
              data-testid="proofs-clear"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Clear
            </Button>
          )}
        </div>
      </div>

      {proofs.length === 0 ? (
        <div
          className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white px-6 py-12 text-center"
          data-testid="proofs-empty"
        >
          <FileText className="w-8 h-8 text-slate-300 mx-auto" />
          <div className="mt-3 text-sm font-medium text-slate-600">
            No proofs in this session
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Generate a proof from the Demo to see it listed here.
          </p>
        </div>
      ) : (
        <div className="mt-5 rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="hidden sm:grid grid-cols-12 gap-3 px-4 py-2.5 border-b border-slate-100 bg-slate-50/60 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            <div className="col-span-4">Transaction</div>
            <div className="col-span-3">Proof ID</div>
            <div className="col-span-2 text-right">Amount</div>
            <div className="col-span-2">Issued</div>
            <div className="col-span-1 text-right">Status</div>
          </div>
          <div className="divide-y divide-slate-100">
            {proofs.map((p) => (
              <button
                key={p.proof_id}
                onClick={() => onOpen && onOpen(p.proof_id)}
                className="grid grid-cols-1 sm:grid-cols-12 gap-1 sm:gap-3 w-full px-4 py-3 hover:bg-slate-50 transition-colors text-left items-center"
                data-testid={`proofs-row-${p.proof_id}`}
              >
                <div className="sm:col-span-4 min-w-0">
                  <div className="text-sm font-medium text-slate-900 font-mono truncate">
                    {p.transaction_id || SHORT(p.proof_id)}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {p.industry_label}
                  </div>
                </div>
                <div className="sm:col-span-3 text-xs font-mono text-slate-500 truncate">
                  {SHORT(p.proof_id)}
                </div>
                <div className="sm:col-span-2 text-sm text-slate-900 sm:text-right font-medium">
                  {formatUSD(p.amount)}
                </div>
                <div className="sm:col-span-2 text-xs text-slate-500">
                  {timeAgo(p.recorded_at)}
                </div>
                <div className="sm:col-span-1 sm:text-right">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                      p.compliant
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                        : "bg-red-50 text-red-700 border-red-200"
                    }`}
                  >
                    {p.compliant ? "Verified" : "Flagged"}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      <p className="mt-3 text-[11px] text-slate-400">
        <ExternalLink className="w-3 h-3 inline mr-1" />
        Session proofs are stored only in this browser (localStorage) and are
        never sent anywhere. Clearing your browser data removes them.
      </p>
    </div>
  );
}
