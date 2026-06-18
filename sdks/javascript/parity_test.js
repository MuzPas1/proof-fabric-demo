'use strict';
// JS SDK parity check against shipped test vectors (Ed25519 / ES256 / ES256K).
const fs = require('fs');
const path = require('path');
const { PFPClient } = require('./index');

const vectors = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'test_vectors.json'), 'utf-8'));
let pass = 0, fail = 0;

for (const v of vectors.fea) {
  const res = PFPClient.verifyLocal(v.fea_payload, v.signature, v.public_key_b64);
  const ok = res.valid === v.expected_valid;
  console.log(`[JS] ${v.suite}: valid=${res.valid} expected=${v.expected_valid} ${ok ? 'PASS' : 'FAIL ' + (res.reason || '')}`);
  ok ? pass++ : fail++;

  // Negative: tamper the amount -> must fail.
  const tampered = JSON.parse(JSON.stringify(v.fea_payload));
  if (tampered.transaction_summary) tampered.transaction_summary.amount = 999999999;
  const neg = PFPClient.verifyLocal(tampered, v.signature, v.public_key_b64);
  const negOk = neg.valid === false;
  console.log(`[JS] ${v.suite} tamper: valid=${neg.valid} ${negOk ? 'PASS' : 'FAIL'}`);
  negOk ? pass++ : fail++;
}

console.log(`\n[JS] parity: ${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
