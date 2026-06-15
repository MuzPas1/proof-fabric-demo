import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ShieldCheck, Search, Menu, X, ChevronRight } from "lucide-react";
import { DOC_TREE, SLUG_MAP, TOP_NAV, CANONICAL } from "./docsData";
import { DocsSidebar } from "./DocsSidebar";
import { DocsSearch } from "./DocsSearch";
import { DocsHome } from "./DocsHome";
import { DocContent } from "./DocContent";
import { Releases } from "./Releases";
import { TrustOverview } from "./TrustOverview";

const Breadcrumbs = ({ item }) => {
  const navigate = useNavigate();
  if (!item) return null;
  return (
    <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-5" data-testid="docs-breadcrumbs">
      <button onClick={() => navigate("/docs")} className="hover:text-slate-600">Docs</button>
      <ChevronRight className="h-3 w-3" />
      <span className="text-slate-500">{item.categoryLabel}</span>
      <ChevronRight className="h-3 w-3" />
      <span className="text-slate-700 font-medium">{item.title}</span>
    </div>
  );
};

export default function DocsPortal() {
  const params = useParams();
  const navigate = useNavigate();
  const sub = (params["*"] || "").split("#")[0].replace(/\/$/, "");
  const slug = sub || "";
  const item = slug ? SLUG_MAP[slug] : null;

  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);

  useEffect(() => {
    document.title = item ? `${item.title} · PFP Docs` : "Documentation · Proof Fabric Protocol";
  }, [item]);

  // ⌘K / Ctrl+K opens search.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearchOpen(true); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => { setMobileNav(false); }, [slug]);

  // Unknown slug → bounce to docs home.
  useEffect(() => {
    if (slug && slug !== "releases" && !item) navigate("/docs", { replace: true });
  }, [slug, item, navigate]);

  const renderMain = () => {
    if (!slug) return <DocsHome onSearch={() => setSearchOpen(true)} />;
    if (slug === "releases" || item?.type === "releases") return <Releases />;
    if (item?.type === "page" && item.slug === "trust-overview") return <TrustOverview />;
    if (item?.type === "doc") return <><Breadcrumbs item={item} /><DocContent item={item} /></>;
    return <DocsHome onSearch={() => setSearchOpen(true)} />;
  };

  return (
    <div className="min-h-screen bg-white text-slate-900" data-testid="docs-portal">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur supports-[backdrop-filter]:bg-white/70">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-4">
          <button className="lg:hidden text-slate-600" onClick={() => setMobileNav((v) => !v)} data-testid="docs-mobile-nav-toggle" aria-label="Menu">
            {mobileNav ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <button onClick={() => navigate("/docs")} className="flex items-center gap-2 shrink-0" data-testid="docs-logo">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <ShieldCheck className="h-5 w-5 text-white" />
            </div>
            <span className="font-semibold text-slate-900 font-['Space_Grotesk']">PFP <span className="text-slate-400 font-normal">Docs</span></span>
          </button>

          <button
            onClick={() => setSearchOpen(true)}
            data-testid="docs-search-trigger"
            className="ml-2 hidden sm:flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-400 hover:border-slate-300 transition-colors min-w-[200px]"
          >
            <Search className="h-4 w-4" /> Search…
            <kbd className="ml-auto rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] font-medium text-slate-500">⌘K</kbd>
          </button>

          <nav className="ml-auto hidden md:flex items-center gap-1">
            {TOP_NAV.map((n) => (
              <a
                key={n.label}
                href={n.href}
                target={n.external ? "_blank" : undefined}
                rel={n.external ? "noreferrer" : undefined}
                onClick={n.external ? undefined : (e) => { e.preventDefault(); navigate(n.href); }}
                data-testid={`docs-topnav-${n.label.toLowerCase().replace(/\s+/g, "-")}`}
                className="px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-md hover:bg-slate-100 transition-colors"
              >
                {n.label}
              </a>
            ))}
          </nav>
          <button onClick={() => setSearchOpen(true)} className="sm:hidden ml-auto text-slate-600" aria-label="Search"><Search className="h-5 w-5" /></button>
        </div>
      </header>

      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 flex">
        {/* Sidebar (desktop) */}
        <aside className="hidden lg:block w-64 shrink-0 py-10 pr-6 border-r border-slate-100 sticky top-16 self-start max-h-[calc(100vh-4rem)] overflow-y-auto">
          <DocsSidebar activeSlug={slug} />
        </aside>

        {/* Sidebar (mobile drawer) */}
        {mobileNav && (
          <div className="lg:hidden fixed inset-0 z-30 top-16" data-testid="docs-mobile-drawer">
            <div className="absolute inset-0 bg-slate-900/30" onClick={() => setMobileNav(false)} />
            <div className="absolute top-0 left-0 bottom-0 w-72 bg-white border-r border-slate-200 overflow-y-auto p-5">
              <DocsSidebar activeSlug={slug} onNavigate={() => setMobileNav(false)} />
            </div>
          </div>
        )}

        {/* Main */}
        <main className="flex-1 min-w-0 py-10 lg:pl-10">
          {renderMain()}
          <footer className="mt-16 pt-6 border-t border-slate-100 text-xs text-slate-400 flex flex-wrap gap-x-4 gap-y-2">
            <span>© Proof Fabric Protocol</span>
            <a href={CANONICAL.website} target="_blank" rel="noreferrer" className="hover:text-slate-600">pfprotocol.com</a>
            <a href={CANONICAL.developers} onClick={(e) => { e.preventDefault(); navigate(CANONICAL.developers); }} className="hover:text-slate-600">Developer Portal</a>
            <a href={CANONICAL.swagger} target="_blank" rel="noreferrer" className="hover:text-slate-600">API Reference</a>
            <button onClick={() => navigate("/docs/releases")} className="hover:text-slate-600">Release Notes</button>
          </footer>
        </main>
      </div>

      <DocsSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
