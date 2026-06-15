/**
 * Generic Workflow Builder — configuration helpers.
 *
 * Browser-only persistence (LocalStorage) + URL-encoded sharing. NO backend,
 * NO database, NO schema changes. The builder feeds custom workflow data into
 * the existing proof architecture (see TransactionFlow.jsx); these helpers only
 * manage the editable configuration and its (de)serialization.
 */

export const STORAGE_KEY = "pfp_generic_workflow_v1";

/**
 * Starter template — loaded automatically so the screen is never empty.
 */
export const STARTER_TEMPLATE = {
  workflowName: "Release",
  fields: [
    { label: "Release ID", value: "REL-2026-001" },
    { label: "Environment", value: "Production" },
    { label: "CAB Reference", value: "CAB-APPROVED-2026" },
  ],
  checks: [
    { name: "Test Execution" },
    { name: "UAT Completion" },
    { name: "CAB Approval" },
  ],
  simulateFailure: false,
};

/** Deep clone the starter template (so callers cannot mutate the constant). */
export const cloneStarter = () => JSON.parse(JSON.stringify(STARTER_TEMPLATE));

/** Coerce any parsed object into a safe, fully-shaped config. */
export function sanitizeConfig(c) {
  if (!c || typeof c !== "object") return null;
  const fields = Array.isArray(c.fields)
    ? c.fields.map((f) => ({
        label: String(f?.label ?? ""),
        value: String(f?.value ?? ""),
      }))
    : [];
  const checks = Array.isArray(c.checks)
    ? c.checks.map((ch) => ({ name: String(ch?.name ?? "") }))
    : [];
  return {
    workflowName: String(c.workflowName ?? ""),
    fields,
    checks,
    simulateFailure: Boolean(c.simulateFailure),
  };
}

/* ----------------------------- LocalStorage ------------------------------ */

export function saveTemplate(config) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    return true;
  } catch {
    return false;
  }
}

export function loadTemplate() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return sanitizeConfig(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function clearTemplate() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/* ------------------------- URL-encoded sharing --------------------------- */

function b64EncodeUnicode(str) {
  const bytes = new TextEncoder().encode(str);
  let binary = "";
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary);
}

function b64DecodeUnicode(b64) {
  const binary = atob(b64);
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function encodeConfig(config) {
  try {
    return encodeURIComponent(b64EncodeUnicode(JSON.stringify(config)));
  } catch {
    return null;
  }
}

export function decodeConfig(str) {
  try {
    return sanitizeConfig(JSON.parse(b64DecodeUnicode(decodeURIComponent(str))));
  } catch {
    return null;
  }
}

/* ------------------------------ Validation ------------------------------- */

/**
 * A field is empty when its label OR value is blank. Empty / deleted fields
 * are excluded from the canonical payload. Returns the list of fields/checks
 * that will actually be embedded, plus any blocking validation errors.
 */
export function validateConfig(c) {
  const safe = sanitizeConfig(c) || { workflowName: "", fields: [], checks: [] };
  const validFields = safe.fields.filter(
    (f) => f.label.trim() && f.value.trim()
  );
  const validChecks = safe.checks.filter((ch) => ch.name.trim());

  const errors = [];
  if (!safe.workflowName.trim()) errors.push("Workflow Name is required.");
  if (validFields.length === 0)
    errors.push("Add at least one field with both a label and a value.");
  if (validChecks.length === 0)
    errors.push("Add at least one workflow check.");

  return { valid: errors.length === 0, errors, validFields, validChecks };
}
