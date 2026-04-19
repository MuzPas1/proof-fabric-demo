"""
Demo routes — Two-Party Proof Comparison.

Public, unauthenticated demo endpoint that normalizes a party record and
returns a deterministic proof hash. Intended to showcase proof-based
consistency comparison across two independent parties.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Union
from datetime import datetime

from crypto.canonicalize import canonicalize_to_json, normalize_timestamp
from crypto.hashing import compute_sha256


router = APIRouter(prefix="/demo", tags=["Demo"])


class PartyRecord(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=200)
    user_id: str = Field(..., min_length=1, max_length=200)
    amount: Union[str, float, int]
    created_at: str = Field(..., min_length=1)


class ProofMetadata(BaseModel):
    algorithm: str
    canonicalization: str
    generated_at: str


class ProofResponse(BaseModel):
    proof_hash: str
    normalized_payload: dict
    metadata: ProofMetadata


def _normalize_amount(amount: Union[str, float, int]) -> str:
    """Normalize amount to a canonical string with 2 decimal places."""
    try:
        if isinstance(amount, str):
            amount = amount.strip().replace(",", "")
            if amount == "":
                raise ValueError("empty amount")
        value = float(amount)
        return f"{value:.2f}"
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid amount: {amount!r}",
        )


def _normalize_timestamp_safe(ts: str) -> str:
    """Normalize timestamp; raise 400 on invalid input."""
    raw = ts.strip()
    normalized = normalize_timestamp(raw)
    # normalize_timestamp returns raw value on parse failure — detect that.
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid timestamp: {ts!r}",
        )
    return normalized


def normalize_party_record(record: PartyRecord) -> dict:
    """
    Normalize a party record so logically identical inputs produce
    identical canonical representations.

    Rules:
      - trim surrounding whitespace
      - lowercase user_id (casing consistency across systems)
      - preserve transaction_id casing (treated as opaque identifier)
      - amount → string with 2 decimals
      - created_at → ISO 8601 UTC (`...Z`)
      - deterministic field ordering is applied later by canonicalization
    """
    return {
        "transaction_id": record.transaction_id.strip(),
        "user_id": record.user_id.strip().lower(),
        "amount": _normalize_amount(record.amount),
        "created_at": _normalize_timestamp_safe(record.created_at),
    }


@router.post("/proof", response_model=ProofResponse)
async def generate_party_proof(record: PartyRecord):
    """
    Generate a deterministic proof for a party record.

    Steps:
      1. Normalize fields (trim, casing, amount format, timestamp format)
      2. Canonicalize to a deterministic JSON string (sorted keys)
      3. SHA-256 hash the canonical JSON

    Two parties applying these same steps to logically-identical records
    will produce identical `proof_hash` values — enabling proof-based
    consistency comparison without exposing raw data.
    """
    normalized = normalize_party_record(record)
    canonical_json = canonicalize_to_json(normalized)
    proof_hash = compute_sha256(canonical_json)

    return ProofResponse(
        proof_hash=proof_hash,
        normalized_payload=normalized,
        metadata=ProofMetadata(
            algorithm="SHA-256",
            canonicalization="sorted-keys/utf-8/no-whitespace",
            generated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        ),
    )
