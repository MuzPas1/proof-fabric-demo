import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/JsonViewer";
import { Loader2, Send, Copy, RefreshCw } from "lucide-react";

export const GenerateFEA = ({ apiKey, apiUrl }) => {
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [request, setRequest] = useState(null);
  
  const [formData, setFormData] = useState({
    idempotency_key: "",
    transaction_id: "",
    timestamp: new Date().toISOString(),
    amount: "",
    currency: "INR",
    payer_id: "",
    payee_id: "",
    metadata: ""
  });

  const generateIdempotencyKey = () => {
    const key = `idem_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setFormData(prev => ({ ...prev, idempotency_key: key }));
  };

  const generateTransactionId = () => {
    const id = `txn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setFormData(prev => ({ ...prev, transaction_id: id }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResponse(null);

    try {
      const payload = {
        idempotency_key: formData.idempotency_key,
        transaction_id: formData.transaction_id,
        timestamp: formData.timestamp,
        amount: parseInt(formData.amount, 10),
        currency: formData.currency.toUpperCase(),
        payer_id: formData.payer_id,
        payee_id: formData.payee_id,
      };

      if (formData.metadata.trim()) {
        try {
          payload.metadata = JSON.parse(formData.metadata);
        } catch {
          toast.error("Invalid JSON in metadata field");
          setLoading(false);
          return;
        }
      }

      setRequest(payload);

      const res = await axios.post(`${apiUrl}/fea/generate`, payload, {
        headers: {
          "X-API-Key": apiKey,
          "Content-Type": "application/json"
        }
      });

      setResponse({ status: res.status, data: res.data });
      toast.success("FEA generated successfully");
    } catch (error) {
      const errData = error.response?.data || { detail: error.message };
      setResponse({ 
        status: error.response?.status || 500, 
        data: errData,
        error: true 
      });
      toast.error(errData.detail || "Failed to generate FEA");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="generate-fea-panel">
      {/* Form Panel */}
      <div className="bg-[#09090b] border border-zinc-800 rounded-sm">
        <div className="border-b border-zinc-800 p-4 bg-zinc-900/50">
          <h2 className="text-sm font-semibold text-white font-['Space_Grotesk'] uppercase tracking-wider">
            Generate FEA
          </h2>
          <p className="text-xs text-zinc-500 mt-1">POST /api/fea/generate</p>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
              Idempotency Key *
            </Label>
            <div className="flex gap-2">
              <Input
                value={formData.idempotency_key}
                onChange={(e) => setFormData(prev => ({ ...prev, idempotency_key: e.target.value }))}
                placeholder="idem_unique_key"
                className="bg-black border-zinc-800 text-white font-mono text-sm"
                required
                data-testid="input-idempotency-key"
              />
              <Button 
                type="button" 
                variant="outline" 
                size="icon"
                onClick={generateIdempotencyKey}
                className="border-zinc-700 hover:bg-zinc-800"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
              Transaction ID *
            </Label>
            <div className="flex gap-2">
              <Input
                value={formData.transaction_id}
                onChange={(e) => setFormData(prev => ({ ...prev, transaction_id: e.target.value }))}
                placeholder="txn_12345"
                className="bg-black border-zinc-800 text-white font-mono text-sm"
                required
                data-testid="input-transaction-id"
              />
              <Button 
                type="button" 
                variant="outline" 
                size="icon"
                onClick={generateTransactionId}
                className="border-zinc-700 hover:bg-zinc-800"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
              Timestamp (ISO 8601) *
            </Label>
            <Input
              value={formData.timestamp}
              onChange={(e) => setFormData(prev => ({ ...prev, timestamp: e.target.value }))}
              placeholder="2024-01-15T10:30:00Z"
              className="bg-black border-zinc-800 text-white font-mono text-sm"
              required
              data-testid="input-timestamp"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
                Amount (smallest unit) *
              </Label>
              <Input
                type="number"
                value={formData.amount}
                onChange={(e) => setFormData(prev => ({ ...prev, amount: e.target.value }))}
                placeholder="10000"
                className="bg-black border-zinc-800 text-white font-mono text-sm"
                required
                data-testid="input-amount"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
                Currency *
              </Label>
              <Input
                value={formData.currency}
                onChange={(e) => setFormData(prev => ({ ...prev, currency: e.target.value.toUpperCase() }))}
                placeholder="INR"
                maxLength={3}
                className="bg-black border-zinc-800 text-white font-mono text-sm"
                required
                data-testid="input-currency"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
              Payer ID (hashed/tokenized) *
            </Label>
            <Input
              value={formData.payer_id}
              onChange={(e) => setFormData(prev => ({ ...prev, payer_id: e.target.value }))}
              placeholder="payer_hash_abc123"
              className="bg-black border-zinc-800 text-white font-mono text-sm"
              required
              data-testid="input-payer-id"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
              Payee ID (hashed/tokenized) *
            </Label>
            <Input
              value={formData.payee_id}
              onChange={(e) => setFormData(prev => ({ ...prev, payee_id: e.target.value }))}
              placeholder="payee_hash_xyz789"
              className="bg-black border-zinc-800 text-white font-mono text-sm"
              required
              data-testid="input-payee-id"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
              Metadata (optional JSON)
            </Label>
            <Textarea
              value={formData.metadata}
              onChange={(e) => setFormData(prev => ({ ...prev, metadata: e.target.value }))}
              placeholder='{"ref": "INV-001", "note": "Payment for services"}'
              className="bg-black border-zinc-800 text-white font-mono text-sm min-h-[80px]"
              data-testid="input-metadata"
            />
          </div>

          <Button 
            type="submit" 
            disabled={loading}
            className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm font-medium uppercase tracking-wider"
            data-testid="btn-generate-fea"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Send className="w-4 h-4 mr-2" />
                Generate FEA
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
              Response
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
              data-testid="btn-copy-response"
            >
              <Copy className="w-4 h-4 mr-1" />
              Copy
            </Button>
          )}
        </div>
        
        <div className="p-4 space-y-4">
          {request && (
            <div>
              <p className="text-xs text-zinc-500 mb-2 font-mono uppercase">Request Payload</p>
              <JsonViewer data={request} />
            </div>
          )}
          
          {response ? (
            <div>
              <p className="text-xs text-zinc-500 mb-2 font-mono uppercase">Response</p>
              <JsonViewer data={response.data} />
            </div>
          ) : (
            <div className="text-center py-12 text-zinc-600">
              <p className="font-mono text-sm">No response yet</p>
              <p className="text-xs mt-1">Submit the form to generate an FEA</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
