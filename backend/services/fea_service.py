"""FEA generation service.

SIGNING MODEL:
- ONLY the fea_payload is signed
- signature_version, created_at are metadata (NOT signed)

SIGNING FLOW:
1. Build fea_payload (without fea_hash)
2. Canonicalize → compute SHA-256 → fea_hash
3. Insert fea_hash into fea_payload
4. Canonicalize full fea_payload
5. Sign canonical fea_payload using Ed25519
6. Return fea_payload + signature + metadata separately
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

from models.fea import (
    GenerateFEARequest,
    FEAResponse,
    FEADocument
)
from crypto.canonicalize import canonicalize_to_json, normalize_timestamp
from crypto.hashing import compute_sha256, hash_metadata
from crypto.signing import sign_message, get_public_key_id, SIGNATURE_VERSION_V2


def build_fea_payload(request: GenerateFEARequest) -> Dict[str, Any]:
    """
    Build the FEA payload - THIS IS WHAT GETS SIGNED.
    
    Does NOT include:
    - signature_version (metadata)
    - created_at (metadata)
    - signature (obviously)
    
    Returns structure WITHOUT fea_hash (added later).
    """
    issuer_id = os.environ.get('ISSUER_ID', 'pfp-issuer-001')
    public_key_id = get_public_key_id()

    # Normalize timestamp
    normalized_ts = normalize_timestamp(request.timestamp)

    # Build FEA payload - ONLY signed data
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

    # Hash metadata if provided (never embed raw)
    if request.metadata:
        fea_payload["metadata_hash"] = hash_metadata(request.metadata)

    return fea_payload


def compute_fea_hash(fea_payload: Dict[str, Any]) -> str:
    """
    Compute the FEA hash from the canonical payload.
    Hash is computed on payload WITHOUT the fea_hash field.
    """
    payload_without_hash = {k: v for k, v in fea_payload.items() if k != 'fea_hash'}
    canonical_json = canonicalize_to_json(payload_without_hash)
    return compute_sha256(canonical_json)


def generate_fea(request: GenerateFEARequest) -> Tuple[FEAResponse, FEADocument]:
    """
    Generate a Financial Evidence Artifact.
    
    SIGNING FLOW:
    1. Build fea_payload (without fea_hash)
    2. Canonicalize → SHA-256 → fea_hash
    3. Insert fea_hash into fea_payload
    4. Canonicalize full fea_payload
    5. Sign canonical fea_payload (Ed25519)
    
    Returns:
    - fea_payload: the signed data
    - signature: pure base64
    - signature_version: metadata (NOT signed)
    - created_at: metadata (NOT signed)
    """
    # Step 1: Build fea_payload (without fea_hash)
    fea_payload = build_fea_payload(request)

    # Step 2: Compute fea_hash
    fea_hash = compute_fea_hash(fea_payload)

    # Step 3: Insert fea_hash into fea_payload
    fea_payload["fea_hash"] = fea_hash

    # Step 4: Canonicalize full fea_payload
    canonical_payload = canonicalize_to_json(fea_payload)

    # Step 5: Sign canonical fea_payload (ONLY the payload, not metadata)
    signature = sign_message(canonical_payload)

    # Generate metadata (NOT part of signed data)
    fea_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    signature_version = SIGNATURE_VERSION_V2

    # Compute idempotency hash (based on input request)
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

    # Build response - clean separation
    response = FEAResponse(
        fea_id=fea_id,
        fea_payload=fea_payload,
        signature=signature,
        signature_version=signature_version,
        public_key_id=fea_payload["public_key_id"],
        created_at=created_at
    )

    # Build document for storage
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
