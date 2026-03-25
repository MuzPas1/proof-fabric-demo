import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { JsonViewer } from "@/components/JsonViewer";
import { Loader2, ShieldCheck, Copy, AlertCircle, CheckCircle2 } from "lucide-react";

export const VerifyFEA = ({ apiKey, apiUrl }) => {
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [feaPayload, setFeaPayload] = useState("");
  const [signature, setSignature] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResponse(null);

    try {
      let parsedPayload;
      try {
        parsedPayload = JSON.parse(feaPayload);
      } catch {
        toast.error("Invalid JSON in FEA payload");
        setLoading(false);
        return;
      }

      const payload = {
        fea_payload: parsedPayload,
        signature: signature.trim()
      };

      const res = await axios.post(`${apiUrl}/fea/verify`, payload, {
        headers: {
          "X-API-Key": apiKey,
          "Content-Type": "application/json"
        }
      });

      setResponse({ status: res.status, data: res.data });
      if (res.data.valid) {
        toast.success("Signature verified successfully");
      } else {
        toast.error(`Verification failed: ${res.data.reason}`);
      }
    } catch (error) {
      const errData = error.response?.data || { detail: error.message };
      setResponse({ 
        status: error.response?.status || 500, 
        data: errData,
        error: true 
      });
      toast.error(errData.detail || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="verify-fea-panel">
      {/* Form Panel */}
      <div className="bg-[#09090b] border border-zinc-800 rounded-sm">
        <div className="border-b border-zinc-800 p-4 bg-zinc-900/50">
          <h2 className="text-sm font-semibold text-white font-['Space_Grotesk'] uppercase tracking-wider">
            Verify FEA
          </h2>
          <p className="text-xs text-zinc-500 mt-1">POST /api/fea/verify</p>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
              FEA Payload (JSON) *
            </Label>
            <Textarea
              value={feaPayload}
              onChange={(e) => setFeaPayload(e.target.value)}
              placeholder={`{
  "fea_version": "1.0",
  "issuer_id": "pfp-issuer-001",
  "public_key_id": "key_...",
  "transaction_summary": {...},
  "parties": {...},
  "fea_hash": "..."
}`}
              className="bg-black border-zinc-800 text-white font-mono text-xs min-h-[240px]"
              required
              data-testid="input-fea-payload"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
              Signature (Base64) *
            </Label>
            <Textarea
              value={signature}
              onChange={(e) => setSignature(e.target.value)}
              placeholder="Base64 encoded Ed25519 signature..."
              className="bg-black border-zinc-800 text-white font-mono text-xs min-h-[80px]"
              required
              data-testid="input-signature"
            />
          </div>

          <Button 
            type="submit" 
            disabled={loading}
            className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm font-medium uppercase tracking-wider"
            data-testid="btn-verify-fea"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Verifying...
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4 mr-2" />
                Verify Signature
              </>
            )}
          </Button>
        </form>
      </div>

      {/* Response Panel */}
      <div className="bg-[#09090b] border border-zinc-800 rounded-sm">
        <div className="border-b border-zinc-800 p-4 bg-zinc-900/50 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white font-['Space_Grotesk'] uppercase tracking-wider">
              Verification Result
            </h2>
            {response && (
              <p className={`text-xs mt-1 ${response.error ? 'text-red-400' : 'text-green-400'}`}>
                Status: {response.status}
              </p>
            )}
          </div>
          {response?.data && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => copyToClipboard(JSON.stringify(response.data, null, 2))}
              className="text-zinc-400 hover:text-white"
              data-testid="btn-copy-verify-response"
            >
              <Copy className="w-4 h-4 mr-1" />
              Copy
            </Button>
          )}
        </div>
        
        <div className="p-4">
          {response?.data ? (
            <div className="space-y-4">
              {/* Verification Status Banner */}
              <div className={`p-4 rounded border ${
                response.data.valid 
                  ? 'bg-green-500/10 border-green-500/30' 
                  : 'bg-red-500/10 border-red-500/30'
              }`}>
                <div className="flex items-center gap-3">
                  {response.data.valid ? (
                    <CheckCircle2 className="w-6 h-6 text-green-500" />
                  ) : (
                    <AlertCircle className="w-6 h-6 text-red-500" />
                  )}
                  <div>
                    <p className={`font-semibold ${response.data.valid ? 'text-green-400' : 'text-red-400'}`}>
                      {response.data.valid ? 'Signature Valid' : 'Signature Invalid'}
                    </p>
                    {response.data.reason && (
                      <p className="text-xs text-zinc-400 mt-0.5">{response.data.reason}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Full Response */}
              <div>
                <p className="text-xs text-zinc-500 mb-2 font-mono uppercase">Full Response</p>
                <JsonViewer data={response.data} />
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-zinc-600">
              <ShieldCheck className="w-12 h-12 mx-auto mb-4 opacity-20" />
              <p className="font-mono text-sm">No verification result</p>
              <p className="text-xs mt-1">Paste an FEA payload and signature to verify</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
