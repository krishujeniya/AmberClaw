import typer
from rich.console import Console
from rich.panel import Panel
import pandas as pd
from typing import Optional
import os
from pathlib import Path
from sqlalchemy import create_engine
from langchain_core.language_models import BaseLanguageModel
from .agents._contracts import LanguageModel
from . import DataCleaningAgent, DataVisualizationAgent, SQLDatabaseAgent

app = typer.Typer(
    name="data",
    help="🚀 DataAgent: Your AI-powered Data Science Team in the Terminal.",
    add_completion=False,
)
console = Console()


def _configured_model() -> LanguageModel:
    """Construct the configured provider's LangChain adapter only for an invocation."""
    from amberclaw.config.loader import load_config
    from amberclaw.providers.factory import make_provider

    config = load_config()
    defaults = config.agents.defaults
    model = make_provider(config).to_langchain_chat(
        model=defaults.model,
        temperature=defaults.temperature,
        max_tokens=defaults.max_tokens,
    )
    if not isinstance(model, BaseLanguageModel):
        raise TypeError("The configured provider did not return a LangChain language model")
    return model


@app.callback()
def callback() -> None:
    """
    DataAgent - Intent-based Data Science CLI.
    Just give your data a vibe, and our agents handle the rest.
    """
    pass


@app.command()
def clean(
    file_path: str = typer.Argument(..., help="Path to the CSV file to clean"),
    output: str = typer.Option(
        "cleaned_data.csv", "--output", "-o", help="Path to save the cleaned data"
    ),
    instructions: Optional[str] = typer.Option(
        None, "--instructions", "-i", help="Custom instructions for the cleaning agent"
    ),
) -> None:
    """
    🧹 Clean a dataset using the AI Data Cleaning Agent.
    """
    console.print(
        Panel(
            f"🧼 [bold blue]Cleaning Agent[/bold blue] started for: [yellow]{file_path}[/yellow]",
            title="DataAgent",
        )
    )

    if not os.path.exists(file_path):
        console.print(f"[red]Error: File {file_path} not found.[/red]")
        raise typer.Exit(1)

    df = pd.read_csv(file_path)
    agent = DataCleaningAgent(model=_configured_model())

    with console.status("[bold green]Cleaning in progress..."):
        agent.invoke_agent(data_raw=df, user_instructions=instructions)
        cleaned_df = agent.get_data_cleaned()

    if cleaned_df is None:
        console.print("[red]Error: The agent did not return cleaned data.[/red]")
        raise typer.Exit(1)

    cleaned_df.to_csv(output, index=False)
    console.print(
        f"✅ [green]Success![/green] Cleaned data saved to [bold cyan]{output}[/bold cyan]"
    )


@app.command()
def viz(
    file_path: str = typer.Argument(..., help="Path to the CSV file to visualize"),
    goal: str = typer.Option(
        "Create a descriptive analysis and key visualizations",
        "--goal",
        "-g",
        help="What do you want to see?",
    ),
) -> None:
    """
    📊 Visualize your data using the AI Data Visualization Agent.
    """
    console.print(
        Panel(
            f"📈 [bold magenta]Visualization Agent[/bold magenta] analyzing: [yellow]{file_path}[/yellow]",
            title="DataAgent",
        )
    )

    if not os.path.exists(file_path):
        console.print(f"[red]Error: File {file_path} not found.[/red]")
        raise typer.Exit(1)

    df = pd.read_csv(file_path)
    agent = DataVisualizationAgent(model=_configured_model())

    with console.status("[bold green]Generating visualizations..."):
        agent.invoke_agent(data_raw=df, user_instructions=goal)

    console.print("✅ [green]Visualizations generated successfully![/green]")


@app.command()
def sql(
    db_path: str = typer.Argument(..., help="Path to the SQLite database"),
    query: str = typer.Argument(..., help="Natural language query for the database"),
) -> None:
    """
    🗄️ Query a SQL database using the AI SQL Database Agent.
    """
    console.print(
        Panel(
            f"🔍 [bold cyan]SQL Agent[/bold cyan] querying: [yellow]{db_path}[/yellow]\n[italic]'{query}'[/italic]",
            title="DataAgent",
        )
    )

    if not os.path.exists(db_path):
        console.print(f"[red]Error: Database {db_path} not found.[/red]")
        raise typer.Exit(1)

    model = _configured_model()
    engine = create_engine("sqlite:///" + str(Path(db_path).resolve()))
    try:
        agent = SQLDatabaseAgent(model=model, connection=engine)
        with console.status("[bold green]Executing SQL query..."):
            agent.invoke_agent(user_instructions=query)
            response = agent.get_data_sql()
        if response is None:
            console.print("[red]Error: The agent did not return query results.[/red]")
            raise typer.Exit(1)
        console.print(Panel(str(response), title="Agent Response"))
    finally:
        engine.dispose()


if __name__ == "__main__":
    app()
