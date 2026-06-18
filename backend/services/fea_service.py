"""Proof Artifact generation service.

Internally the artifact and its fields use the `fea` / `fea_id` contract names
for backward compatibility.

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
from crypto.signing import sign_message, get_public_key_id, get_public_key_id_for, SIGNATURE_VERSION_V2
from crypto import suites


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


def build_fea_payload(request: GenerateFEARequest, tenant_id: str = "default", suite_alg: str = "Ed25519", signer=None) -> Dict[str, Any]:
    """
    Build the FEA payload - THIS IS WHAT GETS SIGNED.

    v1.1 adds issuance-proof + tenant-binding fields INSIDE the signed payload:
      - iat        : issuance time (when PFP signed it), ISO-8601 UTC
      - jti        : unique proof identifier (nonce)
      - tenant_id  : owning tenant (cryptographically bound)
      - algorithm  : explicit signature algorithm (algorithm-confusion defense)

    ``suite_alg`` selects the signature suite (default Ed25519). When a ``signer``
    is provided (BYOS), its algorithm and public-key id are used instead — the
    chosen suite's public key id is embedded so the verifier resolves the right
    key, and ``algorithm`` is bound into the signed payload.
    """
    if signer is not None:
        suite_alg = suites.normalize_algorithm(signer.algorithm)
        public_key_id = signer.public_key_id()
    else:
        suite_alg = suites.normalize_algorithm(suite_alg)
        public_key_id = get_public_key_id_for(suite_alg)
    issuer_id = os.environ.get('ISSUER_ID', 'pfp-issuer-001')
    normalized_ts = normalize_timestamp(request.timestamp)
    iat = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    fea_payload = {
        "fea_version": "1.1",
        "algorithm": suite_alg,
        "issuer_id": issuer_id,
        "tenant_id": tenant_id,
        "public_key_id": public_key_id,
        "iat": iat,
        "jti": str(uuid.uuid4()),
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


def generate_fea(request: GenerateFEARequest, skip_timestamp_validation: bool = False, tenant_id: str = "default", suite_alg: str = "Ed25519", signer=None) -> Tuple[FEAResponse, FEADocument]:
    """
    Generate a Proof Artifact.
    
    SECURITY FEATURES:
    - Domain prefix "PFP_V2::" for cross-protocol attack prevention
    - Timestamp boundary validation
    - Deterministic signing
    - Tenant-bound, issuance-stamped signed payload (v1.1)
    - Selectable signature suite (Ed25519 default; ES256 / ES256K)
    - Pluggable signer (BYOS): local KMS, remote signer, or cloud KMS
    """
    if signer is not None:
        suite_alg = suites.normalize_algorithm(signer.algorithm)
    else:
        suite_alg = suites.normalize_algorithm(suite_alg)

    # Validate timestamp bounds (can be skipped for testing)
    if not skip_timestamp_validation:
        valid, error = validate_timestamp_bounds(request.timestamp)
        if not valid:
            raise ValueError(error)

    # Build fea_payload
    fea_payload = build_fea_payload(request, tenant_id=tenant_id, suite_alg=suite_alg, signer=signer)

    # Compute fea_hash
    fea_hash = compute_fea_hash(fea_payload)
    fea_payload["fea_hash"] = fea_hash

    # Canonicalize and sign (with domain prefix internally) under the suite/signer
    canonical_payload = canonicalize_to_json(fea_payload)
    if signer is not None:
        from crypto.signing import DOMAIN_PREFIX_V2
        import base64 as _b64
        signature = _b64.b64encode(
            signer.sign((DOMAIN_PREFIX_V2 + canonical_payload).encode("utf-8"))
        ).decode("ascii")
    else:
        signature = sign_message(canonical_payload, suite_alg=suite_alg)

    # Generate metadata
    fea_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    signature_version = SIGNATURE_VERSION_V2

    # Compute idempotency hash (includes idempotency_key)
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

    # Compute transaction payload hash (excludes idempotency_key — for replay protection)
    txn_input = canonicalize_to_json({
        "transaction_id": request.transaction_id,
        "timestamp": normalize_timestamp(request.timestamp),
        "amount": request.amount,
        "currency": request.currency.upper(),
        "payer_id": request.payer_id,
        "payee_id": request.payee_id,
        "metadata": request.metadata
    })
    transaction_payload_hash = compute_sha256(txn_input)

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
        tenant_id=tenant_id,
        canonical_payload_hash=canonical_payload_hash,
        transaction_payload_hash=transaction_payload_hash,
        fea_payload=fea_payload,
        signature=signature,
        signature_version=signature_version,
        public_key_id=fea_payload["public_key_id"],
        created_at=created_at
    )

    return response, document


def get_canonical_payload_hash(request: GenerateFEARequest) -> str:
    """Compute the canonical payload hash for idempotency checking (includes idempotency_key)."""
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


def get_transaction_payload_hash(request: GenerateFEARequest) -> str:
    """Compute a hash of the transaction payload ONLY (excludes idempotency_key).
    Used for replay protection — same transaction event should produce the same hash
    regardless of which idempotency key was used."""
    canonical_input = canonicalize_to_json({
        "transaction_id": request.transaction_id,
        "timestamp": normalize_timestamp(request.timestamp),
        "amount": request.amount,
        "currency": request.currency.upper(),
        "payer_id": request.payer_id,
        "payee_id": request.payee_id,
        "metadata": request.metadata
    })
    return compute_sha256(canonical_input)
