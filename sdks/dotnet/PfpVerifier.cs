using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Numerics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;

namespace Pfp.Sdk
{
    /// <summary>
    /// Independent PFP FEA / artifact verification for .NET.
    /// Canonicalization is a faithful port of backend/crypto/canonicalize.py.
    /// Ed25519 verification uses BouncyCastle (Org.BouncyCastle.Cryptography).
    /// No PFP server round-trip required.
    /// </summary>
    public static class PfpVerifier
    {
        private const string DomainPrefixV2 = "PFP_V2::";
        private const string ArtifactDomainPrefix = "PFP_ARTIFACT_V1::";

        public record Result(bool Valid, string? Reason);

        public static Result VerifyFea(string feaPayloadJson, string signatureB64, string publicKeyB64)
        {
            using var doc = JsonDocument.Parse(feaPayloadJson);
            var root = doc.RootElement;
            if (!root.TryGetProperty("fea_hash", out var hashEl))
                return new Result(false, "Missing fea_hash");
            var claimed = hashEl.GetString()!;

            var dict = ToDictionary(root);
            var withoutHash = new SortedDictionary<string, object?>(dict);
            withoutHash.Remove("fea_hash");
            var computed = Sha256Hex(Canonicalize(withoutHash));
            if (!FixedTimeEquals(computed, claimed))
                return new Result(false, "Hash mismatch: payload tampered");

            var message = DomainPrefixV2 + Canonicalize(dict);
            return Ed25519Verify(Encoding.UTF8.GetBytes(message), signatureB64, publicKeyB64)
                ? new Result(true, null)
                : new Result(false, "Invalid signature");
        }

        public static Result VerifyArtifact(string artifactJson, string publicKeyB64)
        {
            using var doc = JsonDocument.Parse(artifactJson);
            var dict = ToDictionary(doc.RootElement);
            if (!dict.ContainsKey("signature") || !dict.ContainsKey("proof_id"))
                return new Result(false, "Missing signature/proof_id");

            var signature = (string)dict["signature"]!;
            var proofId = dict["proof_id"]!.ToString()!;
            var baseDict = new SortedDictionary<string, object?>(dict);
            baseDict.Remove("signature");
            var baseForId = new SortedDictionary<string, object?>(baseDict);
            baseForId.Remove("proof_id");
            if (!FixedTimeEquals(Sha256Hex(Canonicalize(baseForId)), proofId))
                return new Result(false, "proof_id mismatch");

            var message = ArtifactDomainPrefix + Canonicalize(baseDict);
            return Ed25519Verify(Encoding.UTF8.GetBytes(message), signature, publicKeyB64)
                ? new Result(true, null)
                : new Result(false, "Invalid signature");
        }

        // ---- Canonicalization ----
        private static SortedDictionary<string, object?> ToDictionary(JsonElement el)
        {
            var map = new SortedDictionary<string, object?>(StringComparer.Ordinal);
            foreach (var prop in el.EnumerateObject())
            {
                var v = ToValue(prop.Value);
                if (v != null) map[prop.Name] = v;
            }
            return map;
        }

        private static object? ToValue(JsonElement el) => el.ValueKind switch
        {
            JsonValueKind.Null => null,
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.String => NormalizeString(el.GetString()!),
            JsonValueKind.Number => NormalizeNumber(el),
            JsonValueKind.Object => ToDictionary(el),
            JsonValueKind.Array => el.EnumerateArray()
                .Where(x => x.ValueKind != JsonValueKind.Null)
                .Select(ToValue).Where(x => x != null).ToList(),
            _ => el.GetRawText()
        };

        private static object NormalizeNumber(JsonElement el)
        {
            var raw = el.GetRawText();
            if (decimal.TryParse(raw, NumberStyles.Any, CultureInfo.InvariantCulture, out var dec))
            {
                if (dec == Math.Truncate(dec)) return new BigInteger(dec);
                return dec;
            }
            return raw;
        }

        private static object NormalizeString(string s)
        {
            if (s.Length >= 11 && System.Text.RegularExpressions.Regex.IsMatch(s, @"^\d{4}-\d{2}-\d{2}T"))
            {
                if (DateTimeOffset.TryParse(s, CultureInfo.InvariantCulture,
                        DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out var dto))
                    return dto.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", CultureInfo.InvariantCulture);
            }
            return s;
        }

        private static string Canonicalize(object? value)
        {
            var sb = new StringBuilder();
            Write(value, sb);
            return sb.ToString();
        }

        private static void Write(object? value, StringBuilder sb)
        {
            switch (value)
            {
                case null: sb.Append("null"); break;
                case SortedDictionary<string, object?> map:
                    sb.Append('{');
                    var first = true;
                    foreach (var kv in map)
                    {
                        if (!first) sb.Append(',');
                        first = false;
                        WriteString(kv.Key, sb); sb.Append(':'); Write(kv.Value, sb);
                    }
                    sb.Append('}');
                    break;
                case List<object?> list:
                    sb.Append('[');
                    for (var i = 0; i < list.Count; i++)
                    {
                        if (i > 0) sb.Append(',');
                        Write(list[i], sb);
                    }
                    sb.Append(']');
                    break;
                case bool b: sb.Append(b ? "true" : "false"); break;
                case BigInteger bi: sb.Append(bi.ToString(CultureInfo.InvariantCulture)); break;
                case decimal d: sb.Append(d.ToString(CultureInfo.InvariantCulture)); break;
                case string s: WriteString(s, sb); break;
                default: WriteString(value.ToString()!, sb); break;
            }
        }

        private static void WriteString(string s, StringBuilder sb)
        {
            sb.Append('"');
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }

        // ---- Crypto ----
        private static bool Ed25519Verify(byte[] message, string signatureB64, string publicKeyB64)
        {
            try
            {
                var pub = Convert.FromBase64String(publicKeyB64);
                var verifier = new Ed25519Signer();
                verifier.Init(false, new Ed25519PublicKeyParameters(pub, 0));
                verifier.BlockUpdate(message, 0, message.Length);
                return verifier.VerifySignature(Convert.FromBase64String(signatureB64));
            }
            catch { return false; }
        }

        private static string Sha256Hex(string s)
        {
            var hash = SHA256.HashData(Encoding.UTF8.GetBytes(s));
            return Convert.ToHexString(hash).ToLowerInvariant();
        }

        private static bool FixedTimeEquals(string a, string b) =>
            CryptographicOperations.FixedTimeEquals(
                Encoding.UTF8.GetBytes(a), Encoding.UTF8.GetBytes(b));
    }
}
