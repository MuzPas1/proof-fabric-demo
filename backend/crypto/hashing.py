"""SHA-256 hashing for FEA."""
import hashlib
from typing import Dict, Any
from .canonicalize import canonicalize_to_json


def compute_sha256(data: str) -> str:
    """Compute SHA-256 hash of a string, return hex digest."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def hash_canonical_payload(payload: Dict[str, Any]) -> str:
    """
    Hash a payload after canonicalization.
    Returns SHA-256 hex digest.
    """
    canonical_json = canonicalize_to_json(payload)
    return compute_sha256(canonical_json)


def hash_metadata(metadata: Dict[str, Any]) -> str:
    """Hash metadata separately (never embed raw metadata in FEA)."""
    canonical_json = canonicalize_to_json(metadata)
    return compute_sha256(canonical_json)
