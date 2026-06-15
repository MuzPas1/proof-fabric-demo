import React, { createContext, useCallback, useContext, useState } from "react";
import { API } from "./data";

const SandboxContext = createContext(null);

export const useSandbox = () => {
  const ctx = useContext(SandboxContext);
  if (!ctx) throw new Error("useSandbox must be used within SandboxProvider");
  return ctx;
};

export const SandboxProvider = ({ children }) => {
  const [keyData, setKeyData] = useState(null); // { api_key, scopes, expires_at, ... }
  const [generating, setGenerating] = useState(false);
  const [keyError, setKeyError] = useState(null);

  // Last generated proof shared between FirstProof -> VerifyProof.
  const [lastProofId, setLastProofId] = useState("");

  const apiKey = keyData?.api_key || "";

  const generateKey = useCallback(async () => {
    setGenerating(true);
    setKeyError(null);
    try {
      const res = await fetch(`${API}/demo/sandbox-key`, { method: "POST" });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const data = await res.json();
      setKeyData(data);
      return data;
    } catch (e) {
      setKeyError(e.message || "Failed to generate sandbox key");
      return null;
    } finally {
      setGenerating(false);
    }
  }, []);

  return (
    <SandboxContext.Provider
      value={{
        keyData,
        apiKey,
        generating,
        keyError,
        generateKey,
        lastProofId,
        setLastProofId,
      }}
    >
      {children}
    </SandboxContext.Provider>
  );
};
