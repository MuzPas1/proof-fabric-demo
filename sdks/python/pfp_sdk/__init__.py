"""PFP Python SDK — client for the Proof Fabric Protocol API.

Usage:
    from pfp_sdk import PFPClient
    pfp = PFPClient("https://api.pfprotocol.com", api_key="pfp_live_...")
    fea = pfp.generate_fea(idempotency_key="...", transaction_id="...",
                           timestamp="2026-06-10T12:00:00Z", amount=250000,
                           currency="INR", payer_id="...", payee_id="...")
    # Independent verification (no server round-trip):
    keys = pfp.public_keys()
    pub = next(k["public_key"] for k in keys["keys"]
               if k["public_key_id"] == fea["public_key_id"])
    print(pfp.verify_local(fea["fea_payload"], fea["signature"], pub))
"""
from typing import Any, Dict, List, Optional

import requests

from .verify import verify_fea as _verify_fea_local, verify_artifact as _verify_artifact_local

__all__ = ["PFPClient"]


class PFPError(Exception):
    pass


class PFPClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = 15.0):
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self, auth: bool = True) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if auth and self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    def _post(self, path: str, body: dict, auth: bool = True) -> dict:
        r = requests.post(f"{self.base}{path}", json=body, headers=self._headers(auth), timeout=self.timeout)
        if not r.ok:
            raise PFPError(f"{r.status_code}: {r.text}")
        return r.json()

    def _get(self, path: str, auth: bool = False) -> dict:
        r = requests.get(f"{self.base}{path}", headers=self._headers(auth), timeout=self.timeout)
        if not r.ok:
            raise PFPError(f"{r.status_code}: {r.text}")
        return r.json()

    # --- FEA ---
    def generate_fea(self, **kwargs) -> dict:
        return self._post("/api/fea/generate", kwargs)

    def batch_generate(self, items: List[dict]) -> dict:
        return self._post("/api/fea/batch", {"items": items})

    def verify_fea(self, fea_payload: dict, signature: str, signature_version: Optional[str] = None) -> dict:
        return self._post("/api/fea/verify", {
            "fea_payload": fea_payload, "signature": signature,
            "signature_version": signature_version,
        })

    def list_feas(self, limit: int = 50, skip: int = 0) -> dict:
        return self._get(f"/api/fea?limit={limit}&skip={skip}", auth=True)

    def get_fea(self, fea_id: str) -> dict:
        return self._get(f"/api/fea/{fea_id}", auth=True)

    # --- Public ---
    def public_verify(self, fea_id: str) -> dict:
        return self._get(f"/api/public/verify/{fea_id}")

    def public_keys(self) -> dict:
        return self._get("/api/public/keys")

    # --- Webhooks ---
    def subscribe_webhook(self, url: str, events: Optional[List[str]] = None) -> dict:
        return self._post("/api/webhooks/subscribe", {"url": url, "events": events or ["fea.generated"]})

    # --- Independent verification (offline) ---
    def verify_local(self, fea_payload: dict, signature: str, public_key_b64: str) -> dict:
        return _verify_fea_local(fea_payload, signature, public_key_b64)

    def verify_artifact_local(self, artifact: dict, public_key_b64: str) -> dict:
        return _verify_artifact_local(artifact, public_key_b64)
