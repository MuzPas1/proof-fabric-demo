// Shareable verification-link helpers.
// Encodes a signed proof artifact into a URL-safe string so an auditor can
// verify it by clicking a single link.

const MAX_URL_PROOF_LENGTH = 2000; // conservative — keep well under 2–4KB URL limits

function toBase64Url(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) {
    bin += String.fromCharCode(bytes[i]);
  }
  return btoa(bin)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function fromBase64Url(b64url) {
  let b64 = String(b64url).replace(/-/g, "+").replace(/_/g, "/");
  const pad = b64.length % 4;
  if (pad) b64 += "=".repeat(4 - pad);
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

export { MAX_URL_PROOF_LENGTH };

export function encodeProofToLinkParam(jsonString) {
  return toBase64Url(jsonString);
}

export function decodeProofFromLinkParam(b64url) {
  const jsonStr = fromBase64Url(b64url);
  // Validate it is actually JSON; caller may still choose to re-parse.
  JSON.parse(jsonStr);
  return jsonStr;
}

export function buildVerifyUrl(jsonString, originOverride) {
  const origin =
    originOverride ||
    (typeof window !== "undefined" ? window.location.origin : "");
  const param = encodeProofToLinkParam(jsonString);
  const url = `${origin}/verify?proof=${param}`;
  return { url, param, tooLong: url.length > MAX_URL_PROOF_LENGTH };
}
