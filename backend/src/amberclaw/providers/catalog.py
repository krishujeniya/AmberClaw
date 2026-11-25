"""Provider model catalog validation and fuzzy matching."""

from __future__ import annotations

import difflib

from pydantic import BaseModel, Field

# Canonical models grouped by provider
CANONICAL_PROVIDER_CATALOG: dict[str, list[str]] = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o1-preview",
        "o3-mini",
        "chatgpt-4o-latest",
    ],
    "anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-3-7-sonnet",
        "claude-4-opus",
    ],
    "google": [
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-pro-exp-02-05",
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-reasoner",
        "deepseek-r1",
        "deepseek-v3",
    ],
    "mistral": [
        "mistral-large-latest",
        "mistral-small-latest",
        "codestral-latest",
        "pixtral-large-latest",
    ],
    "meta": [
        "llama-3.1-8b-instruct",
        "llama-3.1-70b-instruct",
        "llama-3.2-3b-instruct",
        "llama-3.3-70b-instruct",
        "llama3",
        "llama3:8b",
        "llama3:70b",
    ],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    ],
    "cohere": [
        "command-r",
        "command-r-plus",
    ],
}

# Common aliases mapping to canonical model names
MODEL_ALIASES: dict[str, str] = {
    "gpt4o": "gpt-4o",
    "gpt4o-mini": "gpt-4o-mini",
    "gpt-4o-latest": "gpt-4o",
    "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3.5-haiku": "claude-3-5-haiku-20241022",
    "claude-3-opus": "claude-3-opus-20240229",
    "claude-3-sonnet": "claude-3-sonnet-20240229",
    "claude-3-haiku": "claude-3-haiku-20240307",
    "gemini-pro": "gemini-1.5-pro",
    "gemini-flash": "gemini-1.5-flash",
    "deepseek-r1": "deepseek-reasoner",
}

# Flat list of all known models
ALL_KNOWN_MODELS = [
    model for models in CANONICAL_PROVIDER_CATALOG.values() for model in models
] + list(MODEL_ALIASES.keys())


class ModelValidationResult(BaseModel):
    """Validation report for an LLM model identifier."""

    model: str
    is_valid: bool
    canonical_name: str
    provider: str | None = None
    suggested_alternatives: list[str] = Field(default_factory=list)
    warning: str | None = None


def validate_model_name(
    model: str,
    provider: str | None = None,
) -> ModelValidationResult:
    """Validate a model identifier against provider catalogs.

    Performs:
      1. Canonical lookup and alias resolution.
      2. Provider prefix handling (e.g. 'openai/gpt-4o' -> 'gpt-4o').
      3. Fuzzy Levenshtein matching for misspelled model names.
      4. Passthrough for custom or local models.
    """
    clean_model = model.strip()
    prefix = None
    bare_model = clean_model

    if "/" in clean_model:
        prefix, bare_model = clean_model.split("/", 1)
        prefix = prefix.lower()

    effective_provider = provider or prefix

    # Custom or direct model endpoints are considered valid
    if prefix in ("custom", "local", "azure", "vllm", "ollama", "openai-codex"):
        return ModelValidationResult(
            model=model,
            is_valid=True,
            canonical_name=bare_model,
            provider=effective_provider,
        )

    # 1. Direct alias resolution
    if bare_model in MODEL_ALIASES:
        canonical = MODEL_ALIASES[bare_model]
        return ModelValidationResult(
            model=model,
            is_valid=True,
            canonical_name=f"{prefix}/{canonical}" if prefix else canonical,
            provider=effective_provider,
            warning=f"Model '{bare_model}' is an alias for '{canonical}'.",
        )

    # 2. Check within specific provider if known
    if effective_provider and effective_provider in CANONICAL_PROVIDER_CATALOG:
        provider_models = CANONICAL_PROVIDER_CATALOG[effective_provider]
        if bare_model in provider_models:
            return ModelValidationResult(
                model=model,
                is_valid=True,
                canonical_name=clean_model,
                provider=effective_provider,
            )
        # Fuzzy match within this provider's catalog
        suggestions = difflib.get_close_matches(
            bare_model, provider_models, n=3, cutoff=0.5
        )
        full_suggestions = [f"{prefix}/{s}" if prefix else s for s in suggestions]
        return ModelValidationResult(
            model=model,
            is_valid=False,
            canonical_name=clean_model,
            provider=effective_provider,
            suggested_alternatives=full_suggestions,
            warning=(
                f"Model '{bare_model}' not found in '{effective_provider}' catalog. "
                f"Did you mean: {', '.join(full_suggestions)}?"
                if full_suggestions
                else f"Model '{bare_model}' not found in '{effective_provider}' catalog."
            ),
        )

    # 3. Check across all catalogs
    for prov_name, models in CANONICAL_PROVIDER_CATALOG.items():
        if bare_model in models:
            return ModelValidationResult(
                model=model,
                is_valid=True,
                canonical_name=clean_model,
                provider=effective_provider or prov_name,
            )

    # 4. Global fuzzy match
    global_suggestions = difflib.get_close_matches(
        bare_model, ALL_KNOWN_MODELS, n=3, cutoff=0.5
    )
    return ModelValidationResult(
        model=model,
        is_valid=False,
        canonical_name=clean_model,
        provider=effective_provider,
        suggested_alternatives=global_suggestions,
        warning=(
            f"Unrecognized model '{clean_model}'. "
            f"Did you mean: {', '.join(global_suggestions)}?"
            if global_suggestions
            else f"Unrecognized model '{clean_model}'."
        ),
    )
