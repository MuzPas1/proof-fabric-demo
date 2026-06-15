import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Loader2, AlertTriangle, ExternalLink } from "lucide-react";
import { DOCS_RES, CANONICAL } from "./docsData";
import { MarkdownView, extractHeadings } from "./MarkdownView";

export const DocContent = ({ item }) => {
  const location = useLocation();
  const [md, setMd] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [headings, setHeadings] = useState([]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetch(`${DOCS_RES}/${item.file}`)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`Could not load ${item.file} (${r.status})`))))
      .then((text) => {
        if (!active) return;
        setMd(text);
        setHeadings(extractHeadings(text));
        setLoading(false);
      })
      .catch((e) => { if (active) { setError(e.message); setLoading(false); } });
    return () => { active = false; };
  }, [item.file]);

  // Deep-link: scroll to #hash once content is rendered.
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
          <a href={`${DOCS_RES}/${item.file}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-slate-600">
            View raw <ExternalLink className="h-3 w-3" />
          </a>
          <span>·</span>
          <a href={CANONICAL.developers} className="hover:text-slate-600">Developer Portal</a>
          <span>·</span>
          <a href={CANONICAL.swagger} target="_blank" rel="noreferrer" className="hover:text-slate-600">API Docs</a>
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
