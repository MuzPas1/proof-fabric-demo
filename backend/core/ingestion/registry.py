"""Generic Provider Registry — the single source of truth that maps a provider
to its **category** and default **event source**.

This is a pure, config-only module (no secrets, no I/O, no proof-engine coupling).
Presets, the event-descriptor builder, and the verification UI all draw provider
taxonomy from here, so provider metadata lives in exactly ONE place. Onboarding a
new provider is a single entry below — the Proof Engine, verification pipeline
and cryptographic infrastructure never change.

Provider Category taxonomy (extensible):
    Payment · Cross-border Payment · Document · Identity · Source Control ·
    Messaging · E-commerce · Event (generic fallback)

Event Source taxonomy (how an event entered PFP):
    Webhook · OAuth · API · Manual · Scheduled
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple


# Inbound authentication taxonomy — how PFP verifies an event a provider SENDS
# in. The Proof Engine stays authentication-agnostic: the ingestion layer picks
# the verifier from the integration's configured policy (see ``auth_providers``).
INBOUND_AUTH_METHODS: List[str] = [
    "api_key", "hmac_sha256", "hmac_sha1", "bearer", "oauth2", "basic", "mtls", "none",
]


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    category: str
    default_event_source: str
    # Generic inbound-auth policy: each provider DECLARES the inbound
    # authentication methods it supports and its recommended default. This keeps
    # authentication provider-declared (not hard-coded per integration) while the
    # Proof Engine remains completely authentication-agnostic.
    supported_auth_methods: Tuple[str, ...] = ("api_key", "hmac_sha256", "bearer")
    default_auth_method: str = "hmac_sha256"


# Ordered category list (stable for UI / documentation).
CATEGORIES: List[str] = [
    "Payment", "Cross-border Payment", "Document", "Identity",
    "Source Control", "Messaging", "E-commerce", "Issue Tracking", "Event",
]

EVENT_SOURCES: List[str] = ["Webhook", "OAuth", "API", "Manual", "Scheduled"]

_PROVIDERS: List[Provider] = [
    Provider("cashfree", "Cashfree", "Payment", "Webhook", ("hmac_sha256",), "hmac_sha256"),
    Provider("razorpay", "Razorpay", "Payment", "Webhook", ("hmac_sha256",), "hmac_sha256"),
    Provider("stripe", "Stripe", "Payment", "Webhook", ("hmac_sha256",), "hmac_sha256"),
    Provider("tazapay", "Tazapay", "Cross-border Payment", "Webhook", ("hmac_sha256",), "hmac_sha256"),
    Provider("docusign", "DocuSign", "Document", "Webhook", ("hmac_sha256",), "hmac_sha256"),
    Provider("github", "GitHub", "Source Control", "Webhook", ("hmac_sha256",), "hmac_sha256"),
    Provider("slack", "Slack", "Messaging", "Webhook", ("hmac_sha256",), "hmac_sha256"),
    Provider("shopify", "Shopify", "E-commerce", "Webhook", ("hmac_sha256",), "hmac_sha256"),
    Provider("jira", "Jira", "Issue Tracking", "Webhook",
             ("api_key", "hmac_sha256", "bearer", "oauth2"), "api_key"),
    Provider("auth0", "Auth0", "Identity", "OAuth", ("oauth2", "bearer"), "oauth2"),
    Provider("generic", "Generic", "Event", "API", ("hmac_sha256", "api_key", "bearer"), "hmac_sha256"),
]

_BY_ID: Dict[str, Provider] = {p.id: p for p in _PROVIDERS}
_GENERIC = _BY_ID["generic"]


def get_provider(provider_id: Optional[str]) -> Optional[Provider]:
    return _BY_ID.get((provider_id or "").lower())


def resolve(kind: Optional[str] = None, name: Optional[str] = None) -> Provider:
    """Best-effort provider resolution from a signature scheme / provider id
    (``kind``) and/or a human name. Falls back to the generic provider so the
    pipeline is never provider-dependent."""
    if kind:
        hit = _BY_ID.get(kind.strip().lower())
        if hit:
            return hit
    if name:
        nl = name.strip().lower()
        if nl in _BY_ID:
            return _BY_ID[nl]
        for p in _PROVIDERS:
            if p.id == "generic":
                continue
            if p.label.lower() == nl or p.id in nl:
                return p
    return _GENERIC


def list_providers() -> List[dict]:
    return [asdict(p) for p in _PROVIDERS]


def enrich_descriptor(desc: Optional[dict]) -> Optional[dict]:
    """Backward-compatible read-time backfill: older stored descriptors may lack
    ``provider_category`` / ``event_source``. Derive them from the registry
    without mutating the stored document. Never raises."""
    if not isinstance(desc, dict):
        return desc
    d = dict(desc)
    prov = resolve(d.get("provider_kind"), d.get("provider"))
    if not d.get("provider_category"):
        d["provider_category"] = prov.category
    if not d.get("event_source"):
        d["event_source"] = prov.default_event_source
    if "attributes" not in d or not isinstance(d.get("attributes"), dict):
        d["attributes"] = {}
    return d
