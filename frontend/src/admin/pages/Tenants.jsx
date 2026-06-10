import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { PageHeader, Panel, StatusBadge, Empty, Mono } from "../ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import { Plus, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Tenants() {
  const { user } = useAuth();
  const [tenants, setTenants] = useState(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const isSuper = user?.role === "super_admin";

  const load = () => api.listTenants().then((d) => setTenants(d.tenants || [])).catch(() => setTenants([]));
  useEffect(() => { load(); }, []);

  const create = async () => {
    setBusy(true);
    try {
      await api.createTenant(name.trim());
      toast.success("Tenant created");
      setOpen(false); setName(""); load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to create tenant");
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="tenants-page">
      <PageHeader title="Tenants" description="Customer isolation boundaries."
        actions={isSuper && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-slate-900 hover:bg-slate-800" data-testid="create-tenant-open">
                <Plus className="h-4 w-4 mr-1.5" /> New Tenant
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Create tenant</DialogTitle>
                <DialogDescription>Define a new customer isolation boundary.</DialogDescription>
              </DialogHeader>
              <div className="space-y-3 py-2">
                <Label htmlFor="tname">Tenant name</Label>
                <Input id="tname" value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="Acme Bank" data-testid="create-tenant-name" />
              </div>
              <DialogFooter>
                <Button onClick={create} disabled={busy || !name.trim()}
                  className="bg-slate-900 hover:bg-slate-800" data-testid="create-tenant-submit">
                  {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Create
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )} />

      <Panel>
        {tenants === null ? <Empty>Loading…</Empty> : tenants.length === 0 ? <Empty>No tenants</Empty> : (
          <table className="w-full text-sm" data-testid="tenants-table">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                <th className="px-4 py-2.5 font-medium">Tenant ID</th>
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tenants.map((t) => (
                <tr key={t.tenant_id} data-testid={`tenant-row-${t.tenant_id}`}>
                  <td className="px-4 py-2.5"><Mono>{t.tenant_id}</Mono></td>
                  <td className="px-4 py-2.5 text-slate-800">{t.name}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={t.status} /></td>
                  <td className="px-4 py-2.5 text-slate-500">{String(t.created_at).slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
