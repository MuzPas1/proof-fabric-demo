import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShieldCheck, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email.trim(), password);
      toast.success("Signed in");
      navigate("/admin");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Invalid email or password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-8 justify-center">
          <div className="h-9 w-9 rounded-md bg-slate-900 flex items-center justify-center">
            <ShieldCheck className="h-5 w-5 text-white" />
          </div>
          <div className="text-left">
            <div className="text-sm font-semibold text-slate-900 leading-tight">Proof Fabric Protocol</div>
            <div className="text-xs text-slate-500 leading-tight">Admin Control Plane</div>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg shadow-sm p-6">
          <h1 className="text-base font-semibold text-slate-900 mb-1">Sign in</h1>
          <p className="text-sm text-slate-500 mb-5">Enterprise administrator access.</p>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="email" className="text-slate-700">Email</Label>
              <Input id="email" type="email" autoComplete="username" value={email}
                onChange={(e) => setEmail(e.target.value)} required
                className="mt-1" data-testid="admin-login-email" />
            </div>
            <div>
              <Label htmlFor="password" className="text-slate-700">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} required
                className="mt-1" data-testid="admin-login-password" />
            </div>
            <Button type="submit" disabled={busy} className="w-full bg-slate-900 hover:bg-slate-800"
              data-testid="admin-login-submit">
              {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Sign in
            </Button>
          </form>
        </div>
        <p className="text-center text-xs text-slate-400 mt-4">JWT + RBAC · session secured</p>
      </div>
    </div>
  );
}
