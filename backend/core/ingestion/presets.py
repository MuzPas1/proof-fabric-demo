"""Inbound integration **provider presets** (configuration-only).

Each preset is a recommended, vendor-spec-derived DEFAULT configuration for a
well-known webhook provider. Presets ONLY pre-fill the existing, fully generic
inbound configuration (auth provider, signature scheme/header/encoding,
timestamp + replay handling). They do NOT add code paths to the core ingestion
framework or the Proof Artifact pipeline, and every value remains reviewable and
overridable by an administrator before saving.

Extensibility: add a new provider by appending a ``ProviderPreset`` below — no
core change is required, because a preset is just a bundle of the same config
keys the framework already understands (see ``core/ingestion/auth_providers.py``
and ``models/ingestion.py``).

Security: presets contain ONLY non-secret configuration. Provider signing
secrets are never embedded here — vendors that sign with their own key are
flagged ``requires_secret`` so the operator supplies it (stored redacted).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    label: str
    category: str                       # payments | source-control | messaging | issue-tracking | generic
    description: str
    auth_provider: str
    auth_config: Dict[str, str] = field(default_factory=dict)
    adapter: str = "generic"            # normalization adapter (generic | jira | ...)
    requires_secret: bool = False       # vendor signs with ITS own key (operator supplies)
    secret_label: Optional[str] = None
    secret_hint: Optional[str] = None
    require_timestamp: bool = False
    timestamp_tolerance_seconds: int = 300
    replay_protection: bool = False
    docs_url: Optional[str] = None
    notes: Optional[str] = None
    # Generic inbound-auth policy this provider supports (declared, not hard-coded).
    supported_auth_methods: List[str] = field(default_factory=list)

    def to_public(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Registry — recommended defaults derived from each vendor's official webhook
# signature specification. All values are overridable in the Admin Portal.
# ---------------------------------------------------------------------------
_PRESETS: List[ProviderPreset] = [
    ProviderPreset(
        id="generic",
        label="Generic (PFP-signed)",
        category="generic",
        description="PFP mints an HMAC-SHA256 signing secret. The sender signs the raw "
                    "body and sends it in the X-PFP-Signature header (hex).",
        auth_provider="hmac_sha256",
        auth_config={},
        requires_secret=False,
        require_timestamp=False,
        replay_protection=False,
        notes="Default for systems that can adopt PFP's own signing scheme.",
    ),
    ProviderPreset(
        id="cashfree",
        label="Cashfree Payments",
        category="payments",
        description="Base64(HMAC-SHA256('{timestamp}.{rawBody}', merchantSecret)) sent in "
                    "x-webhook-signature; epoch-milliseconds timestamp in x-webhook-timestamp.",
        auth_provider="hmac_sha256",
        auth_config={
            "signature_scheme": "cashfree",
            "signature_header": "x-webhook-signature",
            "signature_encoding": "base64",
            "timestamp_header": "x-webhook-timestamp",
        },
        requires_secret=True,
        secret_label="Cashfree PG secret key",
        secret_hint="Payments → Developers → Webhooks (secret key)",
        require_timestamp=True,
        timestamp_tolerance_seconds=300,
        replay_protection=True,
        docs_url="https://www.cashfree.com/docs/payments/online/webhooks/signature-verification",
    ),
    ProviderPreset(
        id="stripe",
        label="Stripe",
        category="payments",
        description="Hex HMAC-SHA256 over '{t}.{rawBody}'; the Stripe-Signature header carries "
                    "t (timestamp) and v1 (signature).",
        auth_provider="hmac_sha256",
        auth_config={
            "signature_scheme": "stripe",
            "signature_header": "stripe-signature",
            "signature_encoding": "hex",
        },
        requires_secret=True,
        secret_label="Stripe webhook signing secret (whsec_…)",
        secret_hint="Developers → Webhooks → Signing secret",
        require_timestamp=True,
        timestamp_tolerance_seconds=300,
        replay_protection=True,
        docs_url="https://stripe.com/docs/webhooks/signatures",
    ),
    ProviderPreset(
        id="razorpay",
        label="Razorpay",
        category="payments",
        description="Hex HMAC-SHA256 over the raw request body, sent in the "
                    "X-Razorpay-Signature header.",
        auth_provider="hmac_sha256",
        auth_config={
            "signature_scheme": "plain",
            "signature_header": "x-razorpay-signature",
            "signature_encoding": "hex",
        },
        requires_secret=True,
        secret_label="Razorpay webhook secret",
        secret_hint="Settings → Webhooks → Secret",
        require_timestamp=False,
        replay_protection=True,
        docs_url="https://razorpay.com/docs/webhooks/validate-test/",
    ),
    ProviderPreset(
        id="github",
        label="GitHub",
        category="source-control",
        description="Hex HMAC-SHA256 over the raw body with a 'sha256=' prefix, sent in the "
                    "X-Hub-Signature-256 header.",
        auth_provider="hmac_sha256",
        auth_config={
            "signature_scheme": "plain",
            "signature_header": "x-hub-signature-256",
            "signature_prefix": "sha256=",
            "signature_encoding": "hex",
        },
        requires_secret=True,
        secret_label="GitHub webhook secret",
        secret_hint="Repo/Org → Settings → Webhooks → Secret",
        require_timestamp=False,
        replay_protection=False,
        notes="GitHub may legitimately redeliver; keep replay protection off unless deduping.",
        docs_url="https://docs.github.com/webhooks/using-webhooks/validating-webhook-deliveries",
    ),
    ProviderPreset(
        id="slack",
        label="Slack",
        category="messaging",
        description="Hex HMAC-SHA256 over 'v0:{ts}:{rawBody}' with a 'v0=' prefix; timestamp in "
                    "X-Slack-Request-Timestamp, signature in X-Slack-Signature.",
        auth_provider="hmac_sha256",
        auth_config={
            "signature_scheme": "slack",
            "signature_header": "x-slack-signature",
            "timestamp_header": "x-slack-request-timestamp",
            "signature_prefix": "v0=",
            "signature_encoding": "hex",
        },
        requires_secret=True,
        secret_label="Slack signing secret",
        secret_hint="App → Basic Information → Signing Secret",
        require_timestamp=True,
        timestamp_tolerance_seconds=300,
        replay_protection=True,
        docs_url="https://api.slack.com/authentication/verifying-requests-from-slack",
    ),
    ProviderPreset(
        id="docusign",
        label="DocuSign Connect",
        category="agreements",
        description="Base64(HMAC-SHA256(secret, rawBody)) sent in X-DocuSign-Signature-1 "
                    "(one signature per active HMAC key; a match against any key trusts the message).",
        auth_provider="hmac_sha256",
        auth_config={
            "signature_scheme": "docusign",
            "signature_header": "x-docusign-signature-1",
            "signature_encoding": "base64",
        },
        requires_secret=True,
        secret_label="DocuSign Connect HMAC secret key",
        secret_hint="Settings → Connect → HMAC Security (secret key)",
        require_timestamp=False,
        replay_protection=False,
        notes="Verified over the EXACT raw body bytes. DocuSign may redeliver; keep replay "
              "protection off unless deduping. Supports multiple keys (X-DocuSign-Signature-1..N).",
        docs_url="https://developers.docusign.com/platform/webhooks/connect/hmac/",
    ),
    ProviderPreset(
        id="shopify",
        label="Shopify",
        category="e-commerce",
        description="Base64 HMAC-SHA256 over the raw body, sent in the X-Shopify-Hmac-Sha256 header.",
        auth_provider="hmac_sha256",
        auth_config={
            "signature_scheme": "plain",
            "signature_header": "x-shopify-hmac-sha256",
            "signature_encoding": "base64",
        },
        requires_secret=True,
        secret_label="Shopify webhook signing secret",
        secret_hint="Settings → Notifications → Webhooks (signing secret)",
        require_timestamp=False,
        replay_protection=False,
        docs_url="https://shopify.dev/docs/apps/build/webhooks/subscribe/verify-webhooks",
        supported_auth_methods=["hmac_sha256"],
    ),
    ProviderPreset(
        id="jira",
        label="Jira Cloud",
        category="issue-tracking",
        description="Jira Cloud issue lifecycle events (created, updated, assignee/status changes, "
                    "comments, attachments, resolved). Jira Cloud signs every delivery with the "
                    "webhook secret using HMAC-SHA256 over the raw body, sent as 'sha256=<hex>' in "
                    "the X-Hub-Signature header. Sensitive content stays hash-only.",
        auth_provider="hmac_sha256",
        adapter="jira",
        auth_config={
            "signature_scheme": "plain",
            "signature_header": "x-hub-signature",
            "signature_prefix": "sha256=",
            "signature_encoding": "hex",
            "site_url": "",
            "cloud_id": "",
            "project_filter": "",
            "event_filter": "issue_created,issue_updated,assignee_changed,status_changed,"
                            "comment_added,attachment_added,issue_resolved",
        },
        requires_secret=False,       # PFP mints a secret to paste into Jira, OR supply Jira's own
        secret_label="Webhook Secret",
        secret_hint="Paste the secret set on the Jira webhook, or leave blank to have PFP generate one.",
        require_timestamp=False,     # Jira's X-Hub-Signature carries no timestamp
        replay_protection=True,
        notes="In Jira: System → WebHooks (or a REST/Connect webhook) → set a Secret and point the URL "
              "at the inbound URL below. Jira signs with HMAC-SHA256 (X-Hub-Signature: sha256=<hex>) "
              "over the raw body. Leave the secret blank here to have PFP generate one (shown once) to "
              "paste into Jira. Auto-provisioning via Atlassian OAuth 2.0 (3LO) is a future enhancement.",
        docs_url="https://developer.atlassian.com/cloud/jira/software/webhooks/",
        supported_auth_methods=["hmac_sha256", "api_key", "bearer", "oauth2"],
    ),
]

_BY_ID: Dict[str, ProviderPreset] = {p.id: p for p in _PRESETS}


def list_presets() -> List[dict]:
    """Public, non-secret list of provider presets for the Admin Portal."""
    return [p.to_public() for p in _PRESETS]


def get_preset(preset_id: str) -> Optional[ProviderPreset]:
    return _BY_ID.get((preset_id or "").lower())
