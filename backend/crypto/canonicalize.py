"""Canonicalization logic for deterministic JSON output."""
import json
from typing import Any, Dict
from datetime import datetime
import re


def normalize_timestamp(ts: str) -> str:
    """Normalize timestamp to ISO 8601 UTC format."""
    # Parse various formats and output consistent ISO 8601 UTC
    try:
        # Handle ISO format with Z or +00:00
        ts = ts.replace('Z', '+00:00')
        if '+' in ts or '-' in ts[10:]:  # Has timezone info
            dt = datetime.fromisoformat(ts)
        else:
            # Assume UTC if no timezone
            dt = datetime.fromisoformat(ts + '+00:00')
        
        # Output in consistent format: YYYY-MM-DDTHH:MM:SS.ffffffZ
        return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    except Exception:
        return ts


def normalize_value(value: Any) -> Any:
    """Normalize a single value for canonicalization."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        # Convert float to int if it's a whole number
        if value == int(value):
            return int(value)
        return value
    if isinstance(value, str):
        # Check if it looks like a timestamp
        if re.match(r'\d{4}-\d{2}-\d{2}T', value):
            return normalize_timestamp(value)
        return value
    if isinstance(value, list):
        return [normalize_value(v) for v in value if v is not None]
    if isinstance(value, dict):
        return canonicalize_dict(value)
    return value


def canonicalize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonicalize a dictionary:
    - Sort keys lexicographically
    - Remove null/undefined fields
    - Normalize values
    """
    result = {}
    for key in sorted(data.keys()):
        value = data[key]
        if value is None:
            continue
        normalized = normalize_value(value)
        if normalized is not None:
            result[key] = normalized
    return result


def canonicalize_to_json(data: Dict[str, Any]) -> str:
    """
    Convert dictionary to canonical JSON string.
    This is the ONLY input to hashing.
    """
    canonical = canonicalize_dict(data)
    # Use separators to remove extra whitespace
    # ensure_ascii=False for UTF-8
    return json.dumps(canonical, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
