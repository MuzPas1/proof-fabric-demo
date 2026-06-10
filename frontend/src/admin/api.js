// PFP Admin Dashboard — API client. Uses ONLY existing verified endpoints.
import axios from "axios";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TOKEN_KEY = "pfp_admin_token";
const USER_KEY = "pfp_admin_user";
const TENANT_KEYS = "pfp_tenant_keys"; // sessionStorage: { [tenant_id]: rawApiKey }

export const auth = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  getUser: () => {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
  },
  set: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(TENANT_KEYS);
  },
};

// Session-scoped tenant API keys (data-plane "act as tenant")
export const tenantKeys = {
  all: () => { try { return JSON.parse(sessionStorage.getItem(TENANT_KEYS)) || {}; } catch { return {}; } },
  get: (tid) => tenantKeys.all()[tid] || null,
  set: (tid, raw) => {
    const m = tenantKeys.all(); m[tid] = raw;
    sessionStorage.setItem(TENANT_KEYS, JSON.stringify(m));
  },
};

const cp = axios.create({ baseURL: BASE }); // control plane (JWT)
cp.interceptors.request.use((config) => {
  const t = auth.getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});
cp.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response && e.response.status === 401 && !e.config.url.includes("/auth/login")) {
      auth.clear();
      if (!window.location.pathname.endsWith("/admin/login")) window.location.href = "/admin/login";
    }
    return Promise.reject(e);
  }
);

// Data-plane call with a tenant API key
const dp = (apiKey) => axios.create({ baseURL: BASE, headers: { "X-API-Key": apiKey } });

export const api = {
  // --- Auth ---
  login: (email, password) => cp.post("/auth/login", { email, password }).then((r) => r.data),
  me: () => cp.get("/auth/me").then((r) => r.data),

  // --- Tenants ---
  listTenants: () => cp.get("/admin/tenants").then((r) => r.data),
  createTenant: (name) => cp.post("/admin/tenants", { name }).then((r) => r.data),

  // --- API keys ---
  listApiKeys: () => cp.get("/admin/api-keys").then((r) => r.data),
  createApiKey: (body) => cp.post("/admin/api-keys/create", body).then((r) => r.data),
  revokeApiKey: (keyId) => cp.post(`/admin/api-keys/revoke?key_id=${encodeURIComponent(keyId)}`).then((r) => r.data),

  // --- Signing keys ---
  listSigningKeys: () => cp.get("/public/keys").then((r) => r.data),
  rotateKey: () => cp.post("/admin/keys/rotate").then((r) => r.data),
  revokeKey: (kid) => cp.post(`/admin/keys/revoke?public_key_id=${encodeURIComponent(kid)}`).then((r) => r.data),
  retireKey: (kid) => cp.post(`/admin/keys/retire?public_key_id=${encodeURIComponent(kid)}`).then((r) => r.data),

  // --- Audit ---
  audit: (params = {}) => cp.get("/admin/audit", { params }).then((r) => r.data),
  auditVerify: () => cp.get("/admin/audit/verify").then((r) => r.data),

  // --- System ---
  health: () => cp.get("/health").then((r) => r.data),
  metricsRaw: () => cp.get("/metrics", { responseType: "text" }).then((r) => r.data),
  config: () => cp.get("/config").then((r) => r.data),

  // --- Data plane (tenant API key) ---
  listFeas: (apiKey, limit = 25, skip = 0) =>
    dp(apiKey).get(`/fea?limit=${limit}&skip=${skip}`).then((r) => r.data),
  getFea: (apiKey, id) => dp(apiKey).get(`/fea/${id}`).then((r) => r.data),
  listWebhooks: (apiKey) => dp(apiKey).get("/webhooks").then((r) => r.data),
  subscribeWebhook: (apiKey, url, events) =>
    dp(apiKey).post("/webhooks/subscribe", { url, events }).then((r) => r.data),
  testWebhook: (apiKey, id) =>
    dp(apiKey).post(`/webhooks/test?webhook_id=${encodeURIComponent(id)}`).then((r) => r.data),
  deleteWebhook: (apiKey, id) => dp(apiKey).delete(`/webhooks/${id}`).then((r) => r.data),
};

// Parse Prometheus exposition text -> sum of a metric family
export function sumMetric(text, name) {
  let total = 0;
  for (const line of String(text).split("\n")) {
    if (line.startsWith(name) && !line.startsWith("#")) {
      const v = parseFloat(line.trim().split(/\s+/).pop());
      if (!Number.isNaN(v)) total += v;
    }
  }
  return total;
}
