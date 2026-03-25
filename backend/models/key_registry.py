"""Key registry models."""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal


class PublicKeyInfo(BaseModel):
    """Public key information for verification."""
    model_config = ConfigDict(extra="ignore")
    
    public_key_id: str
    public_key: str  # Base64 encoded
    algorithm: str = "Ed25519"
    created_at: str
    status: Literal["active", "retired"] = "active"


class KeyRegistryResponse(BaseModel):
    """Response from key registry endpoint."""
    keys: list[PublicKeyInfo]
    total: int = 0
    active_count: int = 0
    retired_count: int = 0
