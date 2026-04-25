"""LLM provider factory."""

from rich.console import Console
import typer

from amberclaw.config.schema import Config

console = Console()


def make_provider(config: Config):
    """Create the appropriate LLM provider from config."""
    from amberclaw.providers.openai_codex_provider import OpenAICodexProvider
    from amberclaw.providers.azure_openai_provider import AzureOpenAIProvider
    from amberclaw.providers.custom_provider import CustomProvider
    from amberclaw.providers.litellm_provider import LiteLLMProvider
    from amberclaw.providers.registry import find_by_name

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    # OpenAI Codex (OAuth)
    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model)

    # Custom: direct OpenAI-compatible endpoint, bypasses LiteLLM
    if provider_name == "custom":
        return CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )

    # Azure OpenAI: direct Azure OpenAI endpoint with deployment name
    if provider_name == "azure_openai":
        if not p or not p.api_key or not p.api_base:
            console.print("[red]Error: Azure OpenAI requires api_key and api_base.[/red]")
            console.print(
                "Set them in ~/.amberclaw/config.json under providers.azure_openai section"
            )
            console.print("Use the model field to specify the deployment name.")
            raise typer.Exit(1)

        return AzureOpenAIProvider(
            api_key=p.api_key,
            api_base=p.api_base,
            default_model=model,
        )

    # Ollama: direct local endpoint, supports vision
    if provider_name == "ollama":
        from amberclaw.providers.ollama_provider import OllamaProvider

        return OllamaProvider(
            api_key=p.api_key if p else None,
            api_base=config.get_api_base(model),
            default_model=model,
        )

    spec = find_by_name(provider_name)
    if not model.startswith("bedrock/") and not (p and p.api_key) and not (spec and spec.is_oauth):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.amberclaw/config.json under providers section")
        raise typer.Exit(1)

    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
    )
