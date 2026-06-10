import React from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthContext";
import Layout from "./Layout";
import Login from "./Login";
import Overview from "./pages/Overview";
import Tenants from "./pages/Tenants";
import ApiKeys from "./pages/ApiKeys";
import SigningKeys from "./pages/SigningKeys";
import ProofExplorer from "./pages/ProofExplorer";
import Webhooks from "./pages/Webhooks";
import Audit from "./pages/Audit";
import { Loader2 } from "lucide-react";

function Protected({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }
  if (!user) return <Navigate to="/admin/login" state={{ from: location }} replace />;
  return <Layout>{children}</Layout>;
}

export default function AdminApp() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="login" element={<Login />} />
        <Route path="" element={<Protected><Overview /></Protected>} />
        <Route path="tenants" element={<Protected><Tenants /></Protected>} />
        <Route path="api-keys" element={<Protected><ApiKeys /></Protected>} />
        <Route path="signing-keys" element={<Protected><SigningKeys /></Protected>} />
        <Route path="proofs" element={<Protected><ProofExplorer /></Protected>} />
        <Route path="webhooks" element={<Protected><Webhooks /></Protected>} />
        <Route path="audit" element={<Protected><Audit /></Protected>} />
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </AuthProvider>
  );
}
