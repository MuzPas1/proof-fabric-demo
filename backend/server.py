"""
Proof Fabric Protocol (PFP) - Main Server
Enterprise-grade API for cryptographically verifiable Proof Artifacts —
general-purpose proof infrastructure (data plane API stores artifacts under the
historical `fea` / `fea_id` contract names for backward compatibility).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.config import settings
from core.ratelimit import limiter
from core.security import SecurityHeadersMiddleware, RequestSizeLimitMiddleware
from core.observability import (
    configure_logging, MetricsMiddleware, metrics_response,
)

configure_logging()
logger = logging.getLogger("pfp.server")

# MongoDB connection — single managed database.
# Demo data is logically isolated via dedicated collections (demo_proofs,
# demo_key_registry) within the same database. Using a separate physical
# database breaks in managed deployments where only DB_NAME is authorized.
client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.DB_NAME]
demo_db = db

app = FastAPI(
    title="Proof Fabric Protocol (PFP)",
    description="Cryptographically verifiable Proof Artifacts — general-purpose proof infrastructure & enterprise control plane.",
    version="2.0.0",
    # Interactive API docs are GATED. A curated PUBLIC spec is served at
    # /api/openapi-public.json (and powers the public Swagger/ReDoc); the FULL
    # spec at /api/openapi.json requires Enterprise Evaluation / staff access.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware (order matters: outermost first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(MetricsMiddleware)

# Strict CORS: explicit origins (no "*" with credentials). "*" allowed only if
# credentials are not required.
cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
allow_credentials = "*" not in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP-only session cookie (Auth0 identity sessions + OAuth state). Signed with a
# dedicated secret; never exposes tokens/claims to the browser.
app.add_middleware(
    SessionMiddleware,
    secret_key=(settings.AUTH0_SECRET or settings.JWT_SECRET or "pfp-session-key"),
    session_cookie="pfp_session",
    https_only=True,
    same_site="lax",
    max_age=60 * 60 * 8,
)

from routes.fea_routes import router as fea_router
from routes.public_routes import router as public_router
from routes.demo_routes import router as demo_router
from routes.auth_routes import router as auth_router
from routes.admin_routes import router as admin_router
from routes.webhook_routes import router as webhook_router
from routes.resources_routes import router as resources_router
from routes.evaluation_routes import router as evaluation_router
from routes.ingestion_routes import router as ingestion_router
from routes.ingestion_admin_routes import router as ingestion_admin_router
from routes.auth0_routes import router as auth0_router
from routes.tarabut_routes import router as tarabut_router

for r in (fea_router, public_router, demo_router, auth_router, admin_router,
          webhook_router, resources_router, evaluation_router,
          ingestion_router, ingestion_admin_router, auth0_router,
          tarabut_router):
    app.include_router(r, prefix="/api")

# Developer assets (docs, OpenAPI, Postman, SDKs) are served through the
# resources router with SERVER-SIDE tiered access control (PUBLIC / ENTERPRISE /
# INTERNAL) — see routes/resources_routes.py + core/doc_classification.py. The
# previous open StaticFiles mounts were removed so internal docs can no longer be
# fetched by direct URL.

# --------------------------------------------------------------------------
# OpenAPI / Swagger / ReDoc — gated full spec + curated public spec
# --------------------------------------------------------------------------
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi import Depends
from typing import Optional as _Optional
from auth.dependencies import get_optional_user, has_enterprise_access
from models.auth_models import User as _User

# Paths exposed in the PUBLIC (curated) spec — verification + demo + value only.
# Issuance, batch, listing, control plane, federated keys & BYOS are NOT public.
_PUBLIC_SPEC_EXACT = {
    "/api/", "/api/health", "/api/config", "/api/developer",
    "/api/fea/verify", "/api/evaluation/request",
}
_PUBLIC_SPEC_PREFIXES = ("/api/public/", "/api/demo/")


def _full_openapi() -> dict:
    from fastapi.openapi.utils import get_openapi
    if not app.openapi_schema:
        app.openapi_schema = get_openapi(
            title=app.title, version=app.version, description=app.description, routes=app.routes,
        )
    return app.openapi_schema


def _is_public_path(path: str) -> bool:
    if "/admin/" in path:
        return False
    if path in _PUBLIC_SPEC_EXACT:
        return True
    return any(path.startswith(p) for p in _PUBLIC_SPEC_PREFIXES)


def _public_openapi() -> dict:
    full = _full_openapi()
    paths = {p: item for p, item in full.get("paths", {}).items() if _is_public_path(p)}
    return {
        "openapi": full.get("openapi", "3.1.0"),
        "info": {
            "title": "Proof Fabric Protocol — Public API",
            "version": app.version,
            "description": "Public verification & demo surface. Full API (issuance, "
                           "control plane, federated keys, BYOS) is available via the "
                           "PFP Enterprise Evaluation Center.",
        },
        "paths": paths,
        "components": full.get("components", {}),
    }


@app.get("/api/openapi-public.json", include_in_schema=False)
async def openapi_public():
    return _public_openapi()


@app.get("/api/openapi.json", include_in_schema=False)
async def openapi_full(user: _Optional[_User] = Depends(get_optional_user)):
    if not has_enterprise_access(user):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={
            "error": "enterprise_access_required",
            "message": "The full OpenAPI specification is available via the PFP Enterprise Evaluation Center.",
            "public_spec": "/api/openapi-public.json",
            "request_access": "/evaluation",
        })
    return _full_openapi()


@app.get("/api/docs", include_in_schema=False)
async def public_swagger():
    return get_swagger_ui_html(openapi_url="/api/openapi-public.json", title="PFP Public API — Swagger")


@app.get("/api/redoc", include_in_schema=False)
async def public_redoc():
    return get_redoc_html(openapi_url="/api/openapi-public.json", title="PFP Public API — ReDoc")


@app.on_event("startup")
async def startup_event():
    from services.key_service import initialize_key_registry
    from services import api_key_service, user_service, tenant_service, webhook_service
    from services.artifact_service import ensure_demo_signing_key

    # Production key registry (main DB)
    try:
        await initialize_key_registry(db)
        logger.info("Production key registry initialized")
    except Exception as e:
        logger.warning(f"Key registry init warning: {e}")

    # Demo signing key in the ISOLATED demo DB registry
    try:
        demo_kid = await ensure_demo_signing_key(demo_db)
        logger.info(f"Demo signing key active (isolated): kid={demo_kid}")
    except Exception as e:
        logger.warning(f"Demo signing key init warning: {e}")

    # Control-plane indexes + seeding
    await user_service.ensure_indexes(db)
    await api_key_service.ensure_indexes(db)
    await tenant_service.ensure_indexes(db)
    await webhook_service.ensure_indexes(db)
    await db.audit_log.create_index("created_at")
    try:
        from services import federated_key_service
        await federated_key_service.ensure_indexes(db)
        from services import signer_service
        await signer_service.ensure_indexes(db)
        from services import evaluation_service
        await evaluation_service.ensure_indexes(db)
    except Exception as e:
        logger.warning(f"Federated key index warning: {e}")

    # Inbound event ingestion framework (additive; independent module)
    try:
        from services import ingestion_service
        await ingestion_service.ensure_indexes(db)
    except Exception as e:
        logger.warning(f"Ingestion index warning: {e}")

    await tenant_service.ensure_tenant(db, settings.DEFAULT_TENANT_ID, "Default Tenant")
    await user_service.seed_admin(db, settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD, settings.DEFAULT_TENANT_ID)

    # External Reviewer (Read Only) evaluation account — separate from super-admin.
    # View-only role + a read-only API key (fea:read, webhooks:read) for data-plane views.
    if settings.EVAL_EMAIL and settings.EVAL_PASSWORD:
        await user_service.seed_user(
            db, settings.EVAL_EMAIL, settings.EVAL_PASSWORD,
            "external_reviewer", settings.DEFAULT_TENANT_ID,
        )
        if settings.EVAL_READONLY_API_KEY:
            await api_key_service.ensure_static_key(
                db, settings.EVAL_READONLY_API_KEY, "external-reviewer-readonly",
                settings.DEFAULT_TENANT_ID, ["fea:read", "webhooks:read"], "system",
            )
        logger.info("External reviewer (read-only) account seeded")

    # Sandbox API key (dev only) — persisted in DB so all workers share it
    if settings.SANDBOX_API_KEY and not settings.is_production:
        await api_key_service.ensure_sandbox_key(db, settings.SANDBOX_API_KEY, settings.DEFAULT_TENANT_ID)
        logger.info("Sandbox API key seeded (development)")

    # FEA indexes + replay protection (scoped per tenant)
    await db.feas.create_index("fea_id", unique=True)
    await db.feas.create_index([("tenant_id", 1), ("idempotency_key", 1)])
    await db.feas.create_index("tenant_id")
    try:
        await db.feas.create_index(
            [
                ("tenant_id", 1),
                ("fea_payload.transaction_summary.transaction_id", 1),
                ("fea_payload.transaction_summary.timestamp", 1),
            ],
            unique=True,
            name="replay_protection_tenant",
        )
    except Exception as e:
        logger.warning(f"Replay protection index warning: {e}")

    logger.info("PFP startup complete")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


@app.get("/api/")
@limiter.limit("100/minute")
async def root(request: Request):
    return {
        "name": "Proof Fabric Protocol (PFP)",
        "version": "2.0.0",
        "status": "operational",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/health")
async def health_check():
    """Deep health check: validates DB, key registry, and signing service."""
    checks = {"database": False, "key_registry": False, "signing_service": False, "demo_db": False}
    try:
        await client.admin.command("ping")
        checks["database"] = True
    except Exception:
        pass
    try:
        count = await db.key_registry.count_documents({})
        checks["key_registry"] = count >= 0
    except Exception:
        pass
    try:
        from crypto.signing import get_public_key_id
        checks["signing_service"] = bool(get_public_key_id())
    except Exception:
        pass
    try:
        await demo_db.command("ping")
        checks["demo_db"] = True
    except Exception:
        pass
    healthy = all(checks.values())
    try:
        from core.kms import kms_status
        signing = kms_status()
    except Exception:
        signing = {"provider": settings.KMS_PROVIDER, "ready": False}
    return {"status": "healthy" if healthy else "degraded", "checks": checks, "signing": signing}


@app.get("/api/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return metrics_response()


@app.get("/api/config")
async def get_config():
    """Public configuration.

    The sandbox API key is exposed ONLY outside production (dev/sandbox) for the
    developer console. In production, no key is returned — keys are provisioned
    via the admin control plane (POST /api/admin/api-keys/create).
    """
    config = {
        "issuer_id": settings.ISSUER_ID,
        "environment": settings.ENVIRONMENT,
        "endpoints": {
            "generate_fea": "/api/fea/generate",
            "verify_fea": "/api/fea/verify",
            "batch_fea": "/api/fea/batch",
            "public_verify": "/api/public/verify/{fea_id}",
            "key_registry": "/api/public/keys",
            "admin_login": "/api/auth/login",
        },
    }
    if settings.expose_sandbox_key:
        config["test_api_key"] = settings.SANDBOX_API_KEY
        config["sandbox_notice"] = "Sandbox key — development only. Not present in production."
    return config


@app.get("/api/developer")
async def developer_resources(request: Request):
    """Developer resource index — Swagger, OpenAPI, Postman, docs, and SDKs.

    URLs are built from the request's own base URL, so this works identically on
    any attached domain (demo.pfprotocol.com or api.pfprotocol.com).
    """
    base = str(request.base_url).rstrip("/")
    return {
        "name": "Proof Fabric Protocol — Developer Resources",
        "version": "2.0.0",
        "api_base": f"{base}/api",
        "access_model": {
            "tiers": ["public", "enterprise", "internal"],
            "note": "Full API specs, SDKs, integration & architecture materials are "
                    "available through the Enterprise Evaluation Center.",
            "request_access": f"{base}/evaluation",
        },
        "public": {
            "swagger_ui": f"{base}/api/docs",
            "redoc": f"{base}/api/redoc",
            "openapi_public_json": f"{base}/api/openapi-public.json",
            "quickstart": f"{base}/api/resources/docs/QUICKSTART.md",
            "use_case": f"{base}/api/resources/docs/USE_CASE_CHANGE_RELEASE.md",
            "release_notes": f"{base}/api/resources/docs/RELEASE_NOTES.md",
            "public_verify": f"{base}/api/public/verify/{{fea_id}}",
            "public_keys": f"{base}/api/public/keys",
        },
        "enterprise": {
            "note": "Requires Enterprise Evaluation access (Authorization: Bearer <evaluator/staff token>).",
            "openapi_full_json": f"{base}/api/openapi.json",
            "openapi_yaml": f"{base}/api/resources/docs/openapi.yaml",
            "postman_collection": f"{base}/api/resources/docs/postman_collection.json",
            "developer_guide": f"{base}/api/resources/docs/DEVELOPER_GUIDE.md",
            "integration_guide": f"{base}/api/resources/docs/INTEGRATION_GUIDE.md",
            "api_reference": f"{base}/api/resources/docs/API_REFERENCE.md",
            "architecture": f"{base}/api/resources/docs/ARCHITECTURE.md",
            "sdks": {
                "python": f"{base}/api/resources/sdks/python/",
                "javascript": f"{base}/api/resources/sdks/javascript/",
                "java": f"{base}/api/resources/sdks/java/",
                "dotnet": f"{base}/api/resources/sdks/dotnet/",
            },
        },
        "auth": {
            "data_plane": "X-API-Key: <key>  (provisioned via POST /api/admin/api-keys/create)",
            "control_plane": "Authorization: Bearer <jwt>  (POST /api/auth/login)",
        },
        "signing": _signing_capability(),
    }


def _signing_capability() -> dict:
    """Non-secret signing/KMS capability profile for the developer portal.

    Distinguishes what is ACTIVE today from what the architecture is READY for
    and what is PLANNED — so the portal can present accurate trust messaging
    without overstating capabilities.
    """
    from core.kms import kms_status
    from crypto import suites
    st = kms_status()
    available_suites = st.get("signature_suites", {}).get("production", ["Ed25519"])
    return {
        "algorithm": st.get("algorithm", "Ed25519"),
        "default_suite": settings.DEFAULT_SIGNATURE_SUITE,
        "active_provider": st.get("provider"),
        "active_mode": st.get("mode"),
        "ready": st.get("ready"),
        "supported_providers": st.get("supported_providers", []),
        "signature_suites": {
            "supported": list(suites.SUPPORTED_ALGORITHMS),
            "available": available_suites,
            "default": settings.DEFAULT_SIGNATURE_SUITE,
        },
        "crypto_agility": {
            "enabled": settings.ENABLE_CRYPTO_SUITES,
            "suites": ["Ed25519 (EdDSA/Curve25519)", "ES256 (ECDSA/secp256r1)", "ES256K (ECDSA/secp256k1)"],
            "encoding": "Ed25519 raw 64B; ECDSA raw r||s 64B, low-S enforced",
            "algorithm_binding": "verify-suite bound to registry key algorithm (anti-confusion)",
        },
        "federated_keys": {
            "enabled": settings.ENABLE_FEDERATED_KEYS,
            "formats": ["raw", "jwk", "spki-pem"],
            "controls": ["proof-of-possession", "validity windows", "tenant ownership", "revocation/retirement"],
        },
        "byos": {
            "enabled": settings.ENABLE_BYOS,
            "signers": ["local KMS", "remote signer (HTTP)", "cloud KMS (config-gated)"],
            "verification": "independent of signer availability (public key only)",
        },
        "current_capability": [
            "Deterministic canonicalization (PFP-JCS) + signing",
            "Crypto agility: Ed25519 (default), ES256, ES256K — selectable per request/tenant",
            "Independent, offline verification with the public key (any suite)",
            "Federated key registry: customer/partner keys (raw/JWK/PEM) with proof-of-possession",
            "Bring-Your-Own-Signing: local / remote / cloud-KMS signers per tenant",
            "Multi-tenant key isolation; persistent key registry & rotation",
        ],
        "architecture_readiness": [
            "Cloud KMS ready — AWS Secrets Manager / GCP Secret Manager / Azure Key Vault (config-only switch)",
            "Native HSM / cloud-KMS signing path (private key never leaves the boundary) — config-gated",
        ],
        "planned_enhancements": [
            "Live cloud-KMS native signing enablement (provider credentials)",
            "External time anchoring (RFC-3161 / transparency log)",
        ],
    }
