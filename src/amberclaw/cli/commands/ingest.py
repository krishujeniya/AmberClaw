import typer
from pathlib import Path
from rich.console import Console
from amberclaw.config import loader

console = Console()

def ingest(
    path: Path = typer.Argument(..., help="Path to file or directory to ingest"),
    collection: str = typer.Option("default", "--collection", "-c", help="Vector collection name"),
) -> None:
    """Ingest documents into the RAG memory."""
    from amberclaw.memory import rag_pipeline

    cfg = loader.load_config()
    
    ingestor = rag_pipeline.DocumentIngestor(
        workspace=cfg.workspace_path,
        collection=collection,
        embedding_model=cfg.agents.defaults.embedding_model,
    )
    
    console.print(f"[bold cyan]Ingesting {path} into '{collection}' collection...[/bold cyan]")
    count = ingestor.ingest(path)
    console.print(f"[green]✓ Successfully ingested {count} documents.[/green]")
