import React, { useEffect, useState } from "react";
import { Loader2, Tag } from "lucide-react";
import { DOCS_RES } from "./docsData";
import { MarkdownView } from "./MarkdownView";

export const Releases = () => {
  const [md, setMd] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${DOCS_RES}/RELEASE_NOTES.md`)
      .then((r) => (r.ok ? r.text() : ""))
      .then((t) => { setMd(t); setLoading(false); })
      .catch(() => setLoading(false));
    window.scrollTo({ top: 0 });
  }, []);

  return (
    <div className="max-w-3xl" data-testid="docs-releases">
      <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20 px-3 py-1 text-sm font-medium">
        <Tag className="h-3.5 w-3.5" /> Release Notes
      </div>
      {loading ? (
        <div className="flex items-center gap-2 text-slate-400 py-20 justify-center"><Loader2 className="h-5 w-5 animate-spin" /> Loading…</div>
      ) : (
        <div className="mt-4"><MarkdownView markdown={md} /></div>
      )}
    </div>
  );
};
