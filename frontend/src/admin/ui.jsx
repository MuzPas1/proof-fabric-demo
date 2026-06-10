import React from "react";

export function PageHeader({ title, description, actions }) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {description && <p className="text-sm text-slate-500 mt-1">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Panel({ title, children, className = "" }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-lg ${className}`}>
      {title && <div className="px-4 py-3 border-b border-slate-200 text-sm font-medium text-slate-900">{title}</div>}
      {children}
    </div>
  );
}

const STATUS_STYLES = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  revoked: "bg-red-50 text-red-700 border-red-200",
  retired: "bg-amber-50 text-amber-700 border-amber-200",
  suspended: "bg-slate-100 text-slate-600 border-slate-200",
};

export function StatusBadge({ status }) {
  const cls = STATUS_STYLES[status] || "bg-slate-100 text-slate-600 border-slate-200";
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

export function StatCard({ label, value, sub, accent }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-semibold mt-2 ${accent || "text-slate-900"}`}>{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

export function Empty({ children }) {
  return <div className="px-4 py-10 text-center text-sm text-slate-400">{children}</div>;
}

export function Mono({ children }) {
  return <span className="font-mono text-xs text-slate-600">{children}</span>;
}

// Roles permitted to perform write operations in the UI. Backend enforces too.
export const canWrite = (role) => ["super_admin", "tenant_admin"].includes(role);

export function ReadOnlyBadge() {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
      data-testid="readonly-badge">
      Read-only
    </span>
  );
}
