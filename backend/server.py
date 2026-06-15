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
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
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

from routes.fea_routes import router as fea_router
from routes.public_routes import router as public_router
from routes.demo_routes import router as demo_router
from routes.auth_routes import router as auth_router
from routes.admin_routes import router as admin_router
from routes.webhook_routes import router as webhook_router

for r in (fea_router, public_router, demo_router, auth_router, admin_router, webhook_router):
    app.include_router(r, prefix="/api")

# Developer resources hosted under /api so they are reachable on any attached
# domain (e.g. demo.pfprotocol.com or api.pfprotocol.com) via the /api ingress
# route. Read-only static serving of docs (OpenAPI, Postman, guides) and SDKs.
import os as _os
_DOCS_DIR = _os.path.join(_os.path.dirname(__file__), "..", "docs")
_SDKS_DIR = _os.path.join(_os.path.dirname(__file__), "..", "sdks")
if _os.path.isdir(_DOCS_DIR):
    app.mount("/api/resources/docs", StaticFiles(directory=_DOCS_DIR), name="docs")
if _os.path.isdir(_SDKS_DIR):
    app.mount("/api/resources/sdks", StaticFiles(directory=_SDKS_DIR), name="sdks")


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
        "interactive": {
            "swagger_ui": f"{base}/api/docs",
            "redoc": f"{base}/api/redoc",
            "openapi_json": f"{base}/api/openapi.json",
            "openapi_yaml": f"{base}/api/resources/docs/openapi.yaml",
            "postman_collection": f"{base}/api/resources/docs/postman_collection.json",
        },
        "guides": {
            "quickstart": f"{base}/api/resources/docs/QUICKSTART.md",
            "developer_guide": f"{base}/api/resources/docs/DEVELOPER_GUIDE.md",
            "integration_guide": f"{base}/api/resources/docs/INTEGRATION_GUIDE.md",
            "api_reference": f"{base}/api/resources/docs/API_REFERENCE.md",
            "canonical_endpoints": f"{base}/api/resources/docs/CANONICAL_ENDPOINTS.md",
        },
        "sdks": {
            "python": f"{base}/api/resources/sdks/python/",
            "javascript": f"{base}/api/resources/sdks/javascript/",
            "java": f"{base}/api/resources/sdks/java/",
            "dotnet": f"{base}/api/resources/sdks/dotnet/",
            "readme": f"{base}/api/resources/sdks/README.md",
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
    st = kms_status()
    return {
        "algorithm": st.get("algorithm", "Ed25519"),
        "active_provider": st.get("provider"),
        "active_mode": st.get("mode"),
        "ready": st.get("ready"),
        "supported_providers": st.get("supported_providers", []),
        "current_capability": [
            "Deterministic canonicalization (PFP-JCS) + Ed25519 signing",
            "Independent, offline verification with the public key",
            "Pluggable KMS abstraction (single signing call site)",
            "Multi-tenant key isolation; persistent key registry & rotation",
        ],
        "architecture_readiness": [
            "Cloud KMS ready — AWS Secrets Manager / GCP Secret Manager / Azure Key Vault (config-only switch)",
            "HSM-ready signing architecture (pluggable provider; no API changes)",
        ],
        "planned_enhancements": [
            "Native HSM signing — private key never leaves the HSM/KMS boundary",
            "External time anchoring (RFC-3161 / transparency log)",
        ],
    }
