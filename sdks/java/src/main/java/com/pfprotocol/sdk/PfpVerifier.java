package com.pfprotocol.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigInteger;
import java.security.AlgorithmParameters;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.ECParameterSpec;
import java.security.spec.ECPoint;
import java.security.spec.ECPublicKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Arrays;
import java.util.Base64;
import java.util.HexFormat;

/**
 * Independent PFP FEA / artifact verification for Java (JDK 17+).
 *
 * Crypto-agile: the signature suite is read from the payload's {@code algorithm}
 * field (Ed25519 default; ES256 = secp256r1; ES256K = secp256k1). ECDSA
 * signatures are raw r||s (64 bytes) with enforced low-S (anti-malleability).
 *
 * No PFP server round-trip required — verify with just the issuer's public key
 * (base64, from GET /api/public/keys). Dependency: jackson-databind (JSON only).
 */
public final class PfpVerifier {

    private static final String DOMAIN_PREFIX_V2 = "PFP_V2::";
    private static final String ARTIFACT_DOMAIN_PREFIX = "PFP_ARTIFACT_V1::";
    private static final byte[] ED25519_SPKI_PREFIX =
            HexFormat.of().parseHex("302a300506032b6570032100");

    private static final BigInteger N_R1 =
            new BigInteger("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16);
    private static final BigInteger N_K1 =
            new BigInteger("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16);

    private static final ObjectMapper MAPPER = new ObjectMapper();

    public record Result(boolean valid, String reason) {}

    private PfpVerifier() {}

    public static Result verifyFea(String feaPayloadJson, String signatureB64, String publicKeyB64)
            throws Exception {
        JsonNode payload = MAPPER.readTree(feaPayloadJson);
        if (!payload.has("fea_hash")) return new Result(false, "Missing fea_hash");
        String claimed = payload.get("fea_hash").asText();

        ObjectNode withoutHash = payload.deepCopy();
        withoutHash.remove("fea_hash");
        String computed = sha256Hex(PfpCanonicalizer.canonicalize(withoutHash));
        if (!constantTimeEquals(computed, claimed)) {
            return new Result(false, "Hash mismatch: payload tampered");
        }

        String alg = payload.has("algorithm") ? payload.get("algorithm").asText() : "Ed25519";
        String message = DOMAIN_PREFIX_V2 + PfpCanonicalizer.canonicalize(payload);
        boolean ok = verifySuite(alg, message.getBytes("UTF-8"), signatureB64, publicKeyB64);
        return ok ? new Result(true, null) : new Result(false, "Invalid signature");
    }

    public static Result verifyArtifact(String artifactJson, String publicKeyB64) throws Exception {
        JsonNode artifact = MAPPER.readTree(artifactJson);
        if (!artifact.has("signature") || !artifact.has("proof_id")) {
            return new Result(false, "Missing signature/proof_id");
        }
        ObjectNode base = artifact.deepCopy();
        base.remove("signature");
        ObjectNode baseForId = base.deepCopy();
        baseForId.remove("proof_id");
        String expected = sha256Hex(PfpCanonicalizer.canonicalize(baseForId));
        if (!constantTimeEquals(expected, artifact.get("proof_id").asText())) {
            return new Result(false, "proof_id mismatch");
        }
        String alg = artifact.has("algorithm") ? artifact.get("algorithm").asText() : "Ed25519";
        String message = ARTIFACT_DOMAIN_PREFIX + PfpCanonicalizer.canonicalize(base);
        boolean ok = verifySuite(alg, message.getBytes("UTF-8"),
                artifact.get("signature").asText(), publicKeyB64);
        return ok ? new Result(true, null) : new Result(false, "Invalid signature");
    }

    private static boolean verifySuite(String alg, byte[] message, String signatureB64, String publicKeyB64) {
        if (alg == null || alg.equals("Ed25519") || alg.equals("EdDSA")) {
            return ed25519Verify(message, signatureB64, publicKeyB64);
        }
        if (alg.equals("ES256") || alg.equals("ES256K")) {
            return ecdsaVerify(alg, message, signatureB64, publicKeyB64);
        }
        return false;
    }

    private static boolean ed25519Verify(byte[] message, String signatureB64, String publicKeyB64) {
        try {
            byte[] raw = Base64.getDecoder().decode(publicKeyB64);
            byte[] spki = new byte[ED25519_SPKI_PREFIX.length + raw.length];
            System.arraycopy(ED25519_SPKI_PREFIX, 0, spki, 0, ED25519_SPKI_PREFIX.length);
            System.arraycopy(raw, 0, spki, ED25519_SPKI_PREFIX.length, raw.length);
            PublicKey key = KeyFactory.getInstance("Ed25519")
                    .generatePublic(new X509EncodedKeySpec(spki));
            Signature sig = Signature.getInstance("Ed25519");
            sig.initVerify(key);
            sig.update(message);
            return sig.verify(Base64.getDecoder().decode(signatureB64));
        } catch (Exception e) {
            return false;
        }
    }

    private static boolean ecdsaVerify(String alg, byte[] message, String signatureB64, String publicKeyB64) {
        try {
            byte[] raw = Base64.getDecoder().decode(publicKeyB64);
            if (raw.length != 65 || raw[0] != 0x04) return false;
            byte[] sig = Base64.getDecoder().decode(signatureB64);
            if (sig.length != 64) return false;

            String curveName = alg.equals("ES256") ? "secp256r1" : "secp256k1";
            BigInteger order = alg.equals("ES256") ? N_R1 : N_K1;
            BigInteger r = new BigInteger(1, Arrays.copyOfRange(sig, 0, 32));
            BigInteger s = new BigInteger(1, Arrays.copyOfRange(sig, 32, 64));
            // Anti-malleability: reject high-S / out-of-range.
            if (r.signum() == 0 || s.signum() == 0
                    || r.compareTo(order) >= 0 || s.compareTo(order) >= 0
                    || s.compareTo(order.shiftRight(1)) > 0) {
                return false;
            }

            AlgorithmParameters params = AlgorithmParameters.getInstance("EC");
            params.init(new ECGenParameterSpec(curveName));
            ECParameterSpec ecSpec = params.getParameterSpec(ECParameterSpec.class);
            ECPoint point = new ECPoint(
                    new BigInteger(1, Arrays.copyOfRange(raw, 1, 33)),
                    new BigInteger(1, Arrays.copyOfRange(raw, 33, 65)));
            PublicKey key = KeyFactory.getInstance("EC")
                    .generatePublic(new ECPublicKeySpec(point, ecSpec));

            Signature verifier = Signature.getInstance("SHA256withECDSA");
            verifier.initVerify(key);
            verifier.update(message);
            return verifier.verify(rawToDer(r, s));
        } catch (Exception e) {
            return false;
        }
    }

    /** Convert raw (r,s) to a DER-encoded ECDSA signature. */
    private static byte[] rawToDer(BigInteger r, BigInteger s) {
        byte[] rb = toUnsigned(r);
        byte[] sb = toUnsigned(s);
        int len = 2 + rb.length + 2 + sb.length;
        byte[] der = new byte[2 + len];
        int i = 0;
        der[i++] = 0x30;
        der[i++] = (byte) len;
        der[i++] = 0x02;
        der[i++] = (byte) rb.length;
        System.arraycopy(rb, 0, der, i, rb.length); i += rb.length;
        der[i++] = 0x02;
        der[i++] = (byte) sb.length;
        System.arraycopy(sb, 0, der, i, sb.length);
        return der;
    }

    private static byte[] toUnsigned(BigInteger v) {
        byte[] b = v.toByteArray();
        if (b.length > 1 && b[0] == 0x00) {
            // keep one leading zero only if high bit set; BigInteger already
            // adds it for sign — strip extra when not needed.
            if ((b[1] & 0x80) == 0) {
                return Arrays.copyOfRange(b, 1, b.length);
            }
        }
        return b;
    }

    private static String sha256Hex(String s) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(s.getBytes("UTF-8"));
        return HexFormat.of().formatHex(digest);
    }

    private static boolean constantTimeEquals(String a, String b) {
        if (a.length() != b.length()) return false;
        int r = 0;
        for (int i = 0; i < a.length(); i++) r |= a.charAt(i) ^ b.charAt(i);
        return r == 0;
    }
}
