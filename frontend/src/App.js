import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import { Toaster, toast } from "sonner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GenerateFEA } from "@/components/GenerateFEA";
import { VerifyFEA } from "@/components/VerifyFEA";
import { PublicVerify } from "@/components/PublicVerify";
import { Shield, Key, CheckCircle2 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchConfig = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/config`);
      setConfig(response.data);
    } catch (e) {
      console.error("Failed to fetch config:", e);
      toast.error("Failed to connect to API");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-zinc-500 font-mono text-sm">Initializing PFP Console...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] scanlines" data-testid="pfp-console">
      <Toaster 
        theme="dark" 
        position="top-right"
        toastOptions={{
          style: {
            background: '#09090b',
            border: '1px solid #27272a',
            color: '#fafafa',
          },
        }}
      />
      
      {/* Header */}
      <header className="border-b border-zinc-800 bg-[#09090b]">
        <div className="max-w-6xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 bg-green-500/10 border border-green-500/30 rounded flex items-center justify-center">
                <Shield className="w-5 h-5 text-green-500" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight font-['Space_Grotesk']" data-testid="app-title">
                  Proof Fabric Protocol
                </h1>
                <p className="text-xs text-zinc-500 font-mono mt-0.5">
                  Developer Test Console v1.0
                </p>
              </div>
            </div>
            
            {config?.test_api_key && (
              <div className="flex items-center gap-3 bg-zinc-900/50 border border-zinc-800 rounded px-3 py-2">
                <Key className="w-4 h-4 text-zinc-500" />
                <div className="flex flex-col">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Test API Key</span>
                  <code className="text-xs text-green-400 font-mono" data-testid="api-key-display">
                    {config.test_api_key.slice(0, 20)}...
                  </code>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Tabs defaultValue="generate" className="space-y-6">
          <TabsList className="bg-zinc-900/50 p-1 border border-zinc-800 rounded-md inline-flex">
            <TabsTrigger 
              value="generate" 
              className="data-[state=active]:bg-zinc-800 data-[state=active]:text-white text-zinc-400 px-4 py-2 rounded-sm text-sm font-medium"
              data-testid="tab-generate"
            >
              Generate FEA
            </TabsTrigger>
            <TabsTrigger 
              value="verify" 
              className="data-[state=active]:bg-zinc-800 data-[state=active]:text-white text-zinc-400 px-4 py-2 rounded-sm text-sm font-medium"
              data-testid="tab-verify"
            >
              Verify FEA
            </TabsTrigger>
            <TabsTrigger 
              value="public" 
              className="data-[state=active]:bg-zinc-800 data-[state=active]:text-white text-zinc-400 px-4 py-2 rounded-sm text-sm font-medium"
              data-testid="tab-public"
            >
              Public Verify
            </TabsTrigger>
          </TabsList>

          <TabsContent value="generate" className="mt-6">
            <GenerateFEA apiKey={config?.test_api_key} apiUrl={API} />
          </TabsContent>

          <TabsContent value="verify" className="mt-6">
            <VerifyFEA apiKey={config?.test_api_key} apiUrl={API} />
          </TabsContent>

          <TabsContent value="public" className="mt-6">
            <PublicVerify apiUrl={API} />
          </TabsContent>
        </Tabs>

        {/* Footer Info */}
        <div className="mt-12 pt-6 border-t border-zinc-800/50">
          <div className="flex items-center gap-6 text-xs text-zinc-600">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3" />
              <span>Ed25519 Signatures</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3" />
              <span>SHA-256 Hashing</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3" />
              <span>Deterministic Canonicalization</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
