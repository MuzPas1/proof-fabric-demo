"""FEA generation service.

SIGNING MODEL (v2):
1. Build FEA structure (without fea_hash)
2. Canonicalize JSON
3. Compute SHA-256 → fea_hash
4. Add fea_hash into FEA structure
5. Canonicalize FINAL structure (including fea_hash)
6. Sign the final canonical JSON directly using Ed25519
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
from crypto.signing import sign_message, get_public_key_id


def build_fea_structure(request: GenerateFEARequest) -> Dict[str, Any]:
    """
    Build the canonical FEA structure (Section 3) from input request.
    Returns structure WITHOUT fea_hash (added later).
    """
    issuer_id = os.environ.get('ISSUER_ID', 'pfp-issuer-001')
    public_key_id = get_public_key_id()

    # Normalize timestamp
    normalized_ts = normalize_timestamp(request.timestamp)

    # Build FEA structure
    fea_dict = {
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
        fea_dict["metadata_hash"] = hash_metadata(request.metadata)

    return fea_dict


def compute_fea_hash(fea_structure: Dict[str, Any]) -> str:
    """
    Compute the FEA hash from the canonical FEA structure.
    The hash is computed on the structure WITHOUT the fea_hash field.
    
    Used for:
    - Integrity verification
    - Idempotency checking
    - Indexing
    """
    # Ensure fea_hash is not in the structure when computing
    structure_copy = {k: v for k, v in fea_structure.items() if k != 'fea_hash'}
    canonical_json = canonicalize_to_json(structure_copy)
    return compute_sha256(canonical_json)


def generate_fea(request: GenerateFEARequest) -> Tuple[FEAResponse, FEADocument]:
    """
    Generate a Financial Evidence Artifact from the request.
    
    SIGNING MODEL (v2):
    1. Build FEA structure (without fea_hash)
    2. Canonicalize and compute SHA-256 → fea_hash
    3. Add fea_hash to structure
    4. Canonicalize FULL structure (with fea_hash)
    5. Sign the canonical JSON directly (Ed25519 message signing)
    
    Returns both the response and the document to store.
    """
    # Step 1: Build FEA structure (without fea_hash)
    fea_structure = build_fea_structure(request)

    # Step 2: Compute SHA-256 hash on structure (without fea_hash)
    fea_hash = compute_fea_hash(fea_structure)

    # Step 3: Add fea_hash to structure
    fea_structure["fea_hash"] = fea_hash

    # Step 4: Canonicalize FULL structure (including fea_hash)
    final_canonical_json = canonicalize_to_json(fea_structure)

    # Step 5: Sign the canonical JSON directly (v2 model)
    signature = sign_message(final_canonical_json)

    # Generate FEA ID
    fea_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # Compute canonical payload hash for idempotency (based on input)
    canonical_input_json = canonicalize_to_json({
        "idempotency_key": request.idempotency_key,
        "transaction_id": request.transaction_id,
        "timestamp": normalize_timestamp(request.timestamp),
        "amount": request.amount,
        "currency": request.currency.upper(),
        "payer_id": request.payer_id,
        "payee_id": request.payee_id,
        "metadata": request.metadata
    })
    canonical_payload_hash = compute_sha256(canonical_input_json)

    # Build response
    response = FEAResponse(
        fea_id=fea_id,
        fea_hash=fea_hash,
        signature=signature,
        public_key_id=fea_structure["public_key_id"],
        fea_payload=fea_structure,
        created_at=created_at
    )

    # Build document for storage
    document = FEADocument(
        fea_id=fea_id,
        idempotency_key=request.idempotency_key,
        canonical_payload_hash=canonical_payload_hash,
        fea_hash=fea_hash,
        signature=signature,
        public_key_id=fea_structure["public_key_id"],
        created_at=created_at,
        fea_payload=fea_structure
    )

    return response, document


def get_canonical_payload_hash(request: GenerateFEARequest) -> str:
    """Compute the canonical payload hash for idempotency checking."""
    canonical_input_json = canonicalize_to_json({
        "idempotency_key": request.idempotency_key,
        "transaction_id": request.transaction_id,
        "timestamp": normalize_timestamp(request.timestamp),
        "amount": request.amount,
        "currency": request.currency.upper(),
        "payer_id": request.payer_id,
        "payee_id": request.payee_id,
        "metadata": request.metadata
    })
    return compute_sha256(canonical_input_json)
