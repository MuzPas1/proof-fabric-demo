import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Loader2, AlertTriangle, ExternalLink, Lock } from "lucide-react";
import { DOCS_RES, CANONICAL } from "./docsData";
import { MarkdownView, extractHeadings } from "./MarkdownView";
import { getDocsToken, docsLogin } from "./docsAuth";

const EnterpriseGate = ({ onAuthed }) => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const signIn = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await docsLogin(email, password); onAuthed(); }
    catch (e2) { setErr(e2.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="py-12 max-w-lg mx-auto text-center" data-testid="enterprise-gate">
      <div className="h-12 w-12 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center mx-auto">
        <Lock className="h-6 w-6 text-amber-500" />
      </div>
      <h2 className="mt-4 text-xl font-semibold text-slate-900">Enterprise Evaluation material</h2>
      <p className="mt-2 text-sm text-slate-500">
        This document is part of PFP's Enterprise Evaluation package (architecture, security,
        integration & SDK materials). Request access or sign in with your evaluation account.
      </p>
      <button
        onClick={() => navigate("/evaluation")}
        data-testid="gate-request-access"
        className="mt-5 inline-flex items-center justify-center rounded-lg bg-slate-900 text-white px-5 py-2.5 text-sm font-medium hover:bg-slate-800"
      >
        Request Enterprise Access
      </button>

      <form onSubmit={signIn} className="mt-8 text-left border-t border-slate-200 pt-6 space-y-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">Already approved? Sign in</div>
        <input
          type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="Business email" data-testid="gate-email"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
          placeholder="Evaluation password" data-testid="gate-password"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        {err && <p className="text-sm text-red-600" data-testid="gate-error">{err}</p>}
        <button
          type="submit" disabled={busy} data-testid="gate-signin"
          className="inline-flex items-center justify-center rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Sign in"}
        </button>
      </form>
    </div>
  );
};

export const DocContent = ({ item }) => {
  const location = useLocation();
  const [md, setMd] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [gated, setGated] = useState(false);
  const [headings, setHeadings] = useState([]);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(null); setGated(false);
    const token = getDocsToken();
    const opts = token ? { headers: { Authorization: `Bearer ${token}` } } : {};
    fetch(`${DOCS_RES}/${item.file}`, opts)
      .then((r) => {
        if (r.status === 403) { if (active) { setGated(true); setLoading(false); } return null; }
        if (!r.ok) return Promise.reject(new Error(`Could not load ${item.file} (${r.status})`));
        return r.text();
      })
      .then((text) => {
        if (!active || text === null) return;
        setMd(text);
        setHeadings(extractHeadings(text));
        setLoading(false);
      })
      .catch((e) => { if (active) { setError(e.message); setLoading(false); } });
    return () => { active = false; };
  }, [item.file, reloadKey]);

  useEffect(() => {
    if (loading) return;
    const hash = location.hash?.replace("#", "");
    if (hash) {
      requestAnimationFrame(() => {
        const el = document.getElementById(hash);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } else {
      window.scrollTo({ top: 0 });
    }
  }, [loading, location.hash, item.file]);

  if (loading) {
    return <div className="flex items-center gap-2 text-slate-400 py-20 justify-center" data-testid="doc-loading"><Loader2 className="h-5 w-5 animate-spin" /> Loading…</div>;
  }
  if (gated) {
    return <EnterpriseGate onAuthed={() => setReloadKey((k) => k + 1)} />;
  }
  if (error) {
    return (
      <div className="py-16 max-w-xl mx-auto text-center" data-testid="doc-error">
        <AlertTriangle className="h-8 w-8 text-amber-500 mx-auto" />
        <p className="mt-3 text-slate-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex gap-10">
      <article className="min-w-0 flex-1 max-w-3xl" data-testid="doc-content">
        <MarkdownView markdown={md} />
        <div className="mt-12 pt-6 border-t border-slate-200 text-sm text-slate-400 flex items-center gap-2">
          <a href={CANONICAL.developers} className="hover:text-slate-600">Developer Portal</a>
          <span>·</span>
          <a href={CANONICAL.swagger} target="_blank" rel="noreferrer" className="hover:text-slate-600">Public API Docs</a>
        </div>
      </article>

      {headings.length > 1 && (
        <aside className="hidden xl:block w-56 shrink-0" data-testid="doc-toc">
          <div className="sticky top-24">
            <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400 mb-3">On this page</div>
            <ul className="space-y-1.5 text-sm border-l border-slate-200">
              {headings.map((h, i) => (
                <li key={i} className={h.level === 3 ? "pl-6" : "pl-3"}>
                  <a href={`#${h.id}`} className="block text-slate-500 hover:text-blue-600 transition-colors -ml-px border-l-2 border-transparent hover:border-blue-500 pl-2 truncate">
                    {h.text}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      )}
    </div>
  );
};
