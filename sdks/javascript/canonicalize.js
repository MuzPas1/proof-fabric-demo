'use strict';
/**
 * PFP canonicalization — faithful port of backend/crypto/canonicalize.py.
 * Deterministic JSON: sorted keys, null-strip at all depths, float->int when
 * whole, ISO timestamp normalization to millisecond UTC, minimal separators.
 */
const TS_RE = /^\d{4}-\d{2}-\d{2}T/;

function normalizeTimestamp(ts) {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toISOString(); // YYYY-MM-DDTHH:MM:SS.mmmZ
}

function normalizeValue(value) {
  if (value === null || value === undefined) return undefined;
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value : value;
  }
  if (typeof value === 'string') {
    return TS_RE.test(value) ? normalizeTimestamp(value) : value;
  }
  if (Array.isArray(value)) {
    return value.filter((v) => v !== null && v !== undefined).map(normalizeValue);
  }
  if (typeof value === 'object') return canonicalizeObject(value);
  return value;
}

function canonicalizeObject(obj) {
  const out = {};
  for (const key of Object.keys(obj).sort()) {
    const v = obj[key];
    if (v === null || v === undefined) continue;
    const nv = normalizeValue(v);
    if (nv !== undefined) out[key] = nv;
  }
  return out;
}

/** Serialize an already-canonical object with sorted keys + no whitespace. */
function stableStringify(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return '[' + value.map(stableStringify).join(',') + ']';
  if (typeof value === 'object') {
    const parts = Object.keys(value)
      .sort()
      .map((k) => JSON.stringify(k) + ':' + stableStringify(value[k]));
    return '{' + parts.join(',') + '}';
  }
  return JSON.stringify(value);
}

function canonicalizeToJson(data) {
  return stableStringify(canonicalizeObject(data));
}

module.exports = { canonicalizeToJson, normalizeTimestamp };
