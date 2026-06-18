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

// Curve group orders (for low-S enforcement).
const N_R1 = BigInt('0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551');
const N_K1 = BigInt('0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141');

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

function ecdsaVerify(alg, message, signatureB64, publicKeyB64) {
  try {
    const raw = Buffer.from(publicKeyB64, 'base64');
    if (raw.length !== 65 || raw[0] !== 0x04) return false;
    const crv = alg === 'ES256' ? 'P-256' : 'secp256k1';
    const order = alg === 'ES256' ? N_R1 : N_K1;
    const key = crypto.createPublicKey({
      key: {
        kty: 'EC',
        crv,
        x: raw.subarray(1, 33).toString('base64url'),
        y: raw.subarray(33, 65).toString('base64url'),
      },
      format: 'jwk',
    });
    const sig = Buffer.from(signatureB64, 'base64');
    if (sig.length !== 64) return false;
    // Anti-malleability: reject high-S.
    const s = BigInt('0x' + sig.subarray(32, 64).toString('hex'));
    const r = BigInt('0x' + sig.subarray(0, 32).toString('hex'));
    if (r === 0n || s === 0n || r >= order || s >= order || s > order / 2n) return false;
    return crypto.verify('sha256', Buffer.from(message, 'utf-8'),
      { key, dsaEncoding: 'ieee-p1363' }, sig);
  } catch (e) {
    return false;
  }
}

/** Suite-aware verification (Ed25519 | ES256 | ES256K). */
function verifySuite(algorithm, message, signatureB64, publicKeyB64) {
  const alg = algorithm || 'Ed25519';
  if (alg === 'Ed25519' || alg === 'EdDSA') return ed25519Verify(message, signatureB64, publicKeyB64);
  if (alg === 'ES256' || alg === 'ES256K') return ecdsaVerify(alg, message, signatureB64, publicKeyB64);
  return false;
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

  /** Independent FEA verification — no server round-trip. Suite-aware. */
  static verifyLocal(feaPayload, signatureB64, publicKeyB64, algorithm = null) {
    const claimed = feaPayload.fea_hash;
    if (!claimed) return { valid: false, reason: 'Missing fea_hash' };
    const without = { ...feaPayload };
    delete without.fea_hash;
    if (sha256Hex(canonicalizeToJson(without)) !== claimed) {
      return { valid: false, reason: 'Hash mismatch: payload tampered' };
    }
    const alg = algorithm || feaPayload.algorithm || 'Ed25519';
    const message = DOMAIN_PREFIX_V2 + canonicalizeToJson(feaPayload);
    return verifySuite(alg, message, signatureB64, publicKeyB64)
      ? { valid: true, reason: null }
      : { valid: false, reason: 'Invalid signature' };
  }

  /** Independent artifact verification. Suite-aware. */
  static verifyArtifactLocal(artifact, publicKeyB64, algorithm = null) {
    const { signature, proof_id } = artifact;
    if (!signature || !proof_id) return { valid: false, reason: 'Missing signature/proof_id' };
    const base = { ...artifact }; delete base.signature;
    const baseForId = { ...base }; delete baseForId.proof_id;
    if (sha256Hex(canonicalizeToJson(baseForId)) !== proof_id) {
      return { valid: false, reason: 'proof_id mismatch' };
    }
    const alg = algorithm || artifact.algorithm || 'Ed25519';
    const message = ARTIFACT_DOMAIN_PREFIX + canonicalizeToJson(base);
    return verifySuite(alg, message, signature, publicKeyB64)
      ? { valid: true, reason: null }
      : { valid: false, reason: 'Invalid signature' };
  }
}

module.exports = { PFPClient, canonicalizeToJson };
