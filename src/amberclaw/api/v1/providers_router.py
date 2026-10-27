"""API router for LLM provider health check endpoints."""

import os
from fastapi import APIRouter
from pydantic import BaseModel

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

router = APIRouter()


class ProviderHealthStatus(BaseModel):
    provider: str
    status: str  # "healthy", "configured", "unconfigured", "disabled"
    configured: bool
    details: dict[str, str] = {}


class HealthCheckResponse(BaseModel):
    status: str
    engine: str
    providers: list[ProviderHealthStatus]


@router.get("/health", response_model=HealthCheckResponse)
async def check_provider_health() -> HealthCheckResponse:
    """Check health and environment configuration status of LLM providers."""
    provider_checks = [
        (
            "openai",
            "OPENAI_API_KEY" in os.environ and bool(os.getenv("OPENAI_API_KEY")),
            {"default_model": "gpt-4o"},
        ),
        (
            "anthropic",
            "ANTHROPIC_API_KEY" in os.environ and bool(os.getenv("ANTHROPIC_API_KEY")),
            {"default_model": "claude-3-5-sonnet-20241022"},
        ),
        (
            "azure",
            "AZURE_OPENAI_API_KEY" in os.environ and bool(os.getenv("AZURE_OPENAI_API_KEY")),
            {"endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", "")},
        ),
        (
            "gemini",
            "GEMINI_API_KEY" in os.environ and bool(os.getenv("GEMINI_API_KEY")),
            {"default_model": "gemini-1.5-pro"},
        ),
        (
            "ollama",
            "OLLAMA_BASE_URL" in os.environ and bool(os.getenv("OLLAMA_BASE_URL")),
            {"base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")},
        ),
    ]

    provider_statuses = []
    for name, is_configured, details in provider_checks:
        status_str = "configured" if is_configured else "unconfigured"
        provider_statuses.append(
            ProviderHealthStatus(
                provider=name,
                status=status_str,
                configured=is_configured,
                details=details,
            )
        )

    engine_status = "healthy" if LITELLM_AVAILABLE else "degraded"

    return HealthCheckResponse(
        status="ok" if LITELLM_AVAILABLE else "degraded",
        engine="LiteLLM Router v1.0",
        providers=provider_statuses,
    )
