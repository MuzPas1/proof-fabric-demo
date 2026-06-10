'use strict';
/**
 * PFP JavaScript SDK (Node.js, zero external dependencies).
 *
 *   const { PFPClient } = require('@pfp/sdk');
 *   const pfp = new PFPClient('https://api.pfprotocol.com', 'pfp_live_...');
 *   const fea = await pfp.generateFea({ idempotency_key, transaction_id, ... });
 *   const { keys } = await pfp.publicKeys();
 *   const pub = keys.find(k => k.public_key_id === fea.public_key_id).public_key;
 *   console.log(PFPClient.verifyLocal(fea.fea_payload, fea.signature, pub));
 */
const crypto = require('crypto');
const { canonicalizeToJson } = require('./canonicalize');

const DOMAIN_PREFIX_V2 = 'PFP_V2::';
const ARTIFACT_DOMAIN_PREFIX = 'PFP_ARTIFACT_V1::';
const ED25519_SPKI_PREFIX = Buffer.from('302a300506032b6570032100', 'hex');

function rawEd25519PublicKey(b64) {
  const raw = Buffer.from(b64, 'base64');
  return crypto.createPublicKey({
    key: Buffer.concat([ED25519_SPKI_PREFIX, raw]),
    format: 'der',
    type: 'spki',
  });
}

function sha256Hex(str) {
  return crypto.createHash('sha256').update(Buffer.from(str, 'utf-8')).digest('hex');
}

function ed25519Verify(message, signatureB64, publicKeyB64) {
  try {
    return crypto.verify(
      null,
      Buffer.from(message, 'utf-8'),
      rawEd25519PublicKey(publicKeyB64),
      Buffer.from(signatureB64, 'base64')
    );
  } catch (e) {
    return false;
  }
}

class PFPClient {
  constructor(baseUrl, apiKey = null, timeout = 15000) {
    this.base = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
    this.timeout = timeout;
  }

  async _req(method, path, body, auth = true) {
    const headers = { 'Content-Type': 'application/json' };
    if (auth && this.apiKey) headers['X-API-Key'] = this.apiKey;
    const resp = await fetch(`${this.base}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await resp.text();
    if (!resp.ok) throw new Error(`${resp.status}: ${text}`);
    return text ? JSON.parse(text) : {};
  }

  generateFea(payload) { return this._req('POST', '/api/fea/generate', payload); }
  batchGenerate(items) { return this._req('POST', '/api/fea/batch', { items }); }
  verifyFea(fea_payload, signature, signature_version = null) {
    return this._req('POST', '/api/fea/verify', { fea_payload, signature, signature_version });
  }
  listFeas(limit = 50, skip = 0) { return this._req('GET', `/api/fea?limit=${limit}&skip=${skip}`); }
  getFea(id) { return this._req('GET', `/api/fea/${id}`); }
  publicVerify(id) { return this._req('GET', `/api/public/verify/${id}`, null, false); }
  publicKeys() { return this._req('GET', '/api/public/keys', null, false); }
  subscribeWebhook(url, events = ['fea.generated']) {
    return this._req('POST', '/api/webhooks/subscribe', { url, events });
  }

  /** Independent FEA verification — no server round-trip. */
  static verifyLocal(feaPayload, signatureB64, publicKeyB64) {
    const claimed = feaPayload.fea_hash;
    if (!claimed) return { valid: false, reason: 'Missing fea_hash' };
    const without = { ...feaPayload };
    delete without.fea_hash;
    if (sha256Hex(canonicalizeToJson(without)) !== claimed) {
      return { valid: false, reason: 'Hash mismatch: payload tampered' };
    }
    const message = DOMAIN_PREFIX_V2 + canonicalizeToJson(feaPayload);
    return ed25519Verify(message, signatureB64, publicKeyB64)
      ? { valid: true, reason: null }
      : { valid: false, reason: 'Invalid signature' };
  }

  /** Independent artifact verification. */
  static verifyArtifactLocal(artifact, publicKeyB64) {
    const { signature, proof_id } = artifact;
    if (!signature || !proof_id) return { valid: false, reason: 'Missing signature/proof_id' };
    const base = { ...artifact }; delete base.signature;
    const baseForId = { ...base }; delete baseForId.proof_id;
    if (sha256Hex(canonicalizeToJson(baseForId)) !== proof_id) {
      return { valid: false, reason: 'proof_id mismatch' };
    }
    const message = ARTIFACT_DOMAIN_PREFIX + canonicalizeToJson(base);
    return ed25519Verify(message, signature, publicKeyB64)
      ? { valid: true, reason: null }
      : { valid: false, reason: 'Invalid signature' };
  }
}

module.exports = { PFPClient, canonicalizeToJson };
