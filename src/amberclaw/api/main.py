import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from amberclaw.api.lifespan import os_lifespan
from amberclaw.api.v1 import router as v1_router

# Configure basic logging for the OS
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title="AmberClaw AI OS",
    description="Enterprise-grade personal AI assistant framework",
    version="2026.0.1",
    lifespan=os_lifespan,
)

# Secure default CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API v1 router
# (We will build out the routes in src/amberclaw/api/v1/router.py next)
app.include_router(v1_router.api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """Basic health check for external load balancers and orchestrators."""
    return {"status": "ok", "system": "AmberClaw AI OS"}
