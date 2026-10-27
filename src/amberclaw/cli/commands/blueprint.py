"""Blueprint management CLI commands."""

from pathlib import Path

import typer
import yaml
from rich.panel import Panel
from rich.table import Table

from amberclaw.blueprints.applier import BlueprintApplier
from amberclaw.blueprints.loader import BlueprintLoader
from amberclaw.blueprints.validator import BlueprintValidator
from amberclaw.config.loader import get_config_path, load_config, save_config

from .utils import console

blueprint_app = typer.Typer(help="Manage declarative agent blueprint configurations")


@blueprint_app.command("list")
def blueprint_list() -> None:
    """List available agent blueprint presets."""
    loader = BlueprintLoader()
    presets = loader.list_available_presets()

    table = Table(title="Available Agent Blueprint Presets")
    table.add_column("Preset Name", style="bold cyan")
    table.add_column("Model", style="green")
    table.add_column("Sandbox", style="magenta")
    table.add_column("Skills Included", style="yellow")

    for name in sorted(presets):
        try:
            bp = loader.load_preset(name)
            table.add_row(
                bp.name,
                bp.agent.model_name,
                bp.security.sandbox_type,
                ", ".join(bp.skills) if bp.skills else "(none)",
            )
        except Exception as ex:
            table.add_row(name, "Error", "-", str(ex))

    console.print(table)


@blueprint_app.command("show")
def blueprint_show(
    name_or_path: str = typer.Argument(
        ..., help="Preset name (e.g. 'developer') or path to YAML file"
    ),
) -> None:
    """Show details and configuration for a blueprint."""
    loader = BlueprintLoader()
    path = Path(name_or_path)

    try:
        if path.is_file():
            bp = loader.load_from_file(path)
        else:
            bp = loader.load_preset(name_or_path)
    except Exception as ex:
        console.print(f"[bold red]Failed to load blueprint '{name_or_path}': {ex}[/bold red]")
        raise typer.Exit(code=1) from ex

    dumped_yaml = yaml.dump(bp.model_dump(), sort_keys=False)
    console.print(Panel(dumped_yaml, title=f"Blueprint: [bold cyan]{bp.name}[/bold cyan] (v{bp.version})"))


@blueprint_app.command("validate")
def blueprint_validate(
    file_path: Path = typer.Argument(..., help="Path to YAML blueprint file to validate"),
) -> None:
    """Validate a YAML blueprint file against the AmberClaw schema."""
    loader = BlueprintLoader()
    validator = BlueprintValidator()

    if not file_path.is_file():
        console.print(f"[bold red]File not found: {file_path}[/bold red]")
        raise typer.Exit(code=1)

    try:
        bp = loader.load_from_file(file_path)
    except Exception as ex:
        console.print(f"[bold red]Failed to parse YAML blueprint: {ex}[/bold red]")
        raise typer.Exit(code=1) from ex

    res = validator.validate(bp)
    if res.is_valid:
        console.print(f"[bold green]✓ Blueprint '{bp.name}' is valid![/bold green]")
        if res.warnings:
            for w in res.warnings:
                console.print(f"[yellow]Warning: {w}[/yellow]")
    else:
        console.print(f"[bold red]✗ Blueprint '{bp.name}' failed validation:[/bold red]")
        for err in res.errors:
            console.print(f"  [red]• {err}[/red]")
        raise typer.Exit(code=1)


@blueprint_app.command("apply")
def blueprint_apply(
    name_or_path: str = typer.Argument(
        ..., help="Preset name (e.g. 'developer') or path to YAML file"
    ),
) -> None:
    """Apply a blueprint preset or custom YAML file to active configuration."""
    loader = BlueprintLoader()
    applier = BlueprintApplier()
    path = Path(name_or_path)

    try:
        if path.is_file():
            bp = loader.load_from_file(path)
        else:
            bp = loader.load_preset(name_or_path)
    except Exception as ex:
        console.print(f"[bold red]Failed to load blueprint '{name_or_path}': {ex}[/bold red]")
        raise typer.Exit(code=1) from ex

    current_cfg = load_config().model_dump()
    report = applier.apply(bp, target_config=current_cfg)

    if not report.success:
        console.print(f"[bold red]Failed to apply blueprint: {report.errors}[/bold red]")
        raise typer.Exit(code=1)

    cfg_path = get_config_path()
    save_config(report.applied_settings, cfg_path)
    console.print(
        f"[bold green]✓ Successfully applied blueprint '[cyan]{bp.name}[/cyan]' to active configuration![/bold green]"
    )
