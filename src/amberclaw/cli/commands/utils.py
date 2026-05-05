import os
import select
import sys
import signal
from typing import Any, Iterator, cast
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from amberclaw import __logo__

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None

def _flush_pending_tty_input() -> None:
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return

def _restore_terminal() -> None:
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass

def _init_prompt_session() -> None:
    global _PROMPT_SESSION
    from amberclaw.config.paths import get_cli_history_path
    history_file = get_cli_history_path()
    history_file.parent.mkdir(parents=True, exist_ok=True)
    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,
    )

def _setup_terminal() -> None:
    global _SAVED_TERM_ATTRS
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

def _print_agent_response(response: str, render_markdown: bool) -> None:
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[cyan]{__logo__} AmberClaw[/cyan]")
    console.print(body)
    console.print()

class TokenStreamer:
    def __init__(self, console: Console, render_markdown: bool) -> None:
        self.console = console
        self.render_markdown = render_markdown
        self.content = ""
        self.live = None
        self.header_printed = False

    async def on_token(self, token: str) -> None:
        if not self.header_printed:
            self.console.print()
            self.console.print(f"[cyan]{__logo__} AmberClaw[/cyan]")
            from rich.live import Live
            self.live = Live("", console=self.console, refresh_per_second=12, auto_refresh=True)
            self.live.start()
            self.header_printed = True

        self.content += token
        if self.live:
            if self.render_markdown:
                from rich.markdown import Markdown
                self.live.update(Markdown(self.content))
            else:
                self.live.update(self.content)

    def stop(self) -> None:
        if self.live:
            self.live.stop()
            self.live = None
            self.console.print()

def _is_exit_command(command: str) -> bool:
    return command.lower() in EXIT_COMMANDS

async def _read_interactive_input_async() -> str:
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            result = await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),
            )
            return cast(str, result)
    except EOFError as exc:
        raise KeyboardInterrupt from exc
