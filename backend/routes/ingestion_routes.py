"""Public inbound event ingestion endpoint (no admin auth).

External systems POST business events here. The endpoint itself requires NO PFP
admin/JWT auth — it is protected by the integration's configured provider
authentication / signature verification (HMAC, API key, or bearer). Only the
management surface (/api/admin/integrations) is restricted to PFP administrators.
"""
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from core.config import settings
from core.ratelimit import limiter
from services import ingestion_service, audit_service

router = APIRouter(prefix="/ingest", tags=["Inbound Ingestion"])


@router.post("/{slug}")
@limiter.limit("300/minute")
async def ingest_event(request: Request, slug: str):
    """Submit a verifiable business event for Proof Artifact generation.

    Auth is per-integration (provider signature/token), NOT PFP admin auth.
    Feature-gated by ENABLE_EVENT_INGESTION.
    """
    if not settings.ENABLE_EVENT_INGESTION:
        return JSONResponse(status_code=404, content={"detail": "Event ingestion is not enabled"})

    from server import db as database
    raw_body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    try:
        result = await ingestion_service.process_inbound(database, slug, raw_body, headers)
    except ingestion_service.IngestionError as e:
        return JSONResponse(status_code=e.status_code, content={"detail": str(e)})

    try:
        await audit_service.record_audit(
            database, "ingest.event_accepted", actor=f"integration:{slug}",
            tenant_id="", target=result.get("fea_id"),
            metadata={"integration": slug, "event_id": result.get("event_id")},
        )
    except Exception:
        pass
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=result)
