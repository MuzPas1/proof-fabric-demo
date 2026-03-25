"""
Proof Fabric Protocol (PFP) - Main Server
Production-grade API for cryptographically verifiable Financial Evidence Artifacts (FEAs).
"""
import sys
from pathlib import Path

# Add backend to path for imports
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

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
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

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routes after app creation to avoid circular imports
from routes.fea_routes import router as fea_router
from routes.public_routes import router as public_router
from routes.auth import generate_test_api_key, get_test_api_key

# Include routers with /api prefix
app.include_router(fea_router, prefix="/api")
app.include_router(public_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    # Generate test API key
    test_key = generate_test_api_key()
    logger.info(f"Test API Key generated: {test_key}")
    
    # Initialize key registry
    from services.key_service import initialize_key_registry
    try:
        initialize_key_registry()
        logger.info("Key registry initialized")
    except Exception as e:
        logger.warning(f"Key registry initialization skipped: {e}")
    
    # Create indexes
    await db.feas.create_index("fea_id", unique=True)
    await db.feas.create_index("idempotency_key")
    logger.info("Database indexes created")


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
