import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import pandas as pd
from typing import Optional
import os
from . import DataCleaningAgent, DataVisualizationAgent, SQLDatabaseAgent

app = typer.Typer(
    name="data",
    help="🚀 DataAgent: Your AI-powered Data Science Team in the Terminal.",
    add_completion=False,
)
console = Console()

@app.callback()
def callback():
    """
    DataAgent - Intent-based Data Science CLI.
    Just give your data a vibe, and our agents handle the rest.
    """
    pass

@app.command()
def clean(
    file_path: str = typer.Argument(..., help="Path to the CSV file to clean"),
    output: str = typer.Option("cleaned_data.csv", "--output", "-o", help="Path to save the cleaned data"),
    instructions: Optional[str] = typer.Option(None, "--instructions", "-i", help="Custom instructions for the cleaning agent"),
):
    """
    🧹 Clean a dataset using the AI Data Cleaning Agent.
    """
    console.print(Panel(f"🧼 [bold blue]Cleaning Agent[/bold blue] started for: [yellow]{file_path}[/yellow]", title="DataAgent"))
    
    if not os.path.exists(file_path):
        console.print(f"[red]Error: File {file_path} not found.[/red]")
        raise typer.Exit(1)
        
    df = pd.read_csv(file_path)
    agent = DataCleaningAgent(df)
    
    with console.status("[bold green]Cleaning in progress...") as status:
        agent.invoke_agent(user_instructions=instructions)
        cleaned_df = agent.get_data_cleaned()
        
    cleaned_df.to_csv(output, index=False)
    console.print(f"✅ [green]Success![/green] Cleaned data saved to [bold cyan]{output}[/bold cyan]")

@app.command()
def viz(
    file_path: str = typer.Argument(..., help="Path to the CSV file to visualize"),
    goal: str = typer.Option("Create a descriptive analysis and key visualizations", "--goal", "-g", help="What do you want to see?"),
):
    """
    📊 Visualize your data using the AI Data Visualization Agent.
    """
    console.print(Panel(f"📈 [bold magenta]Visualization Agent[/bold magenta] analyzing: [yellow]{file_path}[/yellow]", title="DataAgent"))
    
    if not os.path.exists(file_path):
        console.print(f"[red]Error: File {file_path} not found.[/red]")
        raise typer.Exit(1)
        
    df = pd.read_csv(file_path)
    agent = DataVisualizationAgent(df)
    
    with console.status("[bold green]Generating visualizations...") as status:
        agent.invoke_agent(user_instructions=goal)
    
    console.print("✅ [green]Visualizations generated successfully![/green]")

@app.command()
def sql(
    db_path: str = typer.Argument(..., help="Path to the SQLite database"),
    query: str = typer.Argument(..., help="Natural language query for the database"),
):
    """
    🗄️ Query a SQL database using the AI SQL Database Agent.
    """
    console.print(Panel(f"🔍 [bold cyan]SQL Agent[/bold cyan] querying: [yellow]{db_path}[/yellow]\n[italic]'{query}'[/italic]", title="DataAgent"))
    
    if not os.path.exists(db_path):
        console.print(f"[red]Error: Database {db_path} not found.[/red]")
        raise typer.Exit(1)
        
    agent = SQLDatabaseAgent(db_path)
    
    with console.status("[bold green]Executing SQL query...") as status:
        response = agent.invoke_agent(user_instructions=query)
    
    console.print(Panel(str(response), title="Agent Response"))

if __name__ == "__main__":
    app()
