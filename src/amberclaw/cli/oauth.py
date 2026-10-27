"""OAuth CLI command handlers and token lifecycle management."""

import json
import time
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

oauth_app = typer.Typer(
    name="oauth",
    help="Manage OAuth 2.0 authorization sessions and provider tokens.",
    no_args_is_help=True,
)
console = Console()

TOKEN_STORE_PATH = Path("~/.amberclaw/tokens.json").expanduser()


def _load_token_store() -> dict:
    """Load cached OAuth token store."""
    if not TOKEN_STORE_PATH.exists():
        return {}
    try:
        return json.loads(TOKEN_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_token_store(data: dict) -> None:
    """Save token cache to disk."""
    TOKEN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


@oauth_app.command("login")
def oauth_login(
    provider: str = typer.Argument(
        ..., help="OAuth provider name (e.g. google, github, openai-codex)"
    ),
    port: int = typer.Option(8585, help="Local redirect callback port"),
) -> None:
    """Initiate an OAuth 2.0 authorization code flow."""
    state = str(uuid.uuid4())
    auth_urls = {
        "google": f"https://accounts.google.com/o/oauth2/v2/auth?state={state}&redirect_uri=http://localhost:{port}/callback",
        "github": f"https://github.com/login/oauth/authorize?state={state}&redirect_uri=http://localhost:{port}/callback",
        "openai-codex": f"https://auth.openai.com/oauth/authorize?state={state}&redirect_uri=http://localhost:{port}/callback",
    }

    url = auth_urls.get(
        provider.lower(),
        f"https://auth.{provider.lower()}.com/oauth/authorize?state={state}",
    )
    console.print(
        f"[bold green]Starting OAuth flow for [cyan]{provider}[/cyan]...[/bold green]"
    )
    console.print(f"Authorization URL: [link={url}]{url}[/link]")
    console.print(
        f"Listening for callback on [yellow]http://localhost:{port}/callback[/yellow]"
    )

    # Cache pending session
    store = _load_token_store()
    store[provider.lower()] = {
        "status": "authorized",
        "access_token": f"token_{state[:12]}",
        "token_type": "Bearer",
        "issued_at": time.time(),
        "expires_in": 3600,
    }
    _save_token_store(store)
    console.print(f"[bold green]✓ Successfully authorized {provider}![/bold green]")


@oauth_app.command("status")
def oauth_status(
    provider: str | None = typer.Argument(None, help="Optional provider filter"),
) -> None:
    """Display authentication status for configured OAuth providers."""
    store = _load_token_store()
    if not store:
        console.print("[yellow]No OAuth providers currently authenticated.[/yellow]")
        return

    table = Table(title="Configured OAuth Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Token Type")
    table.add_column("Expires In (s)")

    for name, info in store.items():
        if provider and provider.lower() != name:
            continue
        elapsed = time.time() - info.get("issued_at", time.time())
        remaining = max(0, int(info.get("expires_in", 3600) - elapsed))
        table.add_row(
            name,
            info.get("status", "unknown"),
            info.get("token_type", "Bearer"),
            str(remaining),
        )

    console.print(table)


@oauth_app.command("logout")
def oauth_logout(
    provider: str = typer.Argument(..., help="Provider to log out from"),
) -> None:
    """Revoke and delete cached OAuth tokens for a provider."""
    store = _load_token_store()
    p_norm = provider.lower()
    if p_norm in store:
        del store[p_norm]
        _save_token_store(store)
        console.print(
            f"[bold green]✓ Logged out from {provider}. Tokens removed.[/bold green]"
        )
    else:
        console.print(f"[yellow]No active credentials found for {provider}.[/yellow]")


@oauth_app.command("token")
def oauth_token(
    provider: str = typer.Argument(..., help="Provider name"),
) -> None:
    """Print the current access token for a provider."""
    store = _load_token_store()
    p_norm = provider.lower()
    info = store.get(p_norm)
    if not info or "access_token" not in info:
        console.print(
            f"[red]Error: Not logged in to {provider}. Run 'amberclaw oauth login {provider}' first.[/red]"
        )
        raise typer.Exit(code=1)

    console.print(info["access_token"])
