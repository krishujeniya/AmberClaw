import typer
import sys
from rich.console import Console
from amberclaw.vemy.AI import VemyAgent, ChatService
from amberclaw.vemy.Tools.MongoDB import MongoDBManager
from amberclaw.vemy.Tools.Google_Drive import GoogleDriveManager
from amberclaw.vemy.Tools.Telegram import TelegramService
from amberclaw.vemy.Tools.RAG import RAGService
from amberclaw.vemy.Credentials.Settings import Config

app = typer.Typer(
    name="vemy",
    help="🤖 Vemy: Modular AI Assistant with RAG and Telegram integration.",
    no_args_is_help=True,
)
console = Console()

class VemyPipeline:
    """Main application pipeline, adapted from Vemy-py/main.py"""
    
    def __init__(self):
        self.mongodb_manager = MongoDBManager()
        self.drive_manager = GoogleDriveManager()
        self.vemy_agent = None
        self.chat_service = None
        self.telegram_service = None
        self.rag_service = None
        
    def initialize(self):
        """Initialize all core components"""
        try:
            Config.validate()
        except ValueError as e:
            console.print(f"[red]Error: Configuration error: {e}[/red]")
            return False
        
        self.mongodb_manager.connect()
        self.vemy_agent = VemyAgent()
        self.vemy_agent.initialize()
        self.drive_manager.connect()
        self.chat_service = ChatService(self.mongodb_manager, self.vemy_agent)
        
        console.print("✅ [green]Vemy is ready![/green]")
        return True

    def cleanup(self):
        """Cleanup resources"""
        if self.mongodb_manager:
            self.mongodb_manager.disconnect()

@app.command()
def telegram():
    """🤖 Start the Vemy Telegram Bot."""
    pipeline = VemyPipeline()
    if not pipeline.initialize():
        raise typer.Exit(1)
    
    try:
        console.print("\n🤖 [bold blue]Starting Telegram Bot...[/bold blue]")
        telegram_service = TelegramService(pipeline.chat_service)
        if telegram_service.setup():
            telegram_service.run()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.cleanup()
        console.print("\n✅ [green]Vemy shutdown complete[/green]")

@app.command()
def sync():
    """📚 Sync files from Google Drive to RAG storage."""
    pipeline = VemyPipeline()
    if not pipeline.initialize():
        raise typer.Exit(1)
    
    try:
        console.print("\n📚 [bold magenta]Starting RAG Sync...[/bold magenta]")
        rag_service = RAGService(pipeline.mongodb_manager, pipeline.drive_manager)
        if rag_service.initialize():
            rag_service.run_sync()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.cleanup()
        console.print("\n✅ [green]Vemy shutdown complete[/green]")

@app.command()
def status():
    """🔍 Check Vemy configuration and connection status."""
    Config.display()
    # Check connections
    mongo = MongoDBManager()
    if mongo.connect():
        console.print("✅ [green]MongoDB Connected[/green]")
        mongo.disconnect()
    else:
        console.print("❌ [red]MongoDB Connection Failed[/red]")
