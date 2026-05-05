import typer
from rich.console import Console
from rich.table import Table
from amberclaw.config import paths

skills_app = typer.Typer(help="Manage amberclaw skills and capabilities.")
console = Console()

@skills_app.command()
def list():
    """List all installed skills."""
    workspace = paths.get_workspace_path()
    skills_dir = workspace / "skills"
    
    if not skills_dir.exists():
        console.print("[yellow]No skills directory found in workspace.[/yellow]")
        return
        
    table = Table(title="Installed Skills", box=None)
    table.add_column("Skill", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="green")
    
    # Mock listing logic based on directory contents
    for item in skills_dir.iterdir():
        if item.is_dir():
            table.add_row(item.name, "Custom", "Active")
            
    console.print(table)

@skills_app.command()
def install(name: str):
    """Install a new skill."""
    console.print(f"[green]Installing skill: {name}...[/green]")
    # Placeholder for actual installation logic
