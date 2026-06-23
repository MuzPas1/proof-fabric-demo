// Enterprise-tier access for the Documentation Portal.
// Approved evaluators (and staff) sign in here; the token gates ENTERPRISE docs,
// SDK source, Postman and the full OpenAPI spec (server-side enforced).
const BACKEND = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND}/api`;
const TOKEN_KEY = "pfp_docs_token";
const USER_KEY = "pfp_docs_user";

export const getDocsToken = () => {
  // Prefer a docs/eval token; fall back to an admin session if present.
  return localStorage.getItem(TOKEN_KEY) || localStorage.getItem("pfp_admin_token");
};

export const getDocsUser = () => {
  try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
};

export const setDocsAuth = (token, user) => {
  localStorage.setItem(TOKEN_KEY, token);
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
};

export const clearDocsAuth = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

export async function docsLogin(email, password) {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const msg = await res.json().catch(() => ({}));
    throw new Error(msg.detail || "Invalid credentials");
  }
  const data = await res.json();
  setDocsAuth(data.access_token, { email: data.email, role: data.role });
  return data;
}

export async function submitEvaluationRequest(payload) {
  const res = await fetch(`${API}/evaluation/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed. Please try again.");
  return data;
}

// Open an ENTERPRISE asset (SDK file / full OpenAPI / Postman). The bearer token
// cannot ride a normal new-tab navigation, so we fetch + open a blob instead.
export async function openEnterpriseAsset(href, navigate) {
  const token = getDocsToken();
  if (!token) { navigate("/evaluation"); return; }
  try {
    const res = await fetch(href, { headers: { Authorization: `Bearer ${token}` } });
    if (res.status === 401 || res.status === 403) { navigate("/evaluation"); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch {
    navigate("/evaluation");
  }
}
