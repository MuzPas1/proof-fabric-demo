import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { JsonViewer } from "@/components/JsonViewer";
import { Loader2, Search, Copy, Globe, CheckCircle2, XCircle } from "lucide-react";

export const PublicVerify = ({ apiUrl }) => {
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [feaId, setFeaId] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResponse(null);

    try {
      const res = await axios.get(`${apiUrl}/public/verify/${feaId.trim()}`);
      setResponse({ status: res.status, data: res.data });
      toast.success("FEA retrieved successfully");
    } catch (error) {
      const errData = error.response?.data || { detail: error.message };
      setResponse({ 
        status: error.response?.status || 500, 
        data: errData,
        error: true 
      });
      toast.error(errData.detail || "Failed to retrieve FEA");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="public-verify-panel">
      {/* Form Panel */}
      <div className="bg-[#09090b] border border-zinc-800 rounded-sm">
        <div className="border-b border-zinc-800 p-4 bg-zinc-900/50">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-semibold text-white font-['Space_Grotesk'] uppercase tracking-wider">
              Public Verify
            </h2>
          </div>
          <p className="text-xs text-zinc-500 mt-1">GET /api/public/verify/{'{fea_id}'}</p>
          <p className="text-xs text-blue-400/70 mt-2">No authentication required</p>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
              FEA ID (UUID) *
            </Label>
            <Input
              value={feaId}
              onChange={(e) => setFeaId(e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="bg-black border-zinc-800 text-white font-mono text-sm"
              required
              data-testid="input-fea-id"
            />
            <p className="text-xs text-zinc-600">
              Enter the FEA ID returned from a previous generate request
            </p>
          </div>

          <Button 
            type="submit" 
            disabled={loading}
            className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm font-medium uppercase tracking-wider"
            data-testid="btn-public-verify"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Looking up...
              </>
            ) : (
              <>
                <Search className="w-4 h-4 mr-2" />
                Lookup FEA
              </>
            )}
          </Button>
        </form>

        {/* Info Box */}
        <div className="mx-6 mb-6 p-4 bg-zinc-900/50 border border-zinc-800 rounded">
          <p className="text-xs text-zinc-400 font-mono">
            Public verification allows anyone to verify an FEA's authenticity without API credentials.
            Only the FEA hash, signature validity, timestamp, and issuer are revealed.
          </p>
        </div>
      </div>

      {/* Response Panel */}
      <div className="bg-[#09090b] border border-zinc-800 rounded-sm">
        <div className="border-b border-zinc-800 p-4 bg-zinc-900/50 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white font-['Space_Grotesk'] uppercase tracking-wider">
              Public Verification Result
            </h2>
            {response && (
              <p className={`text-xs mt-1 ${response.error ? 'text-red-400' : 'text-green-400'}`}>
                Status: {response.status}
              </p>
            )}
          </div>
          {response?.data && !response.error && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => copyToClipboard(JSON.stringify(response.data, null, 2))}
              className="text-zinc-400 hover:text-white"
              data-testid="btn-copy-public-response"
            >
              <Copy className="w-4 h-4 mr-1" />
              Copy
            </Button>
          )}
        </div>
        
        <div className="p-4">
          {response?.data && !response.error ? (
            <div className="space-y-4">
              {/* Signature Status */}
              <div className={`p-4 rounded border ${
                response.data.signature_valid 
                  ? 'bg-green-500/10 border-green-500/30' 
                  : 'bg-red-500/10 border-red-500/30'
              }`}>
                <div className="flex items-center gap-3">
                  {response.data.signature_valid ? (
                    <CheckCircle2 className="w-6 h-6 text-green-500" />
                  ) : (
                    <XCircle className="w-6 h-6 text-red-500" />
                  )}
                  <div>
                    <p className={`font-semibold ${response.data.signature_valid ? 'text-green-400' : 'text-red-400'}`}>
                      {response.data.signature_valid ? 'Signature Valid' : 'Signature Invalid'}
                    </p>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Issuer: {response.data.issuer_id}
                    </p>
                  </div>
                </div>
              </div>

              {/* Details */}
              <div className="space-y-3">
                <div className="p-3 bg-zinc-900/50 rounded border border-zinc-800">
                  <p className="text-xs text-zinc-500 font-mono uppercase mb-1">FEA Hash</p>
                  <code className="text-xs text-green-400 break-all" data-testid="fea-hash-display">
                    {response.data.fea_hash}
                  </code>
                </div>
                <div className="p-3 bg-zinc-900/50 rounded border border-zinc-800">
                  <p className="text-xs text-zinc-500 font-mono uppercase mb-1">Timestamp</p>
                  <code className="text-xs text-blue-400">
                    {response.data.timestamp}
                  </code>
                </div>
              </div>

              {/* Full Response */}
              <div>
                <p className="text-xs text-zinc-500 mb-2 font-mono uppercase">Full Response</p>
                <JsonViewer data={response.data} />
              </div>
            </div>
          ) : response?.error ? (
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded">
              <p className="text-red-400 text-sm font-medium">Error</p>
              <p className="text-xs text-zinc-400 mt-1">
                {response.data.detail || "FEA not found"}
              </p>
            </div>
          ) : (
            <div className="text-center py-12 text-zinc-600">
              <Globe className="w-12 h-12 mx-auto mb-4 opacity-20" />
              <p className="font-mono text-sm">No result</p>
              <p className="text-xs mt-1">Enter an FEA ID to verify publicly</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
