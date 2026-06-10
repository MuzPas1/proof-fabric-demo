"""PFP canonicalization — faithful port of the server's deterministic JSON rules.

Rules (must match backend/crypto/canonicalize.py byte-for-byte):
  1. Objects: keys sorted lexicographically; null values removed at every depth.
  2. Numbers: floats equal to a whole number collapse to int (100.0 -> 100).
  3. Strings matching ^\\d{4}-\\d{2}-\\d{2}T are normalized to
     YYYY-MM-DDTHH:MM:SS.mmmZ (millisecond precision, UTC).
  4. Arrays: each non-null element normalized, nulls dropped.
  5. Serialization: minimal separators (",", ":"), UTF-8, ensure_ascii=False.
"""
import json
import re
from datetime import datetime

_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T")


def normalize_timestamp(ts: str) -> str:
    try:
        ts = ts.replace("Z", "+00:00")
        if "+" in ts or "-" in ts[10:]:
            dt = datetime.fromisoformat(ts)
        else:
            dt = datetime.fromisoformat(ts + "+00:00")
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except Exception:
        return ts


def _normalize_value(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value == int(value):
            return int(value)
        return value
    if isinstance(value, str):
        if _TS_RE.match(value):
            return normalize_timestamp(value)
        return value
    if isinstance(value, list):
        return [_normalize_value(v) for v in value if v is not None]
    if isinstance(value, dict):
        return _canonicalize_dict(value)
    return value


def _canonicalize_dict(data: dict) -> dict:
    result = {}
    for key in sorted(data.keys()):
        value = data[key]
        if value is None:
            continue
        normalized = _normalize_value(value)
        if normalized is not None:
            result[key] = normalized
    return result


def canonicalize_to_json(data: dict) -> str:
    canonical = _canonicalize_dict(data)
    return json.dumps(canonical, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
