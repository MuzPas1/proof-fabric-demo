package com.pfprotocol.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.TreeMap;
import java.util.regex.Pattern;

/**
 * PFP canonicalization — faithful port of backend/crypto/canonicalize.py.
 * Sorted keys, null-strip at all depths, whole-number floats collapse to int,
 * ISO timestamps normalized to millisecond UTC, minimal separators, UTF-8.
 */
public final class PfpCanonicalizer {

    private static final Pattern TS = Pattern.compile("^\\d{4}-\\d{2}-\\d{2}T.*");
    private static final DateTimeFormatter MILLIS =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'").withZone(ZoneOffset.UTC);

    private PfpCanonicalizer() {}

    public static String canonicalize(JsonNode node) {
        StringBuilder sb = new StringBuilder();
        write(canonicalizeNode(node), sb);
        return sb.toString();
    }

    /** Returns a normalized representation using TreeMap / List / scalars. */
    private static Object canonicalizeNode(JsonNode node) {
        if (node == null || node.isNull()) return null;
        if (node.isObject()) {
            TreeMap<String, Object> map = new TreeMap<>();
            Iterator<String> it = node.fieldNames();
            while (it.hasNext()) {
                String k = it.next();
                Object v = canonicalizeNode(node.get(k));
                if (v != null) map.put(k, v);
            }
            return map;
        }
        if (node.isArray()) {
            List<Object> list = new ArrayList<>();
            for (JsonNode child : node) {
                if (child != null && !child.isNull()) {
                    Object v = canonicalizeNode(child);
                    if (v != null) list.add(v);
                }
            }
            return list;
        }
        if (node.isBoolean()) return node.booleanValue();
        if (node.isNumber()) {
            BigDecimal bd = node.decimalValue();
            if (bd.stripTrailingZeros().scale() <= 0) {
                return bd.toBigIntegerExact();
            }
            return bd;
        }
        if (node.isTextual()) {
            String s = node.textValue();
            return TS.matcher(s).matches() ? normalizeTimestamp(s) : s;
        }
        return node.asText();
    }

    static String normalizeTimestamp(String ts) {
        try {
            Instant instant = Instant.parse(ts.endsWith("Z") || ts.contains("+") ? ts : ts + "Z");
            return MILLIS.format(instant);
        } catch (Exception e) {
            return ts;
        }
    }

    @SuppressWarnings("unchecked")
    private static void write(Object value, StringBuilder sb) {
        if (value == null) { sb.append("null"); return; }
        if (value instanceof TreeMap) {
            sb.append('{');
            boolean first = true;
            for (var entry : ((TreeMap<String, Object>) value).entrySet()) {
                if (!first) sb.append(',');
                first = false;
                writeString(entry.getKey(), sb);
                sb.append(':');
                write(entry.getValue(), sb);
            }
            sb.append('}');
        } else if (value instanceof List) {
            sb.append('[');
            boolean first = true;
            for (Object item : (List<Object>) value) {
                if (!first) sb.append(',');
                first = false;
                write(item, sb);
            }
            sb.append(']');
        } else if (value instanceof Boolean) {
            sb.append(value.toString());
        } else if (value instanceof BigDecimal) {
            sb.append(((BigDecimal) value).toPlainString());
        } else if (value instanceof Number) {
            sb.append(value.toString());
        } else {
            writeString(value.toString(), sb);
        }
    }

    private static void writeString(String s, StringBuilder sb) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                default:
                    if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
                    else sb.append(c);
            }
        }
        sb.append('"');
    }
}
