import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, CheckCircle2, Loader2, ArrowLeft, Building2, Lock } from "lucide-react";
import { submitEvaluationRequest, docsLogin } from "../docs/docsAuth";

const INDUSTRIES = [
  "Financial Services / Banking", "Payments / Fintech", "Insurance", "Capital Markets",
  "Government / Public Sector", "Healthcare", "Audit / Assurance", "Compliance / RegTech",
  "Technology / SaaS", "Other",
];

const Field = ({ label, children }) => (
  <label className="block">
    <span className="block text-sm font-medium text-slate-700 mb-1.5">{label}</span>
    {children}
  </label>
);

const inputCls =
  "w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-slate-900 focus:ring-1 focus:ring-slate-900 outline-none";

export default function EnterpriseAccess() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", company: "", business_email: "", industry: "", use_case: "" });
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState(null);

  // sign-in
  const [si, setSi] = useState({ email: "", password: "" });
  const [siBusy, setSiBusy] = useState(false);
  const [siErr, setSiErr] = useState(null);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true); setErr(null);
    try { await submitEvaluationRequest(form); setDone(true); }
    catch (e2) { setErr(e2.message); }
    finally { setSubmitting(false); }
  };

  const signIn = async (e) => {
    e.preventDefault();
    setSiBusy(true); setSiErr(null);
    try { await docsLogin(si.email, si.password); navigate("/docs"); }
    catch (e2) { setSiErr(e2.message); }
    finally { setSiBusy(false); }
  };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="enterprise-access-page">
      <header className="h-14 bg-white border-b border-slate-200 flex items-center px-6">
        <a href="/" className="flex items-center gap-2 text-slate-700 hover:text-slate-900 text-sm">
          <ArrowLeft className="h-4 w-4" /> Back to PFP
        </a>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-12 grid lg:grid-cols-2 gap-12">
        {/* Left: value framing */}
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-900 text-white px-3 py-1 text-xs font-medium">
            <ShieldCheck className="h-3.5 w-3.5" /> Enterprise Evaluation Center
          </div>
          <h1 className="mt-5 text-3xl font-semibold text-slate-900 leading-tight">
            Evaluate the Proof Fabric Protocol
          </h1>
          <p className="mt-4 text-slate-600 leading-relaxed">
            PFP turns any transaction or decision into an independently verifiable, tamper-evident
            proof artifact — verifiable in seconds without access to our systems. Request access to
            the full technical evaluation package for your team.
          </p>
          <ul className="mt-6 space-y-3 text-sm text-slate-700">
            {[
              "Full API reference, OpenAPI spec & Postman collection",
              "Architecture, cryptographic & trust design",
              "Security architecture, threat model & KMS/HSM design",
              "SDKs (Python, JavaScript, Java, .NET) & integration guides",
              "Verification & compliance validation materials",
            ].map((t) => (
              <li key={t} className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4.5 w-4.5 text-emerald-500 mt-0.5 shrink-0" /> {t}
              </li>
            ))}
          </ul>
          <p className="mt-8 text-xs text-slate-400 flex items-center gap-1.5">
            <Lock className="h-3.5 w-3.5" /> Proprietary, patent-backed infrastructure. Access is reviewed and time-limited.
          </p>
        </div>

        {/* Right: form / success / sign-in */}
        <div>
          {done ? (
            <div className="bg-white border border-slate-200 rounded-2xl p-8 text-center" data-testid="evaluation-success">
              <div className="h-12 w-12 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center mx-auto">
                <CheckCircle2 className="h-6 w-6 text-emerald-500" />
              </div>
              <h2 className="mt-4 text-lg font-semibold text-slate-900">Request received</h2>
              <p className="mt-2 text-sm text-slate-500">
                Thank you. Our team will review your request and follow up by email with evaluation access.
              </p>
              <a href="/" className="mt-6 inline-block text-sm text-slate-600 hover:text-slate-900 underline">Return to PFP</a>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-2xl p-7">
              <div className="flex items-center gap-2 text-slate-900 font-semibold">
                <Building2 className="h-4.5 w-4.5" /> Request Enterprise Access
              </div>
              <form onSubmit={submit} className="mt-5 space-y-4" data-testid="evaluation-form">
                <Field label="Full name">
                  <input className={inputCls} required value={form.name} onChange={set("name")} data-testid="eval-name" />
                </Field>
                <Field label="Company">
                  <input className={inputCls} required value={form.company} onChange={set("company")} data-testid="eval-company" />
                </Field>
                <Field label="Business email">
                  <input type="email" className={inputCls} required value={form.business_email} onChange={set("business_email")} data-testid="eval-email" />
                </Field>
                <Field label="Industry">
                  <select className={inputCls} required value={form.industry} onChange={set("industry")} data-testid="eval-industry">
                    <option value="" disabled>Select an industry…</option>
                    {INDUSTRIES.map((i) => <option key={i} value={i}>{i}</option>)}
                  </select>
                </Field>
                <Field label="Intended use case">
                  <textarea className={`${inputCls} min-h-[96px]`} required minLength={5} value={form.use_case} onChange={set("use_case")}
                    placeholder="How do you plan to evaluate PFP?" data-testid="eval-usecase" />
                </Field>
                {err && <p className="text-sm text-red-600" data-testid="eval-error">{err}</p>}
                <button type="submit" disabled={submitting} data-testid="eval-submit"
                  className="w-full inline-flex items-center justify-center rounded-lg bg-slate-900 text-white px-5 py-3 text-sm font-medium hover:bg-slate-800 disabled:opacity-60">
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Request Access"}
                </button>
              </form>

              <form onSubmit={signIn} className="mt-6 pt-5 border-t border-slate-200 space-y-3" data-testid="evaluator-signin">
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">Already approved? Sign in</div>
                <input type="email" required placeholder="Business email" className={inputCls}
                  value={si.email} onChange={(e) => setSi((s) => ({ ...s, email: e.target.value }))} data-testid="signin-email" />
                <input type="password" required placeholder="Evaluation password" className={inputCls}
                  value={si.password} onChange={(e) => setSi((s) => ({ ...s, password: e.target.value }))} data-testid="signin-password" />
                {siErr && <p className="text-sm text-red-600" data-testid="signin-error">{siErr}</p>}
                <button type="submit" disabled={siBusy} data-testid="signin-submit"
                  className="inline-flex items-center justify-center rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                  {siBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Sign in to docs"}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
