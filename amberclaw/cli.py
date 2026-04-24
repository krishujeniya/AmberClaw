"""AmberClaw CLI: The Unified AI Product Entry Point."""

import sys
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text

# Core Feature Imports (Unified)
from amberclaw.features.council import run_council_session
from amberclaw.features.mythos import MythosThoughtLoop
from amberclaw.platforms.manager import PlatformManager

console = Console()

class AmberClawApp:
    def __init__(self):
        from amberclaw.engine.memory import ReinforcementMemory
        self.platform = PlatformManager.get_platform()
        # Initializing core engine components
        self.memory = ReinforcementMemory()
        self.default_model = "gemini-1.5-pro"
        console.print(Panel(
            Text("AMBERCLAW v3.0.0 (Unified Core)", style="bold gold1"),
            subtitle=f"Environment: {self.platform}",
            border_style="cyan"
        ))

    async def main_loop(self):
        """
        The heartbeat of the AmberClaw terminal experience.
        """
        while True:
            try:
                user_input = console.input("[bold cyan]>>> [/]")
                if user_input.lower() in ['exit', 'quit']:
                    console.print("[bold red]AmberClaw shutting down...[/]")
                    break
                
                # Check for special commands
                if user_input.startswith('/'):
                    await self.handle_command(user_input)
                    continue

                # Default: Run council and reasoning flow
                await self.generate_response(user_input)
                
            except KeyboardInterrupt:
                break

    async def handle_command(self, cmd: str):
        if "/council" in cmd:
            console.print("[bold yellow]Activating LLM Council consensus...[/]")
            query = cmd.replace("/council", "").strip()
            if not query:
                console.print("[red]Usage: /council <query>[/]")
                return
            # Mocking agent for demo (in real app, use self.agent)
            result = await run_council_session(self, query, ["gemini-1.5-pro", "claude-3-sonnet"], "gemini-1.5-pro")
            console.print(Panel(result["final_answer"], title="COUNCIL VERDICT"))
            
        elif "/mythos" in cmd:
            console.print("[bold magenta]Engaging Mythos reasoning engine...[/]")
            query = cmd.replace("/mythos", "").strip()
            if not query:
                console.print("[red]Usage: /mythos <query>[/]")
                return
            mythos = MythosThoughtLoop(self)
            result = await mythos.think(query)
            console.print(Panel(result, title="MYTHOS SYNTHESIS"))
        else:
            console.print(f"[red]Unknown command: {cmd}[/]")

    async def generate_response(self, prompt: str):
        """
        Standard generation flow with Mythos behavior enabled by default.
        """
        with console.status("[bold cyan]Processing with Mythos reasoning..."):
            mythos = MythosThoughtLoop(self)
            response = await mythos.think(prompt, depth=2)
            console.print(Panel(response, title="AMBERCLAW RESPONSE"))

    async def query_model(self, model: str, messages: list):
        """Mock query_model for structural integrity."""
        return f"[MOCK_RESPONSE from {model}] Standard processing..."

if __name__ == "__main__":
    app = AmberClawApp()
    asyncio.run(app.main_loop())
