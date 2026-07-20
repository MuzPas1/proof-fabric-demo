"""Pluggable inbound authentication / signature verification framework.

Generalized to the major enterprise authentication and webhook verification
patterns, onboarded through **configuration** or lightweight adapters — WITHOUT
any change to the core ingestion or Proof Artifact pipeline:

    none          -> no verification (explicit opt-in; discouraged)
    hmac_sha256    -> HMAC-SHA256 (alias: ``hmac``)  — GitHub/Stripe/Slack style
    hmac_sha1      -> HMAC-SHA1
    api_key        -> opaque token in a configurable header (hash-compared)
    bearer         -> opaque token in ``Authorization: Bearer`` (hash-compared)
    basic          -> HTTP Basic (username + hashed password)
    jwt            -> JWT via HS256 (shared secret) / RS256|ES256 (PEM or JWKS)
    oauth2         -> OAuth 2.0 bearer token via JWKS or RFC 7662 introspection
    mtls           -> mutual-TLS verified at the edge, asserted via forwarded
                      headers (X-Client-Verify + subject/fingerprint allow-list)
    custom         -> a registered callable for proprietary schemes

Cross-cutting controls (timestamp validation, replay protection, idempotency)
are enforced by the ingestion framework using the ``AuthResult`` returned here
(``timestamp`` and ``replay_key``), so they compose with every provider.

Providers are synchronous and side-effect-free except for optional, strictly
time-bounded and cached network calls (JWKS fetch / introspection). The
ingestion service invokes ``authenticate`` in a worker thread so verification
never blocks the event loop.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, Optional, Tuple

# --- knobs for the (optional) outbound verification calls ---
_HTTP_TIMEOUT = 4.0          # seconds — strict; verification must not stall ingest
_JWKS_CACHE_LIFESPAN = 300   # seconds — cached signing keys with fallback
_CB_FAIL_THRESHOLD = 3       # consecutive failures before the circuit opens
_CB_COOLDOWN = 30            # seconds the circuit stays open (fail-fast)
_NEG_CACHE_TTL = 10          # seconds to cache a negative introspection verdict


class _CircuitBreaker:
    """Minimal per-endpoint circuit breaker: after N consecutive failures it
    opens for a cooldown window and short-circuits (fail-fast) so an unavailable
    IdP cannot cause repeated slow calls. Not shared across processes (best-effort)."""

    def __init__(self, threshold: int, cooldown: float):
        self.threshold = threshold
        self.cooldown = cooldown
        self._state: Dict[str, dict] = {}

    def allow(self, key: str) -> bool:
        st = self._state.get(key)
        return not (st and st.get("open_until", 0.0) > time.monotonic())

    def record_success(self, key: str) -> None:
        self._state[key] = {"fails": 0, "open_until": 0.0}

    def record_failure(self, key: str) -> None:
        st = self._state.setdefault(key, {"fails": 0, "open_until": 0.0})
        st["fails"] += 1
        if st["fails"] >= self.threshold:
            st["open_until"] = time.monotonic() + self.cooldown


_INTROSPECTION_BREAKER = _CircuitBreaker(_CB_FAIL_THRESHOLD, _CB_COOLDOWN)
_INTROSPECTION_NEG_CACHE: Dict[str, float] = {}  # token-hash -> expiry (monotonic)


@dataclass
class AuthResult:
    ok: bool
    reason: str = "ok"
    replay_key: Optional[str] = None   # unique per-request token for replay defense
    timestamp: Optional[float] = None  # unix seconds, if the scheme carries one
    principal: Optional[str] = None     # e.g. JWT sub / OAuth client_id


def _ct_eq(a: str, b: str) -> bool:
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


def _sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cfg(integration: dict) -> dict:
    return integration.get("auth_config") or {}


def _to_epoch(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Provider base + implementations
# ---------------------------------------------------------------------------
class InboundAuthProvider:
    name = "base"
    generates_credential = False  # True => PFP mints the shared secret/token

    def verify(self, integration: dict, headers: Dict[str, str], raw_body: bytes) -> AuthResult:
        raise NotImplementedError


class NoneProvider(InboundAuthProvider):
    name = "none"

    def verify(self, integration, headers, raw_body) -> AuthResult:
        return AuthResult(True)


class HmacProvider(InboundAuthProvider):
    """HMAC over the raw body (or a templated signed payload).

    Config (``auth_config``): ``signature_scheme`` (plain|stripe|slack),
    ``signature_header``, ``signature_prefix``, ``signed_payload_format``
    (``{timestamp}``/``{body}`` placeholders), ``timestamp_header``.
    """

    generates_credential = True

    def __init__(self, algorithm: str = "sha256"):
        self.algorithm = algorithm
        self.name = f"hmac_{algorithm}"

    def _digestmod(self):
        return hashlib.sha1 if self.algorithm == "sha1" else hashlib.sha256

    def verify(self, integration, headers, raw_body) -> AuthResult:
        # Prefer an externally-provided signing secret (e.g. a Cashfree/Stripe
        # merchant key defined in the provider's own dashboard) over a
        # PFP-minted one. Generic PFP HMAC integrations only set ``hmac_secret``,
        # so their behaviour is unchanged.
        secret = integration.get("external_secret") or integration.get("hmac_secret")
        secret_src = "external" if integration.get("external_secret") else ("minted" if integration.get("hmac_secret") else "none")
        if not secret:
            return AuthResult(False, "integration missing HMAC secret")
        cfg = _cfg(integration)
        scheme = (cfg.get("signature_scheme") or "plain").lower()
        body = raw_body.decode("utf-8", "replace")
        ts: Optional[float] = None

        default_header = "x-pfp-signature"
        prefix = cfg.get("signature_prefix", "")
        signed = body
        provided = ""
        # Output encoding of the HMAC digest: hex (default) or base64.
        encoding = (cfg.get("signature_encoding")
                    or ("base64" if scheme == "cashfree" else "hex")).lower()

        if scheme == "stripe":
            default_header = "stripe-signature"
            raw_sig = headers.get(cfg.get("signature_header", default_header).lower(), "")
            parts = dict(p.split("=", 1) for p in raw_sig.split(",") if "=" in p)
            t = parts.get("t")
            provided = parts.get("v1", "")
            ts = _to_epoch(t)
            signed = f"{t}.{body}"
        elif scheme == "slack":
            default_header = "x-slack-signature"
            t = headers.get(cfg.get("timestamp_header", "x-slack-request-timestamp").lower())
            ts = _to_epoch(t)
            prefix = prefix or "v0="
            signed = f"v0:{t}:{body}"
            provided = headers.get(cfg.get("signature_header", default_header).lower(), "")
        elif scheme == "cashfree":
            # Cashfree PG webhooks: Base64(HMAC-SHA256(timestamp + rawBody,
            # merchantSecret)). Per Cashfree's official SDK the signed string is
            # the timestamp DIRECTLY concatenated with the raw body — there is NO
            # separator (the "." in the docs pseudo-code is PHP concatenation).
            # Signature in ``x-webhook-signature``; the timestamp is an
            # epoch-milliseconds value in ``x-webhook-timestamp``.
            default_header = "x-webhook-signature"
            t = headers.get(cfg.get("timestamp_header", "x-webhook-timestamp").lower())
            signed = f"{t}{body}"
            provided = headers.get(cfg.get("signature_header", default_header).lower(), "")
            ts = _to_epoch(t)
            if ts is not None and ts > 1e12:  # Cashfree sends epoch milliseconds
                ts /= 1000.0
        else:
            header_name = (cfg.get("signature_header") or integration.get("signature_header") or default_header).lower()
            provided = headers.get(header_name, "")
            ts_header = cfg.get("timestamp_header")
            if ts_header:
                t = headers.get(ts_header.lower())
                ts = _to_epoch(t)
                fmt = cfg.get("signed_payload_format", "{timestamp}.{body}")
                signed = fmt.replace("{timestamp}", str(t)).replace("{body}", body)

        if provided.startswith("sha256=") or provided.startswith("sha1="):
            provided = provided.split("=", 1)[1]
        elif prefix and provided.startswith(prefix):
            provided = provided[len(prefix):]

        digest = hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), self._digestmod())
        expected = (base64.b64encode(digest.digest()).decode("ascii")
                    if encoding == "base64" else digest.hexdigest())
        if provided and _ct_eq(provided.strip(), expected):
            return AuthResult(True, replay_key=expected, timestamp=ts)
        # Non-sensitive diagnostic: which branch/encoding ran, whether a signature
        # header was present, and which secret source was used. No secret or
        # signature material is ever included.
        diag = f"scheme={scheme}, enc={encoding}, header={'present' if provided else 'missing'}, secret={secret_src}"
        return AuthResult(False, f"invalid {self.name} signature [{diag}]")


class ApiKeyProvider(InboundAuthProvider):
    name = "api_key"
    generates_credential = True

    def verify(self, integration, headers, raw_body) -> AuthResult:
        header_name = (_cfg(integration).get("token_header") or integration.get("token_header") or "x-integration-key").lower()
        provided = headers.get(header_name, "")
        if provided and _ct_eq(_sha256_hex(provided.strip()), integration.get("token_hash", "")):
            return AuthResult(True)
        return AuthResult(False, "invalid or missing API key")


class BearerProvider(InboundAuthProvider):
    name = "bearer"
    generates_credential = True

    def verify(self, integration, headers, raw_body) -> AuthResult:
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            if token and _ct_eq(_sha256_hex(token), integration.get("token_hash", "")):
                return AuthResult(True)
        return AuthResult(False, "invalid or missing bearer token")


class BasicProvider(InboundAuthProvider):
    """HTTP Basic. Username from ``auth_config.basic_username``; password hashed."""

    name = "basic"
    generates_credential = True

    def verify(self, integration, headers, raw_body) -> AuthResult:
        auth = headers.get("authorization", "")
        if not auth.lower().startswith("basic "):
            return AuthResult(False, "missing basic credentials")
        try:
            decoded = base64.b64decode(auth[6:].strip()).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            return AuthResult(False, "malformed basic credentials")
        expected_user = _cfg(integration).get("basic_username", "")
        user_ok = _ct_eq(username, expected_user)
        pass_ok = _ct_eq(_sha256_hex(password), integration.get("basic_password_hash", ""))
        if user_ok and pass_ok:
            return AuthResult(True, principal=username)
        return AuthResult(False, "invalid basic credentials")


@lru_cache(maxsize=16)
def _jwks_client(url: str):
    import jwt
    return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=_JWKS_CACHE_LIFESPAN)


def _extract_bearer(headers: Dict[str, str]) -> Optional[str]:
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


class JwtProvider(InboundAuthProvider):
    """Verify inbound JWTs. Never trusts the token's ``alg``; algorithms are
    fixed by config. Supports HS256 (shared secret), RS256/ES256 via static PEM
    or a cached remote JWKS URL. Validates exp/iss/aud with leeway."""

    name = "jwt"

    def _decode(self, token: str, integration: dict):
        import jwt
        cfg = _cfg(integration)
        issuer = cfg.get("issuer")
        audience = cfg.get("audience")
        leeway = int(cfg.get("leeway", 30))
        secret = integration.get("external_secret")
        pem = cfg.get("public_key")
        jwks_url = cfg.get("jwks_url")
        options = {"require": ["exp"]}
        common = dict(issuer=issuer, audience=audience, leeway=leeway, options=options)
        if secret and not (pem or jwks_url):
            algs = cfg.get("jwt_algorithms") or ["HS256"]
            return jwt.decode(token, secret, algorithms=algs, **common)
        if pem:
            algs = cfg.get("jwt_algorithms") or ["RS256", "ES256"]
            return jwt.decode(token, pem, algorithms=algs, **common)
        if jwks_url:
            algs = cfg.get("jwt_algorithms") or ["RS256", "ES256"]
            key = _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
            return jwt.decode(token, key, algorithms=algs, **common)
        raise ValueError("no JWT verification material configured (external_secret / public_key / jwks_url)")

    def verify(self, integration, headers, raw_body) -> AuthResult:
        token = _extract_bearer(headers)
        if not token:
            return AuthResult(False, "missing bearer JWT")
        try:
            claims = self._decode(token, integration)
        except Exception as e:  # invalid signature / expired / bad claim / config
            return AuthResult(False, f"JWT rejected: {type(e).__name__}")
        return AuthResult(True, replay_key=claims.get("jti"), timestamp=_to_epoch(claims.get("iat")),
                          principal=claims.get("sub"))


class OAuth2Provider(InboundAuthProvider):
    """OAuth 2.0 inbound access-token validation. ``auth_config.oauth_mode`` =
    ``jwks`` (local RS256/ES256 via JWKS) or ``introspection`` (RFC 7662)."""

    name = "oauth2"

    def verify(self, integration, headers, raw_body) -> AuthResult:
        token = _extract_bearer(headers)
        if not token:
            return AuthResult(False, "missing bearer access token")
        cfg = _cfg(integration)
        mode = (cfg.get("oauth_mode") or "jwks").lower()
        if mode == "introspection":
            return self._introspect(token, integration, cfg)
        return self._jwks(token, integration, cfg)

    def _check_scopes(self, cfg, scope_str) -> bool:
        required = set(filter(None, str(cfg.get("required_scopes", "")).split()))
        scopes = set(str(scope_str or "").split())
        return required.issubset(scopes)

    def _jwks(self, token, integration, cfg) -> AuthResult:
        import jwt
        jwks_url = cfg.get("jwks_url")
        if not jwks_url:
            return AuthResult(False, "oauth2 jwks_url not configured")
        try:
            key = _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=cfg.get("jwt_algorithms") or ["RS256", "ES256"],
                                issuer=cfg.get("issuer"), audience=cfg.get("audience"),
                                leeway=int(cfg.get("leeway", 30)), options={"require": ["exp"]})
        except Exception as e:
            return AuthResult(False, f"OAuth2 token rejected: {type(e).__name__}")
        if not self._check_scopes(cfg, claims.get("scope") or claims.get("scp")):
            return AuthResult(False, "OAuth2 missing required scope")
        return AuthResult(True, replay_key=claims.get("jti"), principal=claims.get("sub") or claims.get("client_id"))

    def _introspect(self, token, integration, cfg) -> AuthResult:
        import httpx
        url = cfg.get("introspection_url")
        client_id = cfg.get("oauth_client_id")
        client_secret = integration.get("external_secret")
        if not (url and client_id and client_secret):
            return AuthResult(False, "oauth2 introspection not fully configured")

        # Negative cache: short-circuit repeated calls for a known-bad token.
        token_key = _sha256_hex(f"{url}|{token}")
        exp = _INTROSPECTION_NEG_CACHE.get(token_key)
        if exp and exp > time.monotonic():
            return AuthResult(False, "inactive token (cached)")

        # Circuit breaker: fail fast when the IdP is repeatedly unavailable.
        if not _INTROSPECTION_BREAKER.allow(url):
            return AuthResult(False, "introspection endpoint unavailable (circuit open)")

        try:
            resp = httpx.post(url, data={"token": token, "token_type_hint": "access_token"},
                              auth=(client_id, client_secret), headers={"Accept": "application/json"},
                              timeout=_HTTP_TIMEOUT)
            data = resp.json()
        except Exception as e:
            _INTROSPECTION_BREAKER.record_failure(url)
            return AuthResult(False, f"introspection failed: {type(e).__name__}")
        _INTROSPECTION_BREAKER.record_success(url)  # reachable IdP resets the breaker

        if not data.get("active"):
            _INTROSPECTION_NEG_CACHE[token_key] = time.monotonic() + _NEG_CACHE_TTL
            return AuthResult(False, "inactive token")
        audience = cfg.get("audience")
        if audience:
            aud = data.get("aud")
            auds = aud if isinstance(aud, list) else [aud]
            if audience not in auds:
                return AuthResult(False, "bad audience")
        if not self._check_scopes(cfg, data.get("scope")):
            return AuthResult(False, "OAuth2 missing required scope")
        return AuthResult(True, replay_key=data.get("jti"), principal=data.get("client_id") or data.get("sub"))


class MtlsProvider(InboundAuthProvider):
    """Application-layer mTLS assertion via ingress-forwarded client-cert
    headers. Trust these headers ONLY when the edge/ingress terminates TLS and
    strips any externally-supplied copies. Config: ``mtls_verify_header``,
    ``mtls_success_value``, ``mtls_fingerprint_header``, ``allowed_fingerprints``,
    ``mtls_subject_header``, ``allowed_subjects``."""

    name = "mtls"

    def verify(self, integration, headers, raw_body) -> AuthResult:
        cfg = _cfg(integration)
        verify_header = (cfg.get("mtls_verify_header") or "x-client-verify").lower()
        success = (cfg.get("mtls_success_value") or "SUCCESS").upper()
        if (headers.get(verify_header, "") or "").upper() != success:
            return AuthResult(False, "mTLS not verified by edge")
        subject_header = (cfg.get("mtls_subject_header") or "x-client-cert-subject").lower()
        allowed_fps = [f.strip() for f in (cfg.get("allowed_fingerprints") or []) if f.strip()]
        if allowed_fps:
            fp = headers.get((cfg.get("mtls_fingerprint_header") or "x-client-cert-fingerprint").lower(), "")
            if fp not in allowed_fps:
                return AuthResult(False, "untrusted client certificate fingerprint")
        allowed_subjects = [s.strip() for s in (cfg.get("allowed_subjects") or []) if s.strip()]
        if allowed_subjects:
            subj = headers.get(subject_header, "")
            if subj not in allowed_subjects:
                return AuthResult(False, "untrusted client certificate subject")
        return AuthResult(True, principal=headers.get(subject_header))


# --- custom provider registry (proprietary schemes; lightweight adapters) ---
_CUSTOM_HANDLERS: Dict[str, Callable[[dict, Dict[str, str], bytes], AuthResult]] = {}


def register_custom_provider(name: str, handler: Callable[[dict, Dict[str, str], bytes], AuthResult]) -> None:
    """Extension hook for proprietary verification (no core change required)."""
    _CUSTOM_HANDLERS[name] = handler


class CustomProvider(InboundAuthProvider):
    name = "custom"

    def verify(self, integration, headers, raw_body) -> AuthResult:
        handler_name = _cfg(integration).get("custom_handler")
        handler = _CUSTOM_HANDLERS.get(handler_name)
        if handler is None:
            return AuthResult(False, f"custom handler not registered: {handler_name}")
        result = handler(integration, headers, raw_body)
        if isinstance(result, AuthResult):
            return result
        return AuthResult(bool(result), "ok" if result else "custom verification failed")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_PROVIDERS: Dict[str, InboundAuthProvider] = {
    "none": NoneProvider(),
    "hmac": HmacProvider("sha256"),         # backward-compatible alias
    "hmac_sha256": HmacProvider("sha256"),
    "hmac_sha1": HmacProvider("sha1"),
    "api_key": ApiKeyProvider(),
    "bearer": BearerProvider(),
    "basic": BasicProvider(),
    "jwt": JwtProvider(),
    "oauth2": OAuth2Provider(),
    "mtls": MtlsProvider(),
    "custom": CustomProvider(),
}

# Providers for which PFP mints a shared secret/token at create/rotate time.
CREDENTIAL_PROVIDERS = {name for name, p in _PROVIDERS.items() if p.generates_credential}


def get_provider(name: str) -> InboundAuthProvider:
    return _PROVIDERS.get((name or "hmac").lower(), _PROVIDERS["none"])


def authenticate(integration: dict, headers: Dict[str, str], raw_body: bytes) -> AuthResult:
    """Framework entry point. ``headers`` keys MUST be lowercased by the caller."""
    provider = get_provider(integration.get("auth_provider") or "hmac")
    try:
        return provider.verify(integration, headers, raw_body)
    except Exception as e:  # never leak internals; fail closed
        return AuthResult(False, f"verification error: {type(e).__name__}")


def verify(integration: dict, headers: Dict[str, str], raw_body: bytes) -> Tuple[bool, str]:
    """Backward-compatible boolean/reason wrapper."""
    result = authenticate(integration, headers, raw_body)
    return result.ok, result.reason
