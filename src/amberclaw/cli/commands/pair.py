import typer
from rich.console import Console
from amberclaw.security.dm_pairing import generate_pairing_code

console = Console()


def pair(
    expires: int = typer.Option(
        600,
        "--expires",
        "-e",
        help="Expiration time in seconds for the generated pairing code",
    ),
) -> None:
    """Generate a secure verification code for DM pairing."""
    code = generate_pairing_code(expires)
    console.print(
        "\n🔑 [bold green]New DM Pairing Code generated successfully![/bold green]"
    )
    console.print(f"Code: [bold cyan]{code}[/bold cyan]")
    console.print(f"Expires in: [yellow]{expires} seconds[/yellow]\n")
    console.print(
        "To pair your chat account, send the following command on your messaging platform:"
    )
    console.print(f"   [bold magenta]/pair {code}[/bold magenta]\n")
