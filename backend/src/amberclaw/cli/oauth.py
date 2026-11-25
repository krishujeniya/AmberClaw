"""OAuth CLI commands backed by the same real Codex token store as the provider."""

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer
from oauth_cli_kit import OPENAI_CODEX_PROVIDER, OAuthToken, login_oauth_interactive
from oauth_cli_kit.storage import FileTokenStorage
from rich.console import Console
from rich.table import Table

oauth_app = typer.Typer(
    name="oauth",
    help="Manage supported OAuth authorization sessions and provider tokens.",
    no_args_is_help=True,
)
console = Console()
TOKEN_STORE_PATH: Path = FileTokenStorage(
    token_filename=OPENAI_CODEX_PROVIDER.token_filename,
    import_codex_cli=False,
).get_token_path()
_CODEX_CALLBACK_PORT = urlparse(OPENAI_CODEX_PROVIDER.redirect_uri).port
_CODEX_NAMES = frozenset({"codex", "openai-codex", "openai_codex"})


def _token_from_data(data: object) -> OAuthToken | None:
    """Validate cached credentials without coercing or inventing token fields."""
    if not isinstance(data, dict):
        return None
    access = data.get("access")
    refresh = data.get("refresh")
    expires = data.get("expires")
    account_id = data.get("account_id")
    if not isinstance(access, str) or not access.strip():
        return None
    if not isinstance(refresh, str) or not refresh.strip():
        return None
    if not isinstance(expires, int) or isinstance(expires, bool) or expires <= 0:
        return None
    if not isinstance(account_id, str) or not account_id.strip():
        return None
    return OAuthToken(
        access=access, refresh=refresh, expires=expires, account_id=account_id
    )


def _load_token_store() -> dict[str, Any]:
    """Read only well-formed Codex credentials; status never refreshes or imports."""
    try:
        data = json.loads(TOKEN_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if _token_from_data(data) is None:
        return {}
    return dict(data)


class _CodexTokenStorage(FileTokenStorage):  # type: ignore[misc]  # Installed oauth-cli-kit base has no typing metadata
    """Use the provider's canonical token path with validated, side-effect-free reads."""

    def get_token_path(self) -> Path:
        return TOKEN_STORE_PATH

    def load(self) -> OAuthToken | None:
        return _token_from_data(_load_token_store())

    def save(self, token: OAuthToken) -> None:
        if _token_from_data(vars(token)) is None:
            raise ValueError("OAuth provider returned invalid credentials")
        super().save(token)


def login_provider(provider: str, port: int | None = None) -> None:
    """Run the installed, configured provider flow and report success only afterward."""
    if provider.lower() not in _CODEX_NAMES:
        console.print(
            "[red]OAuth is not configured for this provider. Supported provider: openai-codex.[/red]"
        )
        raise typer.Exit(code=1)
    if port is not None and port != _CODEX_CALLBACK_PORT:
        console.print(
            f"[red]The Codex OAuth flow requires callback port {_CODEX_CALLBACK_PORT}.[/red]"
        )
        raise typer.Exit(code=1)
    try:
        token = login_oauth_interactive(
            print_fn=console.print,
            prompt_fn=typer.prompt,
            provider=OPENAI_CODEX_PROVIDER,
            originator="amberclaw",
            storage=_CodexTokenStorage(import_codex_cli=False),
        )
        if _token_from_data(vars(token)) is None:
            raise ValueError("OAuth provider returned invalid credentials")
    except Exception as exc:
        console.print(f"[red]OAuth authorization failed ({type(exc).__name__}).[/red]")
        raise typer.Exit(code=1) from exc
    console.print("[bold green]✓ Successfully authorized openai-codex.[/bold green]")


@oauth_app.command("login")
def oauth_login(
    provider: str = typer.Argument(
        ..., help="Configured OAuth provider: openai-codex (alias: codex)"
    ),
    port: int = typer.Option(
        _CODEX_CALLBACK_PORT,
        help="Codex callback port (fixed by the installed OAuth flow)",
    ),
) -> None:
    """Authorize Codex through the installed browser/callback and token-exchange flow."""
    login_provider(provider, port)


@oauth_app.command("status")
def oauth_status(
    provider: str | None = typer.Argument(None, help="Optional provider filter"),
) -> None:
    """Display local credential status without refreshing or opening a browser."""
    token = _CodexTokenStorage(import_codex_cli=False).load()
    if not token or (provider and provider.lower() not in _CODEX_NAMES):
        console.print("[yellow]No OAuth providers currently authenticated.[/yellow]")
        return
    remaining = max(0, (token.expires - int(time.time() * 1000)) // 1000)
    table = Table(title="Configured OAuth Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Status")
    table.add_column("Token Type")
    table.add_column("Expires In (s)")
    table.add_row(
        "openai-codex",
        "authorized" if remaining else "expired",
        "Bearer",
        str(remaining),
    )
    console.print(table)


@oauth_app.command("logout")
def oauth_logout(
    provider: str = typer.Argument(..., help="Provider to log out from"),
) -> None:
    """Delete locally stored credentials; no remote token revocation is performed."""
    if provider.lower() not in _CODEX_NAMES:
        console.print(
            "[yellow]No configured OAuth credentials for this provider.[/yellow]"
        )
        raise typer.Exit(code=1)
    if TOKEN_STORE_PATH.exists():
        TOKEN_STORE_PATH.unlink()
        console.print(
            "[bold green]✓ Logged out from openai-codex. Local tokens removed.[/bold green]"
        )
    else:
        console.print("[yellow]No active credentials found for openai-codex.[/yellow]")


@oauth_app.command("token")
def oauth_token(
    provider: str = typer.Argument(..., help="Provider name"),
) -> None:
    """Print an existing, unexpired Codex access token without a network refresh."""
    token = _CodexTokenStorage(import_codex_cli=False).load()
    if (
        provider.lower() not in _CODEX_NAMES
        or token is None
        or token.expires <= time.time() * 1000
    ):
        console.print(
            "[red]No unexpired credentials. Run 'amberclaw oauth login openai-codex'.[/red]"
        )
        raise typer.Exit(code=1)
    console.print(token.access, markup=False)
