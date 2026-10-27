"""High-level unified inference router coordinating profiles, PII scrubbing, and fallback models."""

import time

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.inference.pii_scanner import InferencePIIScanner
from amberclaw.inference.profiles import InferenceProfile, ProfileRegistry
from amberclaw.inference.proxy import InferenceProxyManager
from amberclaw.providers.litellm_client import LLMMessage, LLMRouter


class InferenceRequest(BaseModel):
    """Specification of a prompt invocation passed to the inference router."""

    prompt: str = Field(..., description="The user or agent prompt text")
    system_prompt: str | None = Field(
        default=None, description="Optional system prompt"
    )
    profile: str = Field(
        default="balanced", description="Inference profile tier (fast, balanced, etc.)"
    )
    model: str | None = Field(default=None, description="Explicit model override")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    sanitize_pii: bool = Field(
        default=True, description="Whether to redact PII prior to dispatch"
    )


class InferenceResponse(BaseModel):
    """Structured response produced by the inference router."""

    reply: str
    model_used: str
    profile_used: str
    pii_sanitized: bool = False
    latency_ms: float = 0.0


class InferenceRouter:
    """Enterprise inference router featuring profile selection, PII protection, and multi-tier fallbacks."""

    def __init__(
        self,
        llm_router: LLMRouter | None = None,
        profile_registry: ProfileRegistry | None = None,
        pii_scanner: InferencePIIScanner | None = None,
        proxy_manager: InferenceProxyManager | None = None,
    ) -> None:
        self.llm_router = llm_router or LLMRouter()
        self.profile_registry = profile_registry or ProfileRegistry()
        self.pii_scanner = pii_scanner or InferencePIIScanner()
        self.proxy_manager = proxy_manager or InferenceProxyManager()

    async def execute(self, request: InferenceRequest) -> InferenceResponse:
        """Execute inference with PII sanitization and fallback model failover."""
        start = time.time()
        profile: InferenceProfile = self.profile_registry.get_profile(request.profile)

        effective_text = request.prompt
        pii_detected = False
        if request.sanitize_pii:
            scan_res = self.pii_scanner.scan(request.prompt)
            effective_text = scan_res.sanitized_text
            pii_detected = scan_res.has_pii

        messages = []
        if request.system_prompt:
            messages.append(LLMMessage(role="system", content=request.system_prompt))
        messages.append(LLMMessage(role="user", content=effective_text))

        candidate_models = []
        if request.model:
            candidate_models.append(request.model)
        else:
            candidate_models.append(profile.model)
            candidate_models.extend(profile.fallback_models)

        temp = (
            request.temperature
            if request.temperature is not None
            else profile.temperature
        )

        last_error: Exception | None = None
        for model_name in candidate_models:
            provider_prefix = (
                model_name.split("/")[0] if "/" in model_name else "default"
            )
            if not self.proxy_manager.is_available(provider_prefix):
                logger.warning(
                    "Skipping model '{}': provider circuit breaker open", model_name
                )
                continue

            try:
                reply = await self.llm_router.generate(
                    messages=messages,
                    model=model_name,
                    temperature=temp,
                )
                self.proxy_manager.record_success(provider_prefix)
                elapsed_ms = (time.time() - start) * 1000.0

                return InferenceResponse(
                    reply=reply,
                    model_used=model_name,
                    profile_used=profile.name,
                    pii_sanitized=pii_detected,
                    latency_ms=round(elapsed_ms, 2),
                )
            except Exception as exc:
                logger.warning(
                    "Model '{}' failed during inference: {}", model_name, exc
                )
                self.proxy_manager.record_failure(provider_prefix)
                last_error = exc

        raise RuntimeError(
            f"All candidate models ({candidate_models}) failed for profile '{profile.name}'. Last error: {last_error}"
        )
