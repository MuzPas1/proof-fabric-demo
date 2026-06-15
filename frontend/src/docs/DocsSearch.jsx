import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Loader2, X, FileText, Hash } from "lucide-react";
import { DOCS_RES, SEARCHABLE_DOCS, CATEGORIES, slugify } from "./docsData";

// Lazily fetched, cached search index shared across opens.
let INDEX_CACHE = null;
let INDEX_PROMISE = null;

const buildIndex = async () => {
  if (INDEX_CACHE) return INDEX_CACHE;
  if (INDEX_PROMISE) return INDEX_PROMISE;
  INDEX_PROMISE = (async () => {
    const entries = [];
    await Promise.all(
      SEARCHABLE_DOCS.map(async (d) => {
        try {
          const res = await fetch(`${DOCS_RES}/${d.file}`);
          const text = res.ok ? await res.text() : "";
          // Document-level entry
          entries.push({ slug: d.slug, title: d.title, category: d.category, kind: "doc", text: text.toLowerCase(), preview: text.replace(/[#*`>_\-]/g, " ").replace(/\s+/g, " ").trim().slice(0, 160) });
          // Heading-level entries (deep links)
          let inFence = false;
          for (const line of text.split("\n")) {
            if (/^```/.test(line.trim())) { inFence = !inFence; continue; }
            if (inFence) continue;
            const m = /^(#{2,3})\s+(.*)$/.exec(line);
            if (m) {
              const ht = m[2].replace(/[#*`]/g, "").trim();
              if (ht) entries.push({ slug: d.slug, title: ht, category: d.category, kind: "heading", hash: slugify(ht), text: ht.toLowerCase(), parent: d.title });
            }
          }
        } catch (_) {}
      })
    );
    INDEX_CACHE = entries;
    return entries;
  })();
  return INDEX_PROMISE;
};

export const DocsSearch = ({ open, onClose }) => {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [index, setIndex] = useState(INDEX_CACHE);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      if (!INDEX_CACHE) {
        setLoading(true);
        buildIndex().then((idx) => { setIndex(idx); setLoading(false); });
      }
    }
  }, [open]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const results = useMemo(() => {
    if (!index || !q.trim()) return [];
    const needle = q.trim().toLowerCase();
    const scored = [];
    for (const e of index) {
      if (cat !== "all" && e.category !== cat) continue;
      const titleHit = e.title.toLowerCase().includes(needle);
      const textHit = e.text.includes(needle);
      if (!titleHit && !textHit) continue;
      let score = 0;
      if (titleHit) score += e.kind === "doc" ? 100 : 60;
      if (textHit) score += 10;
      scored.push({ ...e, score });
    }
    return scored.sort((a, b) => b.score - a.score).slice(0, 40);
  }, [index, q, cat]);

  if (!open) return null;

  const goTo = (r) => {
    navigate(`/docs/${r.slug}${r.hash ? "#" + r.hash : ""}`);
    onClose();
    setQ("");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[8vh] px-4 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} data-testid="docs-search-modal">
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl ring-1 ring-slate-200 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100">
          <Search className="h-5 w-5 text-slate-400 shrink-0" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search documentation, releases, architecture…"
            data-testid="docs-search-input"
            className="flex-1 bg-transparent outline-none text-[15px] text-slate-800 placeholder:text-slate-400"
          />
          {loading && <Loader2 className="h-4 w-4 text-slate-400 animate-spin" />}
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700" aria-label="Close"><X className="h-5 w-5" /></button>
        </div>

        <div className="flex items-center gap-1.5 px-4 py-2 border-b border-slate-100 overflow-x-auto">
          {["all", ...CATEGORIES].map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              data-testid={`docs-search-filter-${slugify(c)}`}
              className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                cat === c ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {c === "all" ? "All" : c}
            </button>
          ))}
        </div>

        <div className="max-h-[55vh] overflow-y-auto p-2" data-testid="docs-search-results">
          {q.trim() && results.length === 0 && !loading && (
            <div className="px-4 py-8 text-center text-sm text-slate-400">No results for "{q}"</div>
          )}
          {!q.trim() && (
            <div className="px-4 py-8 text-center text-sm text-slate-400">Type to search across all documentation.</div>
          )}
          {results.map((r, i) => (
            <button
              key={i}
              onClick={() => goTo(r)}
              data-testid="docs-search-result"
              className="w-full text-left flex items-start gap-3 rounded-lg px-3 py-2.5 hover:bg-slate-50 transition-colors"
            >
              {r.kind === "doc" ? <FileText className="h-4 w-4 mt-0.5 text-blue-500 shrink-0" /> : <Hash className="h-4 w-4 mt-0.5 text-slate-400 shrink-0" />}
              <div className="min-w-0">
                <div className="text-sm font-medium text-slate-800 truncate">
                  {r.title}
                  {r.kind === "heading" && <span className="text-slate-400 font-normal"> · {r.parent}</span>}
                </div>
                <div className="text-xs text-slate-400 truncate">{r.category}{r.kind === "doc" && r.preview ? ` — ${r.preview}` : ""}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
