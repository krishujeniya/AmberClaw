import logging
import os
import time

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from amberclaw.api.errors import global_exception_handler, http_exception_handler
from amberclaw.api.lifespan import os_lifespan
from amberclaw.api.middleware import (
    APIDeprecationMiddleware,
    IdempotencyMiddleware,
    RateLimiterMiddleware,
    RequestBodyLimitMiddleware,
    RequestTimeoutMiddleware,
)
from amberclaw.api.v1 import router as v1_router
from amberclaw.config.schema import settings
from amberclaw.observability.metrics import get_metrics_payload, record_request_metric

# Configure basic logging for the OS
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

env_name = os.getenv("ENVIRONMENT", settings.gateway.environment).lower()

app = FastAPI(
    title="AmberClaw AI OS",
    description="Enterprise-grade personal AI assistant framework",
    version="2026.0.1",
    lifespan=os_lifespan,
    docs_url="/docs" if env_name != "production" else None,
    redoc_url="/redoc" if env_name != "production" else None,
)

# Exception handlers for standardized error envelopes
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Request abuse control and reliability middlewares
app.add_middleware(RequestTimeoutMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(APIDeprecationMiddleware)
allowed_origins_env = os.getenv("CORS_ORIGINS")
if allowed_origins_env:
    origins_list = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    origins_list = settings.gateway.cors_origins

if env_name == "production" and ("*" in origins_list or not origins_list):
    raise RuntimeError(
        "CRITICAL SECURITY ERROR: Wildcard origins '*' are strictly prohibited in production mode."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none';"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return response


# Include the API v1 router
app.include_router(v1_router.api_router, prefix="/api/v1")


@app.middleware("http")
async def track_prometheus_metrics(request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time
    endpoint = request.url.path
    record_request_metric(request.method, endpoint, response.status_code, duration)
    return response


@app.get("/health")
async def health_check():
    """Basic health check for external load balancers and orchestrators."""
    return {"status": "ok", "system": "AmberClaw AI OS"}


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus exposition metrics endpoint for monitoring scraping."""
    payload, content_type = get_metrics_payload()
    return Response(content=payload, media_type=content_type)
