"""Inference profiles, model capability tiers, and execution parameters."""

from enum import StrEnum

from loguru import logger
from pydantic import BaseModel, Field


class InferenceTier(StrEnum):
    """Categorization of model performance, latency, and cost trade-offs."""

    FAST = "fast"
    BALANCED = "balanced"
    ACCURATE = "accurate"
    REASONING = "reasoning"
    OFFLINE = "offline"


class InferenceProfile(BaseModel):
    """Execution configuration bundle governing model choice and generation limits."""

    name: str = Field(..., description="Unique profile name")
    tier: InferenceTier = Field(default=InferenceTier.BALANCED)
    model: str = Field(..., description="Primary LiteLLM model identifier")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Secondary models tried in order upon primary failure",
    )
    timeout_seconds: float = Field(default=30.0, ge=1.0)


class ProfileRegistry:
    """Registry maintaining available inference profiles."""

    def __init__(self) -> None:
        self._profiles: dict[str, InferenceProfile] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Register default operational profiles."""
        self.register_profile(
            InferenceProfile(
                name="fast",
                tier=InferenceTier.FAST,
                model="gpt-4o-mini",
                temperature=0.5,
                max_tokens=2048,
                fallback_models=["claude-3-5-haiku", "gemini/gemini-1.5-flash"],
                timeout_seconds=15.0,
            )
        )
        self.register_profile(
            InferenceProfile(
                name="balanced",
                tier=InferenceTier.BALANCED,
                model="gpt-4o",
                temperature=0.7,
                max_tokens=4096,
                fallback_models=["claude-3-5-sonnet", "deepseek/deepseek-chat"],
                timeout_seconds=30.0,
            )
        )
        self.register_profile(
            InferenceProfile(
                name="accurate",
                tier=InferenceTier.ACCURATE,
                model="claude-3-5-sonnet",
                temperature=0.2,
                max_tokens=8192,
                fallback_models=["gpt-4o", "gemini/gemini-1.5-pro"],
                timeout_seconds=45.0,
            )
        )
        self.register_profile(
            InferenceProfile(
                name="reasoning",
                tier=InferenceTier.REASONING,
                model="o3-mini",
                temperature=1.0,
                max_tokens=16384,
                fallback_models=["o1-mini", "deepseek/deepseek-reasoner"],
                timeout_seconds=60.0,
            )
        )
        self.register_profile(
            InferenceProfile(
                name="offline",
                tier=InferenceTier.OFFLINE,
                model="ollama/llama3.2",
                temperature=0.7,
                max_tokens=2048,
                fallback_models=[],
                timeout_seconds=30.0,
            )
        )

    def register_profile(self, profile: InferenceProfile) -> None:
        """Add or update an inference profile."""
        self._profiles[profile.name.lower()] = profile
        logger.debug(
            "Registered inference profile '{}' ({})", profile.name, profile.model
        )

    def get_profile(
        self, name_or_tier: str | InferenceTier = "balanced"
    ) -> InferenceProfile:
        """Retrieve an inference profile by name or tier, falling back to 'balanced'."""
        key = str(name_or_tier).lower()
        if key in self._profiles:
            return self._profiles[key]
        return self._profiles["balanced"]

    def list_profiles(self) -> list[InferenceProfile]:
        """List all registered profiles."""
        return list(self._profiles.values())
