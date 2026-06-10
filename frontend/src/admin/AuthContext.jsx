import React, { createContext, useContext, useEffect, useState } from "react";
import { api, auth } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(auth.getUser());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    if (auth.getToken()) {
      api.me()
        .then((u) => active && setUser(u))
        .catch(() => active && setUser(null))
        .finally(() => active && setLoading(false));
    } else {
      setLoading(false);
    }
    return () => { active = false; };
  }, []);

  const login = async (email, password) => {
    const data = await api.login(email, password);
    const u = { email: data.email, role: data.role, tenant_id: data.tenant_id };
    auth.set(data.access_token, u);
    setUser(u);
    return u;
  };

  const logout = () => {
    auth.clear();
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
