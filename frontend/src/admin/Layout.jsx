import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { ReadOnlyBadge } from "./ui";
import {
  LayoutDashboard, Building2, KeyRound, Webhook, ScrollText,
  Fingerprint, FileSearch, ShieldCheck, LogOut, ExternalLink,
} from "lucide-react";

const NAV = [
  { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/admin/tenants", label: "Tenants", icon: Building2 },
  { to: "/admin/api-keys", label: "API Keys", icon: KeyRound },
  { to: "/admin/signing-keys", label: "Signing Keys", icon: Fingerprint },
  { to: "/admin/proofs", label: "Proof Explorer", icon: FileSearch },
  { to: "/admin/webhooks", label: "Webhooks", icon: Webhook },
  { to: "/admin/audit", label: "Audit Log", icon: ScrollText },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      <aside className="w-60 bg-white border-r border-slate-200 flex flex-col fixed inset-y-0">
        <div className="h-14 flex items-center gap-2 px-4 border-b border-slate-200">
          <div className="h-7 w-7 rounded-md bg-slate-900 flex items-center justify-center">
            <ShieldCheck className="h-4 w-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900 leading-none">PFP Admin</div>
            <div className="text-[11px] text-slate-400 leading-none mt-0.5">Control Plane</div>
          </div>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive ? "bg-slate-100 text-slate-900 font-medium" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`
              }>
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-2 py-3 border-t border-slate-200">
          <a href="/" target="_blank" rel="noreferrer"
            className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-slate-600 hover:bg-slate-50">
            <ExternalLink className="h-4 w-4" /> Demo Portal
          </a>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 ml-60">
        <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 sticky top-0 z-10">
          <div className="text-sm text-slate-500">Enterprise Administration</div>
          <div className="flex items-center gap-4">
            {!["super_admin", "tenant_admin"].includes(user?.role) && <ReadOnlyBadge />}
            <div className="text-right">
              <div className="text-sm font-medium text-slate-900 leading-none" data-testid="current-user-email">{user?.email}</div>
              <div className="text-[11px] text-slate-400 leading-none mt-0.5">
                {user?.role} · tenant: {user?.tenant_id}
              </div>
            </div>
            <button onClick={() => { logout(); navigate("/admin/login"); }}
              data-testid="logout-button"
              className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 border border-slate-200 rounded-md px-3 py-1.5">
              <LogOut className="h-3.5 w-3.5" /> Logout
            </button>
          </div>
        </header>
        <main className="p-6 max-w-6xl">{children}</main>
      </div>
    </div>
  );
}
