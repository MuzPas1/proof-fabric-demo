"""
Proof Fabric Protocol (PFP) - Main Server
Production-grade API for cryptographically verifiable Financial Evidence Artifacts (FEAs).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import logging
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="Proof Fabric Protocol (PFP)",
    description="Transform financial transactions into deterministic, cryptographically verifiable Financial Evidence Artifacts",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

from routes.fea_routes import router as fea_router
from routes.public_routes import router as public_router
from routes.demo_routes import router as demo_router
from routes.auth import generate_test_api_key, get_test_api_key

app.include_router(fea_router, prefix="/api")
app.include_router(public_router, prefix="/api")
app.include_router(demo_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    # Generate test API key
    test_key = generate_test_api_key()
    logger.info(f"Test API Key generated: {test_key}")
    
    # Initialize persistent key registry
    from services.key_service import initialize_key_registry
    try:
        await initialize_key_registry(db)
        logger.info("Persistent key registry initialized")
    except Exception as e:
        logger.warning(f"Key registry initialization warning: {e}")

    # Ensure demo artifact signing key is registered
    try:
        from services.artifact_service import ensure_demo_signing_key
        demo_kid = await ensure_demo_signing_key(db)
        logger.info(f"Demo artifact signing key active: kid={demo_kid}")
    except Exception as e:
        logger.warning(f"Demo signing key init warning: {e}")
    
    # Create indexes for FEAs
    await db.feas.create_index("fea_id", unique=True)
    await db.feas.create_index("idempotency_key")
    
    # Create compound index for replay protection (transaction_id + timestamp)
    # Must deduplicate existing data first to avoid index creation failure
    try:
        await db.feas.create_index([
            ("fea_payload.transaction_summary.transaction_id", 1),
            ("fea_payload.transaction_summary.timestamp", 1)
        ], unique=True)
    except Exception as e:
        logger.warning(f"Replay protection index creation failed (likely existing duplicates): {e}")
        # Deduplicate: keep the earliest document per (transaction_id, timestamp)
        pipeline = [
            {"$group": {
                "_id": {
                    "txn_id": "$fea_payload.transaction_summary.transaction_id",
                    "ts": "$fea_payload.transaction_summary.timestamp"
                },
                "keep_id": {"$first": "$_id"},
                "all_ids": {"$push": "$_id"},
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]
        async for group in db.feas.aggregate(pipeline):
            ids_to_remove = [oid for oid in group["all_ids"] if oid != group["keep_id"]]
            if ids_to_remove:
                await db.feas.delete_many({"_id": {"$in": ids_to_remove}})
                logger.info(f"Removed {len(ids_to_remove)} duplicate(s) for txn {group['_id']}")
        
        # Retry index creation after dedup
        await db.feas.create_index([
            ("fea_payload.transaction_summary.transaction_id", 1),
            ("fea_payload.transaction_summary.timestamp", 1)
        ], unique=True)
        logger.info("Replay protection index created after deduplication")
    
    logger.info("Database indexes created (including replay protection)")


@app.on_event("shutdown")
async def shutdown_db_client():
    """Cleanup on shutdown."""
    client.close()


@app.get("/api/")
@limiter.limit("100/minute")
async def root(request: Request):
    """API root - health check."""
    return {
        "name": "Proof Fabric Protocol (PFP)",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/config")
async def get_config():
    """Get public configuration (test API key for dev console)."""
    return {
        "test_api_key": get_test_api_key(),
        "issuer_id": os.environ.get('ISSUER_ID', 'pfp-issuer-001'),
        "endpoints": {
            "generate_fea": "/api/fea/generate",
            "verify_fea": "/api/fea/verify",
            "public_verify": "/api/public/verify/{fea_id}",
            "key_registry": "/api/public/keys"
        }
    }
