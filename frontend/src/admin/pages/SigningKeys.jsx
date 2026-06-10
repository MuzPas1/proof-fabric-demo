import React, { useEffect, useState } from "react";
import { api } from "../api";
import { PageHeader, Panel, StatusBadge, Empty, Mono } from "../ui";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { RefreshCw, Loader2, Copy } from "lucide-react";
import { toast } from "sonner";

export default function SigningKeys() {
  const [keys, setKeys] = useState(null);
  const [rotated, setRotated] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.listSigningKeys().then((d) => setKeys(d.keys || [])).catch(() => setKeys([]));
  useEffect(() => { load(); }, []);

  const rotate = async () => {
    setBusy(true);
    try {
      const res = await api.rotateKey();
      setRotated(res);
      toast.success("Signing key rotated");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Rotate failed"); }
    finally { setBusy(false); }
  };

  const act = async (fn, kid, verb) => {
    try { await fn(kid); toast.success(`Key ${verb}`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || `Failed to ${verb}`); }
  };

  return (
    <div data-testid="signing-keys-page">
      <PageHeader title="Signing Keys" description="Ed25519 key registry. Retired keys still verify history; revoked keys fail verification."
        actions={
          <Button onClick={rotate} disabled={busy} className="bg-slate-900 hover:bg-slate-800" data-testid="rotate-key-btn">
            {busy ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1.5" />} Rotate Key
          </Button>
        } />

      <Panel>
        {keys === null ? <Empty>Loading…</Empty> : keys.length === 0 ? <Empty>No keys</Empty> : (
          <table className="w-full text-sm" data-testid="signing-keys-table">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-200">
                <th className="px-4 py-2.5 font-medium">Key ID</th>
                <th className="px-4 py-2.5 font-medium">Algorithm</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Created</th>
                <th className="px-4 py-2.5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {keys.map((k) => (
                <tr key={k.public_key_id} data-testid={`signing-key-row-${k.public_key_id}`}>
                  <td className="px-4 py-2.5"><Mono>{k.public_key_id}</Mono></td>
                  <td className="px-4 py-2.5 text-slate-600">{k.algorithm || "Ed25519"}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={k.status} /></td>
                  <td className="px-4 py-2.5 text-slate-500">{k.created_at ? String(k.created_at).slice(0, 10) : "—"}</td>
                  <td className="px-4 py-2.5 text-right space-x-2">
                    {k.status === "active" && (
                      <Button variant="outline" size="sm" className="h-7 text-amber-700 border-amber-200 hover:bg-amber-50"
                        onClick={() => act(api.retireKey, k.public_key_id, "retired")}
                        data-testid={`retire-${k.public_key_id}`}>Retire</Button>
                    )}
                    {k.status !== "revoked" && (
                      <Button variant="outline" size="sm" className="h-7 text-red-600 border-red-200 hover:bg-red-50"
                        onClick={() => act(api.revokeKey, k.public_key_id, "revoked")}
                        data-testid={`revoke-${k.public_key_id}`}>Revoke</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Dialog open={!!rotated} onOpenChange={(o) => !o && setRotated(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>New signing key generated</DialogTitle>
            <DialogDescription>Deploy the new seed to your KMS, then restart to sign with it.</DialogDescription>
          </DialogHeader>
          {rotated && (
            <div className="py-2 space-y-3 text-sm">
              <div>New key ID: <Mono>{rotated.new_public_key_id}</Mono></div>
              <div>
                <div className="text-slate-600 mb-1">New private seed (shown once — deploy to KMS, then restart):</div>
                <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-md p-2">
                  <code className="text-xs text-slate-800 break-all flex-1">{rotated.new_private_seed_b64}</code>
                  <button onClick={() => { navigator.clipboard.writeText(rotated.new_private_seed_b64); toast.success("Copied"); }}>
                    <Copy className="h-4 w-4 text-slate-500" />
                  </button>
                </div>
              </div>
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2">{rotated.action_required}</p>
              <DialogFooter><Button variant="outline" onClick={() => setRotated(null)}>Done</Button></DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
