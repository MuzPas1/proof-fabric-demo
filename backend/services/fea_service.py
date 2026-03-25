"""FEA generation service.

SIGNING MODEL:
- ONLY the fea_payload is signed
- Domain prefix "PFP_V2::" added for cross-protocol attack prevention
- Timestamp validation for boundary checks
- Transaction replay protection via idempotency
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional

from models.fea import (
    GenerateFEARequest,
    FEAResponse,
    FEADocument
)
from crypto.canonicalize import canonicalize_to_json, normalize_timestamp
from crypto.hashing import compute_sha256, hash_metadata
from crypto.signing import sign_message, get_public_key_id, SIGNATURE_VERSION_V2


# Timestamp validation bounds
MAX_FUTURE_SECONDS = 300  # 5 minutes
MAX_PAST_DAYS = 365  # 1 year


def validate_timestamp_bounds(timestamp_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validate timestamp is within acceptable bounds.
    Returns (valid, error_message).
    """
    try:
        normalized = normalize_timestamp(timestamp_str)
        ts = normalized.replace('Z', '+00:00')
        dt = datetime.fromisoformat(ts)
        now = datetime.now(timezone.utc)
        
        # Check future bound
        max_future = now + timedelta(seconds=MAX_FUTURE_SECONDS)
        if dt > max_future:
            return False, f"Timestamp too far in future (max {MAX_FUTURE_SECONDS}s): {timestamp_str}"
        
        # Check past bound
        min_past = now - timedelta(days=MAX_PAST_DAYS)
        if dt < min_past:
            return False, f"Timestamp too far in past (max {MAX_PAST_DAYS} days): {timestamp_str}"
        
        return True, None
    except Exception as e:
        return False, f"Invalid timestamp: {timestamp_str}"


def build_fea_payload(request: GenerateFEARequest) -> Dict[str, Any]:
    """
    Build the FEA payload - THIS IS WHAT GETS SIGNED.
    """
    issuer_id = os.environ.get('ISSUER_ID', 'pfp-issuer-001')
    public_key_id = get_public_key_id()
    normalized_ts = normalize_timestamp(request.timestamp)

    fea_payload = {
        "fea_version": "1.0",
        "issuer_id": issuer_id,
        "public_key_id": public_key_id,
        "transaction_summary": {
            "transaction_id": request.transaction_id,
            "timestamp": normalized_ts,
            "amount": request.amount,
            "currency": request.currency.upper()
        },
        "parties": {
            "payer_hash": request.payer_id,
            "payee_hash": request.payee_id
        }
    }

    if request.metadata:
        fea_payload["metadata_hash"] = hash_metadata(request.metadata)

    return fea_payload


def compute_fea_hash(fea_payload: Dict[str, Any]) -> str:
    """Compute the FEA hash from the canonical payload."""
    payload_without_hash = {k: v for k, v in fea_payload.items() if k != 'fea_hash'}
    canonical_json = canonicalize_to_json(payload_without_hash)
    return compute_sha256(canonical_json)


def generate_fea(request: GenerateFEARequest, skip_timestamp_validation: bool = False) -> Tuple[FEAResponse, FEADocument]:
    """
    Generate a Financial Evidence Artifact.
    
    SECURITY FEATURES:
    - Domain prefix "PFP_V2::" for cross-protocol attack prevention
    - Timestamp boundary validation
    - Deterministic signing
    """
    # Validate timestamp bounds (can be skipped for testing)
    if not skip_timestamp_validation:
        valid, error = validate_timestamp_bounds(request.timestamp)
        if not valid:
            raise ValueError(error)

    # Build fea_payload
    fea_payload = build_fea_payload(request)

    # Compute fea_hash
    fea_hash = compute_fea_hash(fea_payload)
    fea_payload["fea_hash"] = fea_hash

    # Canonicalize and sign (with domain prefix internally)
    canonical_payload = canonicalize_to_json(fea_payload)
    signature = sign_message(canonical_payload)

    # Generate metadata
    fea_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    signature_version = SIGNATURE_VERSION_V2

    # Compute idempotency hash
    canonical_input = canonicalize_to_json({
        "idempotency_key": request.idempotency_key,
        "transaction_id": request.transaction_id,
        "timestamp": normalize_timestamp(request.timestamp),
        "amount": request.amount,
        "currency": request.currency.upper(),
        "payer_id": request.payer_id,
        "payee_id": request.payee_id,
        "metadata": request.metadata
    })
    canonical_payload_hash = compute_sha256(canonical_input)

    response = FEAResponse(
        fea_id=fea_id,
        fea_payload=fea_payload,
        signature=signature,
        signature_version=signature_version,
        public_key_id=fea_payload["public_key_id"],
        created_at=created_at
    )

    document = FEADocument(
        fea_id=fea_id,
        idempotency_key=request.idempotency_key,
        canonical_payload_hash=canonical_payload_hash,
        fea_payload=fea_payload,
        signature=signature,
        signature_version=signature_version,
        public_key_id=fea_payload["public_key_id"],
        created_at=created_at
    )

    return response, document


def get_canonical_payload_hash(request: GenerateFEARequest) -> str:
    """Compute the canonical payload hash for idempotency checking."""
    canonical_input = canonicalize_to_json({
        "idempotency_key": request.idempotency_key,
        "transaction_id": request.transaction_id,
        "timestamp": normalize_timestamp(request.timestamp),
        "amount": request.amount,
        "currency": request.currency.upper(),
        "payer_id": request.payer_id,
        "payee_id": request.payee_id,
        "metadata": request.metadata
    })
    return compute_sha256(canonical_input)
