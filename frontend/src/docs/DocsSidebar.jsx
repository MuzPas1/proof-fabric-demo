import React from "react";
import { useNavigate } from "react-router-dom";
import {
  Rocket, Code, Network, ShieldCheck, Boxes, ServerCog, Scale, FileJson, Tag, ExternalLink,
} from "lucide-react";
import { DOC_TREE } from "./docsData";

const ICONS = { Rocket, Code, Network, ShieldCheck, Boxes, ServerCog, Scale, FileJson, Tag };

export const DocsSidebar = ({ activeSlug, onNavigate }) => {
  const navigate = useNavigate();

  const go = (item) => {
    if (item.type === "link") {
      if (item.internal) navigate(item.href);
      else window.open(item.href, "_blank", "noopener");
    } else {
      navigate(`/docs/${item.slug}`);
    }
    onNavigate && onNavigate();
  };

  return (
    <nav className="text-sm" data-testid="docs-sidebar">
      {DOC_TREE.map((cat) => {
        const Icon = ICONS[cat.icon] || Rocket;
        return (
          <div key={cat.id} className="mb-6">
            <div className="flex items-center gap-2 px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
              <Icon className="h-3.5 w-3.5" /> {cat.label}
            </div>
            <ul className="space-y-0.5">
              {cat.items.map((item) => {
                const isLink = item.type === "link";
                const active = !isLink && item.slug === activeSlug;
                return (
                  <li key={`${cat.id}-${item.slug}`}>
                    <button
                      onClick={() => go(item)}
                      data-testid={`docs-nav-${cat.id}-${item.slug}`}
                      className={`w-full text-left flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-colors ${
                        active
                          ? "bg-blue-50 text-blue-700 font-medium"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                      }`}
                    >
                      <span className="truncate">{item.title}</span>
                      {isLink && !item.internal && <ExternalLink className="h-3 w-3 shrink-0 text-slate-400" />}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
};
