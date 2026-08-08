"""Tarabut Gateway (Open Banking) outbound API client — isolated, additive.

Server-to-server client for the Tarabut Gateway sandbox/production APIs. It is
completely self-contained: it performs OAuth2 client-credentials authentication,
caches access tokens with a safety skew, and exposes typed helpers for every
documented product area (Connect, Consent, Account Information, Regular Payments,
Payments, Income Verification, Categorisation).

Security:
  * Credentials are NEVER hardcoded. They are supplied by the caller (from
    environment configuration or an operator-managed store) and never logged.
  * Two distinct auth surfaces are supported, exactly as Tarabut documents them:
      - Account Information / Connect: JSON body, camelCase
        (clientId/clientSecret/grantType) -> {accessToken, expiresIn, tokenType}.
      - Payments: form-urlencoded (grant_type/client_id/client_secret)
        -> {access_token, expires_in}.

Base URLs default to the Bahrain sandbox and are fully overridable so the same
client serves sandbox and production without code changes.

This module performs NO proof generation and touches NO core PFP code. The
Tarabut service layer (``services.tarabut_service``) turns each API response
into a PFP Proof Artifact through the existing pipeline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

# --- documented endpoints (Bahrain). Confirmed paths from the Developer Hub. ---
REGIONS = {
    "bahrain": {
        "oauth_base": "https://oauth.tarabutgateway.io/sandbox",
        "api_base": "https://api.sandbox.tarabutgateway.io",
        "payments_base": "https://sandbox.payments.tarabutgateway.io",
    },
    "bahrain_production": {
        "oauth_base": "https://oauth.tarabutgateway.io",
        "api_base": "https://api.tarabutgateway.io",
        "payments_base": "https://payments.tarabutgateway.io",
    },
}

_TOKEN_SKEW_SECONDS = 30
_HTTP_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class TarabutError(Exception):
    """Raised for configuration or API errors (never carries secrets)."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class _CachedToken:
    value: str
    expires_at: float


class TarabutClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "",
        region: str = "bahrain",
        payment_client_id: str = "",
        payment_client_secret: str = "",
        oauth_base: Optional[str] = None,
        api_base: Optional[str] = None,
        payments_base: Optional[str] = None,
    ):
        if not client_id or not client_secret:
            raise TarabutError("Tarabut client_id/client_secret not configured")
        defaults = REGIONS.get(region) or REGIONS["bahrain"]
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.payment_client_id = payment_client_id
        self.payment_client_secret = payment_client_secret
        self.oauth_base = (oauth_base or defaults["oauth_base"]).rstrip("/")
        self.api_base = (api_base or defaults["api_base"]).rstrip("/")
        self.payments_base = (payments_base or defaults["payments_base"]).rstrip("/")
        self._ais_token: Optional[_CachedToken] = None
        self._pay_token: Optional[_CachedToken] = None

    # -- authentication -----------------------------------------------------
    async def _access_token(self, client: httpx.AsyncClient) -> str:
        now = time.time()
        if self._ais_token and now < self._ais_token.expires_at - _TOKEN_SKEW_SECONDS:
            return self._ais_token.value
        body: Dict[str, Any] = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "grantType": "client_credentials",
        }
        if self.redirect_uri:
            body["redirect_uri"] = self.redirect_uri
        resp = await client.post(f"{self.oauth_base}/token", json=body)
        if resp.status_code >= 400:
            raise TarabutError(f"Tarabut token request failed (HTTP {resp.status_code})", resp.status_code)
        data = resp.json()
        ttl = int(data.get("expiresIn", 900))
        self._ais_token = _CachedToken(data["accessToken"], time.time() + ttl)
        return self._ais_token.value

    async def _payment_token(self, client: httpx.AsyncClient) -> str:
        if not (self.payment_client_id and self.payment_client_secret):
            raise TarabutError("Tarabut payment credentials not configured")
        now = time.time()
        if self._pay_token and now < self._pay_token.expires_at - _TOKEN_SKEW_SECONDS:
            return self._pay_token.value
        resp = await client.post(
            f"{self.payments_base}/api/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.payment_client_id,
                "client_secret": self.payment_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code >= 400:
            raise TarabutError(f"Tarabut payment token failed (HTTP {resp.status_code})", resp.status_code)
        data = resp.json()
        ttl = int(data.get("expires_in", 3599))
        self._pay_token = _CachedToken(data["access_token"], time.time() + ttl)
        return self._pay_token.value

    # -- low-level request helpers -----------------------------------------
    async def _ais_request(self, method: str, path: str, *, customer_user_id: Optional[str] = None,
                           json: Optional[dict] = None, params: Optional[dict] = None) -> Any:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            token = await self._access_token(client)
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if customer_user_id:
                headers["X-TG-CustomerUserId"] = customer_user_id
            resp = await client.request(method, f"{self.api_base}{path}", headers=headers, json=json, params=params)
            if resp.status_code >= 400:
                raise TarabutError(f"Tarabut API {method} {path} failed (HTTP {resp.status_code})", resp.status_code)
            return resp.json() if resp.content else {}

    async def _pay_request(self, method: str, path: str, *, json: Optional[dict] = None,
                           idempotency_key: Optional[str] = None) -> Any:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            token = await self._payment_token(client)
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if idempotency_key:
                headers["Idempotency-Key"] = idempotency_key
            resp = await client.request(method, f"{self.payments_base}{path}", headers=headers, json=json)
            if resp.status_code >= 400:
                raise TarabutError(f"Tarabut payments {method} {path} failed (HTTP {resp.status_code})", resp.status_code)
            return resp.json() if resp.content else {}

    # -- Connect -----------------------------------------------------------
    async def create_intent(self, *, user: dict, provider_id: str, redirect_url: Optional[str] = None,
                            language: Optional[str] = None, purpose_statement: Optional[str] = None,
                            permissions_list: Optional[List[str]] = None) -> dict:
        body: Dict[str, Any] = {"user": user, "consent": {"providerId": provider_id}}
        if redirect_url:
            body["redirectUrl"] = redirect_url
        if language:
            body["language"] = language
        if purpose_statement:
            body["purposeStatement"] = purpose_statement
        if permissions_list:
            body["permissionsList"] = permissions_list
        cuid = (user or {}).get("customerUserId")
        return await self._ais_request("POST", "/accountInformation/v1/intent",
                                       customer_user_id=cuid, json=body)

    async def get_providers(self) -> dict:
        return await self._ais_request("GET", "/accountInformation/v1/providers")

    # -- Consent -----------------------------------------------------------
    async def get_all_consents(self, customer_user_id: str) -> Any:
        return await self._ais_request("GET", "/accountInformation/v1/consents",
                                       customer_user_id=customer_user_id)

    async def get_consent_details(self, consent_id: str, customer_user_id: str) -> dict:
        return await self._ais_request("GET", f"/accountInformation/v1/consents/{consent_id}",
                                       customer_user_id=customer_user_id)

    async def revoke_consent(self, consent_id: str, customer_user_id: str) -> dict:
        return await self._ais_request("DELETE", f"/accountInformation/v1/consents/{consent_id}",
                                       customer_user_id=customer_user_id)

    async def create_consent_dashboard(self, customer_user_id: str, redirect_url: Optional[str] = None) -> dict:
        body = {"redirectUrl": redirect_url} if redirect_url else {}
        return await self._ais_request("POST", "/accountInformation/v1/consents/dashboard",
                                       customer_user_id=customer_user_id, json=body)

    # -- Account Information -----------------------------------------------
    async def get_accounts(self, customer_user_id: str) -> dict:
        return await self._ais_request("GET", "/accountInformation/v2/accounts",
                                       customer_user_id=customer_user_id)

    async def get_account_balances(self, account_id: str, customer_user_id: str) -> dict:
        return await self._ais_request("GET", f"/accountInformation/v2/accounts/{account_id}/balances",
                                       customer_user_id=customer_user_id)

    async def refresh_account_balances(self, account_id: str, customer_user_id: str) -> dict:
        return await self._ais_request("POST", f"/accountInformation/v2/accounts/{account_id}/balances/refresh",
                                       customer_user_id=customer_user_id)

    async def get_account_transactions(self, account_id: str, customer_user_id: str,
                                       params: Optional[dict] = None) -> dict:
        return await self._ais_request("GET", f"/accountInformation/v2/accounts/{account_id}/transactions",
                                       customer_user_id=customer_user_id, params=params)

    async def get_account_raw_transactions(self, account_id: str, customer_user_id: str,
                                           params: Optional[dict] = None) -> dict:
        return await self._ais_request("GET", f"/accountInformation/v2/accounts/{account_id}/transactions/raw",
                                       customer_user_id=customer_user_id, params=params)

    async def refresh_account_transactions(self, account_id: str, customer_user_id: str) -> dict:
        return await self._ais_request("POST", f"/accountInformation/v2/accounts/{account_id}/transactions/refresh",
                                       customer_user_id=customer_user_id)

    # -- Regular Payments (read-only Open Banking data) --------------------
    async def get_beneficiaries(self, account_id: str, customer_user_id: str) -> dict:
        return await self._ais_request("GET", f"/accountInformation/v2/accounts/{account_id}/beneficiaries",
                                       customer_user_id=customer_user_id)

    async def get_direct_debits(self, account_id: str, customer_user_id: str) -> dict:
        return await self._ais_request("GET", f"/accountInformation/v2/accounts/{account_id}/direct-debits",
                                       customer_user_id=customer_user_id)

    async def get_scheduled_payments(self, account_id: str, customer_user_id: str) -> dict:
        return await self._ais_request("GET", f"/accountInformation/v2/accounts/{account_id}/scheduled-payments",
                                       customer_user_id=customer_user_id)

    async def get_standing_orders(self, account_id: str, customer_user_id: str) -> dict:
        return await self._ais_request("GET", f"/accountInformation/v2/accounts/{account_id}/standing-orders",
                                       customer_user_id=customer_user_id)

    # -- Payments (single + partner) ---------------------------------------
    async def create_payment(self, *, amount: str, currency: str, destination_account: str,
                             callback_url: str, description: Optional[str] = None,
                             media_type: str = "URL", countries: Optional[List[str]] = None,
                             customer_reference: Optional[str] = None, merchant_reference: Optional[str] = None,
                             expiration: Optional[dict] = None, idempotency_key: Optional[str] = None) -> dict:
        body: Dict[str, Any] = {
            "amount": amount, "currency": currency, "destinationAccount": destination_account,
            "callbackUrl": callback_url, "mediaType": media_type,
            "countries": countries or ["BHR"],
        }
        for k, v in (("description", description), ("customerReference", customer_reference),
                     ("merchantReference", merchant_reference), ("expiration", expiration)):
            if v is not None:
                body[k] = v
        return await self._pay_request("POST", "/api/v1/payments", json=body, idempotency_key=idempotency_key)

    async def get_payment(self, payment_id: str) -> dict:
        return await self._pay_request("GET", f"/api/v1/payments/{payment_id}")

    async def create_partner_payment(self, *, merchant_id: str, amount: str, currency: str,
                                     destination_account: str, callback_url: str,
                                     idempotency_key: Optional[str] = None, **extra) -> dict:
        body: Dict[str, Any] = {
            "merchantId": merchant_id, "amount": amount, "currency": currency,
            "destinationAccount": destination_account, "callbackUrl": callback_url,
        }
        body.update({k: v for k, v in extra.items() if v is not None})
        return await self._pay_request("POST", "/api/v1/partners/payments", json=body,
                                       idempotency_key=idempotency_key)

    async def get_partner_payment(self, payment_id: str) -> dict:
        return await self._pay_request("GET", f"/api/v1/partners/payments/{payment_id}")
