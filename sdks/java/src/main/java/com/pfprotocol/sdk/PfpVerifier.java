package com.pfprotocol.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import java.util.HexFormat;

/**
 * Independent PFP FEA / artifact verification for Java (JDK 15+, native Ed25519).
 *
 * No PFP server round-trip required — verify any FEA with just the issuer's
 * public key (base64, from GET /api/public/keys).
 *
 * Dependency: jackson-databind (for JSON parsing only).
 */
public final class PfpVerifier {

    private static final String DOMAIN_PREFIX_V2 = "PFP_V2::";
    private static final String ARTIFACT_DOMAIN_PREFIX = "PFP_ARTIFACT_V1::";
    // DER SPKI header for a raw Ed25519 public key.
    private static final byte[] ED25519_SPKI_PREFIX =
            HexFormat.of().parseHex("302a300506032b6570032100");

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

        String message = DOMAIN_PREFIX_V2 + PfpCanonicalizer.canonicalize(payload);
        boolean ok = ed25519Verify(message.getBytes("UTF-8"), signatureB64, publicKeyB64);
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
        String message = ARTIFACT_DOMAIN_PREFIX + PfpCanonicalizer.canonicalize(base);
        boolean ok = ed25519Verify(message.getBytes("UTF-8"),
                artifact.get("signature").asText(), publicKeyB64);
        return ok ? new Result(true, null) : new Result(false, "Invalid signature");
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
